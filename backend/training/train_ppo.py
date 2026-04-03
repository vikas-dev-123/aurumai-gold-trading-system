"""
Training script for PPO trading agent.
Handles environment setup, training loop, and model saving.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from data.data_pipeline import load_or_fetch_data, preprocess_data, prepare_lstm_features
from models.ppo_agent import GoldTradingEnv, PPOAgent, train_ppo_agent
from models.lstm_model import create_lstm_model, predict_price
from utils.config import PPO_MODEL_PATH, DATA_DIR, LSTM_MODEL_PATH


def prepare_trading_data(df):
    """
    Prepare data for PPO training.
    
    Args:
        df: Preprocessed DataFrame
    
    Returns:
        Tuple of (price_data, predictions, sentiment_scores)
    """
    print("\nPreparing trading data for PPO...")
    
    # Extract features
    features, feature_columns, scaler_params = prepare_lstm_features(df)
    
    # Use close price as primary feature
    close_prices = features[:, 3:4]  # Keep as 2D array
    
    # Generate mock predictions (in production, use actual LSTM predictions)
    predictions = close_prices.flatten() + np.random.randn(len(close_prices)) * 2
    
    # Generate mock sentiment scores
    sentiment_scores = np.random.uniform(-0.5, 0.5, len(close_prices))
    
    # Remove the last column if we have 14 features to match the expected 13
    # This ensures compatibility with the environment's state space
    if features.shape[1] > 13:
        features = features[:, :13]
    
    return features, predictions, sentiment_scores


def plot_trading_results(env: GoldTradingEnv, rewards_history: list, save_path: str = None):
    """
    Plot PPO trading results.
    
    Args:
        env: Trading environment
        rewards_history: List of episode rewards
        save_path: Path to save plot
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Plot rewards
    axes[0].plot(rewards_history)
    
    # Add moving average
    window = 50
    if len(rewards_history) >= window:
        moving_avg = np.convolve(rewards_history, np.ones(window)/window, mode='valid')
        axes[0].plot(range(window-1, len(rewards_history)), moving_avg, 'r-', linewidth=2)
        axes[0].legend(['Raw Rewards', f'{window}-Episode MA'])
    
    axes[0].set_xlabel('Episode')
    axes[0].set_ylabel('Reward')
    axes[0].set_title('PPO Training Progress')
    axes[0].grid(True)
    
    # Plot final episode trades
    prices = env.price_data[:, 3]  # Close prices
    
    axes[1].plot(prices, label='Gold Price')
    
    # Mark buy/sell points
    for trade in env.trades[-20:]:  # Last 20 trades
        idx = env.current_step - len(env.trades) + env.trades.index(trade)
        if idx < 0 or idx >= len(prices):
            continue
        
        if trade['type'] == 'buy':
            axes[1].scatter(idx, trade['price'], c='green', marker='^', s=100, zorder=5)
        else:
            axes[1].scatter(idx, trade['price'], c='red', marker='v', s=100, zorder=5)
    
    axes[1].set_xlabel('Time Step')
    axes[1].set_ylabel('Price ($)')
    axes[1].set_title('Trading Signals')
    axes[1].legend(['Price', 'Buy', 'Sell'])
    axes[1].grid(True)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✓ Trading results plot saved to {save_path}")
    
    plt.show()


def train_ppo_trader(n_episodes: int = 1000, use_lstm_predictions: bool = True):
    """
    Main function to train PPO trading agent.
    
    Args:
        n_episodes: Number of training episodes
        use_lstm_predictions: Whether to use LSTM predictions as input
    """
    print("=" * 60)
    print("PPO Trading Agent Training")
    print("=" * 60)
    
    # Load and prepare data
    print("\nLoading data...")
    raw_df = load_or_fetch_data()
    
    if raw_df.empty:
        print("✗ No data available. Exiting.")
        return None
    
    df = preprocess_data(raw_df)
    price_data, predictions, sentiment_scores = prepare_trading_data(df)
    
    print(f"Data shape: {price_data.shape}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    # Create environment
    env = GoldTradingEnv(
        price_data=price_data,
        predictions=predictions,
        sentiment_scores=sentiment_scores,
        max_steps=len(price_data) - 1
    )
    
    print(f"\nEnvironment state size: {env.state_size}")
    
    # Create PPO agent with the exact state dimension from environment
    agent = PPOAgent(
        state_dim=env.state_size,
        action_dim=3,  # HOLD, BUY, SELL
        learning_rate=0.0001,  # Reduced for stability
        gamma=0.99,
        n_epochs=5,  # Reduced epochs per update
        batch_size=32  # Smaller batch size
    )
    
    print(f"\nPPO Agent Architecture:")
    print(agent.network)
    
    # Count parameters
    total_params = sum(p.numel() for p in agent.network.parameters())
    trainable_params = sum(p.numel() for p in agent.network.parameters() if p.requires_grad)
    print(f"\nTotal parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    # Train agent
    rewards_history = train_ppo_agent(
        env=env,
        agent=agent,
        n_episodes=n_episodes,
        render_every=50
    )
    
    # Save model
    agent.save_model(str(PPO_MODEL_PATH))
    
    # Plot results
    plot_trading_results(
        env=env,
        rewards_history=rewards_history,
        save_path=str(DATA_DIR / "ppo_training_results.png")
    )
    
    print("\n" + "=" * 60)
    print("PPO Training Complete!")
    print("=" * 60)
    print(f"✓ Model saved to: {PPO_MODEL_PATH}")
    
    return agent, rewards_history


if __name__ == "__main__":
    # Train PPO agent
    agent, rewards = train_ppo_trader(n_episodes=1000)
