"""
PPO (Proximal Policy Optimization) Reinforcement Learning Agent for gold trading.
Implements custom trading environment and PPO algorithm using PyTorch.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, List, Tuple
from utils.config import (
    INITIAL_CAPITAL, 
    COMMISSION_RATE,
    PPO_LEARNING_RATE,
    PPO_GAMMA,
    PPO_N_STEPS,
    PPO_BATCH_SIZE
)


class GoldTradingEnv(gym.Env):
    """
    Custom trading environment for gold price trading.
    
    State Space:
        - Current price
        - LSTM predicted price
        - Sentiment score
        - Technical indicators (RSI, MA, etc.)
        - Account balance
        - Current position
    
    Action Space:
        - 0: HOLD
        - 1: BUY
        - 2: SELL
    
    Reward:
        - Profit/loss from trades
        - Penalty for excessive trading
    """
    
    metadata = {'render_modes': ['human']}
    
    def __init__(self, price_data: np.ndarray, predictions: np.ndarray = None,
                 sentiment_scores: np.ndarray = None, initial_capital: float = INITIAL_CAPITAL,
                 commission_rate: float = COMMISSION_RATE, max_steps: int = None):
        """
        Initialize trading environment.
        
        Args:
            price_data: Array of price data with features
            predictions: LSTM predictions (optional)
            sentiment_scores: Sentiment scores (optional)
            initial_capital: Starting capital
            commission_rate: Trading commission rate
            max_steps: Maximum steps per episode
        """
        super(GoldTradingEnv, self).__init__()
        
        self.price_data = price_data
        self.predictions = predictions
        self.sentiment_scores = sentiment_scores
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        
        # Feature indices
        self.close_idx = 3  # Close price index
        
        # Calculate state space size
        self.feature_size = price_data.shape[1]
        # State = features + balance + position + prediction_diff + sentiment
        self.state_size = self.feature_size + 2  # +2 for balance and position
        
        if predictions is not None:
            self.state_size += 1  # +1 for prediction difference
        if sentiment_scores is not None:
            self.state_size += 1  # +1 for sentiment score
        
        # Action space: 0=HOLD, 1=BUY, 2=SELL
        self.action_space = spaces.Discrete(3)
        
        # Observation space
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.state_size,),
            dtype=np.float32
        )
        
        self.max_steps = max_steps or len(price_data) - 1
        
        # Trading parameters
        self.max_position_size = 10  # Maximum units of gold
        self.reward_scaling = 10.0  # Reduced scale for better stability
    
    def reset(self, seed=None, options=None):
        """Reset environment to initial state."""
        super().reset(seed=seed)
        
        self.current_step = 0
        self.balance = self.initial_capital
        self.position = 0  # Current gold holdings
        self.trades = []
        self.total_profit = 0.0
        self.steps_taken = 0
        
        # Get initial observation
        obs = self._get_observation()
        
        return obs, {}
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one step in the environment.
        
        Args:
            action: Action to take (0=HOLD, 1=BUY, 2=SELL)
        
        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        current_price = self.price_data[self.current_step, self.close_idx]
        
        # Execute action
        reward = 0.0
        
        if action == 1:  # BUY
            if self.balance > 0 and current_price > 1e-8:
                # Buy as much as possible with available balance
                max_affordable = self.balance / (current_price * (1 + self.commission_rate))
                buy_amount = min(max_affordable, self.max_position_size - self.position)
                
                if buy_amount > 0:
                    cost = buy_amount * current_price * (1 + self.commission_rate)
                    self.balance -= cost
                    self.position += buy_amount
                    self.trades.append({'type': 'buy', 'price': current_price, 'amount': buy_amount})
        
        elif action == 2:  # SELL
            if self.position > 0 and current_price > 1e-8:
                # Sell all or portion
                sell_amount = self.position
                revenue = sell_amount * current_price * (1 - self.commission_rate)
                self.balance += revenue
                self.position = 0
                self.trades.append({'type': 'sell', 'price': current_price, 'amount': sell_amount})
        
        # Calculate reward based on profit/loss
        if action == 1:  # After buying
            reward = -self.commission_rate * 10  # Small penalty for trading
        elif action == 2:  # After selling
            if len(self.trades) >= 2:
                buy_trades = [t for t in self.trades if t['type'] == 'buy']
                if buy_trades and abs(buy_trades[-1]['price']) > 1e-8:
                    last_buy = buy_trades[-1]
                    profit = (current_price - last_buy['price']) / last_buy['price']
                    reward = np.clip(profit * self.reward_scaling, -5, 5)  # Clip rewards
        
        # Holding reward: encourage holding during uptrends
        if action == 0 and self.position > 0:
            if self.current_step < len(self.price_data) - 1:
                next_price = self.price_data[self.current_step + 1, self.close_idx]
                if abs(current_price) > 1e-8:
                    price_change = (next_price - current_price) / current_price
                    reward += np.clip(price_change * self.reward_scaling * 0.5, -2, 2)  # Clip
        
        # Move to next step
        self.current_step += 1
        self.steps_taken += 1
        
        # Check termination
        terminated = self.current_step >= len(self.price_data) - 1
        truncated = self.steps_taken >= self.max_steps
        
        # Get new observation
        obs = self._get_observation()
        
        info = {
            'balance': self.balance,
            'position': self.position,
            'total_profit': self.balance + self.position * current_price - self.initial_capital,
            'current_price': current_price,
            'trades_count': len(self.trades)
        }
        
        return obs, reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """Get current state observation."""
        current_features = self.price_data[self.current_step].copy()
        
        # Normalize features more safely
        for i in range(len(current_features)):
            if abs(current_features[i]) > 1e-8:
                current_features[i] = current_features[i] / abs(current_features[i]) * 0.1
            else:
                current_features[i] = 0.0
        
        # Add account state
        current_price = self.price_data[self.current_step, self.close_idx]
        balance_norm = min(max(self.balance / self.initial_capital, 0), 2)  # Clip to [0, 2]
        position_norm = min(max(self.position / self.max_position_size, 0), 2)  # Clip to [0, 2]
        
        obs_parts = [current_features, [balance_norm], [position_norm]]
        
        if self.predictions is not None and self.current_step < len(self.predictions):
            if abs(current_price) > 1e-8:
                pred_diff = (self.predictions[self.current_step] - current_price) / current_price
                pred_diff = np.clip(pred_diff, -1, 1)  # Clip to [-1, 1]
            else:
                pred_diff = 0.0
            obs_parts.append([pred_diff])
        
        if self.sentiment_scores is not None and self.current_step < len(self.sentiment_scores):
            obs_parts.append([np.clip(self.sentiment_scores[self.current_step], -1, 1)])
        
        obs = np.concatenate(obs_parts).astype(np.float32)
        
        return obs
    
    def render(self, mode='human'):
        """Render environment state."""
        current_price = self.price_data[self.current_step, self.close_idx]
        total_value = self.balance + self.position * current_price
        profit = total_value - self.initial_capital
        
        print(f"Step: {self.current_step} | "
              f"Price: ${current_price:.2f} | "
              f"Balance: ${self.balance:.2f} | "
              f"Position: {self.position:.4f} | "
              f"Profit: ${profit:.2f} ({profit/self.initial_capital*100:.2f}%)")


class ActorCriticNetwork(nn.Module):
    """
    Actor-Critic network for PPO algorithm.
    """
    
    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int = 128):
        """
        Initialize actor-critic network.
        
        Args:
            input_dim: Input state dimension
            output_dim: Output action dimension
            hidden_dim: Hidden layer dimension
        """
        super(ActorCriticNetwork, self).__init__()
        
        # Shared layers with proper initialization
        self.shared = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),  # Tanh for better stability
            nn.LayerNorm(hidden_dim),  # Layer normalization
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.LayerNorm(hidden_dim)
        )
        
        # Actor head (policy)
        self.actor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.Softmax(dim=-1)
        )
        
        # Critic head (value function)
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize network weights for stability."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight, gain=nn.init.calculate_gain('tanh'))
                nn.init.constant_(module.bias, 0.0)
    
    def forward(self, state):
        """Forward pass through network."""
        x = self.shared(state)
        
        policy = self.actor(x)
        value = self.critic(x)
        
        return policy, value


class PPOAgent:
    """
    PPO (Proximal Policy Optimization) agent for trading.
    """
    
    def __init__(self, state_dim: int, action_dim: int = 3, 
                 learning_rate: float = PPO_LEARNING_RATE,
                 gamma: float = PPO_GAMMA,
                 gae_lambda: float = 0.95,
                 clip_epsilon: float = 0.2,
                 n_epochs: int = 10,
                 batch_size: int = PPO_BATCH_SIZE,
                 device: str = None):
        """
        Initialize PPO agent.
        
        Args:
            state_dim: State space dimension
            action_dim: Action space dimension
            learning_rate: Learning rate
            gamma: Discount factor
            gae_lambda: GAE lambda parameter
            clip_epsilon: PPO clip parameter
            n_epochs: Number of PPO epochs per update
            batch_size: Mini-batch size
            device: Device for training
        """
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.n_epochs = n_epochs
        self.batch_size = batch_size
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        # Create network
        self.network = ActorCriticNetwork(state_dim, action_dim)
        self.network.to(self.device)
        
        # Optimizer
        self.optimizer = optim.Adam(self.network.parameters(), lr=learning_rate)
        
        # Loss functions
        self.value_loss_fn = nn.MSELoss()
        
        # Memory for storing transitions
        self.memory = {
            'states': [],
            'actions': [],
            'rewards': [],
            'values': [],
            'log_probs': [],
            'dones': []
        }
    
    def select_action(self, state: np.ndarray, deterministic: bool = False) -> Tuple[int, float]:
        """
        Select action based on policy.
        
        Args:
            state: Current state
            deterministic: Whether to use deterministic policy
        
        Returns:
            Tuple of (action, log probability)
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            policy, _ = self.network(state_tensor)
        
        if deterministic:
            action = torch.argmax(policy, dim=-1).item()
            log_prob = torch.log(policy[0, action])
        else:
            dist = Categorical(policy)
            action = dist.sample().item()
            log_prob = dist.log_prob(torch.tensor(action))
        
        return action, log_prob.item()
    
    def store_transition(self, state: np.ndarray, action: int, reward: float,
                        value: float, log_prob: float, done: bool):
        """Store transition in memory."""
        self.memory['states'].append(state)
        self.memory['actions'].append(action)
        self.memory['rewards'].append(reward)
        self.memory['values'].append(value)
        self.memory['log_probs'].append(log_prob)
        self.memory['dones'].append(done)
    
    def clear_memory(self):
        """Clear stored transitions."""
        for key in self.memory:
            self.memory[key] = []
    
    def compute_returns_and_advantages(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute returns and advantages using GAE."""
        rewards = np.array(self.memory['rewards'])
        values = np.array(self.memory['values'])
        dones = np.array(self.memory['dones'])
        
        # Compute returns
        returns = np.zeros_like(rewards)
        running_return = 0
        
        for t in reversed(range(len(rewards))):
            running_return = rewards[t] + self.gamma * running_return * (1 - dones[t])
            returns[t] = running_return
        
        # Compute advantages using GAE
        advantages = np.zeros_like(rewards)
        running_advantage = 0
        
        for t in reversed(range(len(rewards))):
            delta = rewards[t] + self.gamma * values[t + 1] * (1 - dones[t]) - values[t] \
                   if t < len(rewards) - 1 else rewards[t] - values[t]
            running_advantage = delta + self.gamma * self.gae_lambda * running_advantage * (1 - dones[t])
            advantages[t] = running_advantage
        
        # Normalize advantages
        std = advantages.std()
        if std > 1e-8 and not np.isnan(std):
            advantages = (advantages - advantages.mean()) / (std + 1e-8)
        else:
            advantages = np.zeros_like(advantages)  # Reset if invalid
        
        return returns, advantages
    
    def update(self):
        """Update policy and value networks."""
        if len(self.memory['states']) == 0:
            return
        
        # Compute returns and advantages
        returns, advantages = self.compute_returns_and_advantages()
        
        # Check for NaN values
        if np.any(np.isnan(advantages)) or np.any(np.isnan(returns)):
            print("Warning: NaN detected in advantages/returns, skipping update")
            self.clear_memory()
            return
        
        # Convert to tensors
        states = torch.FloatTensor(np.array(self.memory['states'])).to(self.device)
        actions = torch.LongTensor(self.memory['actions']).to(self.device)
        returns_tensor = torch.FloatTensor(returns).to(self.device)
        advantages_tensor = torch.FloatTensor(advantages).to(self.device)
        old_log_probs = torch.FloatTensor(self.memory['log_probs']).to(self.device)
        
        # Training loop
        dataset_size = len(states)
        
        for epoch in range(self.n_epochs):
            # Shuffle data
            indices = np.random.permutation(dataset_size)
            
            for start in range(0, dataset_size, self.batch_size):
                end = start + self.batch_size
                batch_indices = indices[start:end]
                
                # Get batch
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_returns = returns_tensor[batch_indices]
                batch_advantages = advantages_tensor[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                
                # Forward pass
                policy, values = self.network(batch_states)
                
                # Get new log probs
                dist = Categorical(policy)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy().mean()
                
                # Compute importance weights
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                
                # PPO clipped surrogate loss
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = self.value_loss_fn(values.squeeze(), batch_returns)
                
                # Total loss with entropy bonus for exploration
                loss = policy_loss + 0.5 * value_loss - 0.02 * entropy
                
                # Skip update if loss is NaN
                if torch.isnan(loss):
                    continue
                
                # Update network
                self.optimizer.zero_grad()
                loss.backward()
                
                # Extra gradient clipping
                nn.utils.clip_grad_norm_(self.network.parameters(), max_norm=1.0)
                self.optimizer.step()
        
        self.clear_memory()
    
    def save_model(self, path: str):
        """Save model to file."""
        torch.save({
            'network_state_dict': self.network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
        }, path)
        print(f"✓ PPO model saved to {path}")
    
    def load_model(self, path: str):
        """Load model from file."""
        checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint['network_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        print(f"✓ PPO model loaded from {path}")


def train_ppo_agent(env: GoldTradingEnv, agent: PPOAgent, 
                   n_episodes: int = 1000, render_every: int = 100) -> List[float]:
    """
    Train PPO agent in trading environment.
    
    Args:
        env: Trading environment
        agent: PPO agent
        n_episodes: Number of training episodes
        render_every: Render every N episodes
    
    Returns:
        List of episode rewards
    """
    print(f"\nTraining PPO agent for {n_episodes} episodes...")
    print(f"Device: {agent.device}")
    print("-" * 60)
    
    episode_rewards = []
    best_reward = -float('inf')
    
    for episode in range(n_episodes):
        state, _ = env.reset()
        episode_reward = 0
        done = False
        truncated = False
        
        while not (done or truncated):
            # Select action
            action, log_prob = agent.select_action(state, deterministic=False)
            
            # Get value estimate
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
            with torch.no_grad():
                _, value = agent.network(state_tensor)
            value = value.squeeze().item()
            
            # Take step
            next_state, reward, done, truncated, info = env.step(action)
            
            # Store transition
            agent.store_transition(state, action, reward, value, log_prob, done)
            
            state = next_state
            episode_reward += reward
        
        # Update agent after each episode
        agent.update()
        
        episode_rewards.append(episode_reward)
        
        # Progress logging
        if (episode + 1) % render_every == 0:
            avg_reward = np.mean(episode_rewards[-render_every:])
            print(f"Episode {episode+1}/{n_episodes} | "
                  f"Avg Reward: {avg_reward:.2f} | "
                  f"Best: {best_reward:.2f}")
            
            # Save best model
            if avg_reward > best_reward:
                best_reward = avg_reward
    
    print("-" * 60)
    print(f"Training complete! Best avg reward: {best_reward:.2f}")
    
    return episode_rewards


if __name__ == "__main__":
    # Test PPO agent
    print("=" * 60)
    print("Testing PPO Trading Agent")
    print("=" * 60)
    
    # Create sample data
    np.random.seed(42)
    n_days = 200
    prices = np.cumsum(np.random.randn(n_days)) + 100
    
    price_data = np.column_stack([
        prices * 0.99,  # Open
        prices * 1.02,  # High
        prices * 0.98,  # Low
        prices,         # Close
        np.random.randint(1000, 5000, n_days),  # Volume
    ])
    
    # Create environment
    env = GoldTradingEnv(price_data)
    
    # Create agent
    agent = PPOAgent(state_dim=env.state_size)
    
    # Train
    rewards = train_ppo_agent(env, agent, n_episodes=500, render_every=50)
    
    # Plot results
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(12, 5))
    plt.plot(rewards)
    plt.xlabel('Episode')
    plt.ylabel('Episode Reward')
    plt.title('PPO Training Rewards')
    plt.grid(True)
    plt.tight_layout()
    plt.show()
