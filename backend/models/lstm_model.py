"""
LSTM (Long Short-Term Memory) model for gold price prediction.
Uses PyTorch to build, train, and evaluate the neural network.
"""

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from utils.config import LSTM_HIDDEN_SIZE, LSTM_NUM_LAYERS, DROPOUT_RATE


class LSTMModel(nn.Module):
    """
    LSTM Neural Network for time series prediction.
    
    Architecture:
    - Input layer: Accepts sequences of features
    - LSTM layers: 2 or more stacked LSTM layers
    - Dropout: Prevents overfitting
    - Fully connected: Output layer for price prediction
    """
    
    def __init__(self, input_size: int = 14, hidden_size: int = LSTM_HIDDEN_SIZE,
                 num_layers: int = LSTM_NUM_LAYERS, output_size: int = 1, 
                 dropout: float = DROPOUT_RATE):
        """
        Initialize LSTM model.
        
        Args:
            input_size: Number of input features
            hidden_size: Number of neurons in LSTM layers
            num_layers: Number of stacked LSTM layers
            output_size: Number of output predictions
            dropout: Dropout rate for regularization
        """
        super(LSTMModel, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        # Dropout layer
        self.dropout = nn.Dropout(dropout)
        
        # Fully connected layers
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size // 2, output_size)
    
    def forward(self, x):
        """
        Forward pass through the network.
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
        
        Returns:
            Output tensor of shape (batch_size, output_size)
        """
        # Initialize hidden state and cell state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # LSTM forward pass
        lstm_out, _ = self.lstm(x, (h0, c0))
        
        # Take only the last time step output
        last_output = lstm_out[:, -1, :]
        
        # Apply dropout
        dropped = self.dropout(last_output)
        
        # Fully connected layers
        out = self.fc1(dropped)
        out = self.relu(out)
        out = self.fc2(out)
        
        return out
    
    def predict_step(self, batch):
        """
        Prediction step for inference.
        
        Args:
            batch: Input batch
        
        Returns:
            Model predictions
        """
        with torch.no_grad():
            predictions = self(batch)
        return predictions


class LSTMTrainer:
    """
    Trainer class for LSTM model.
    Handles training loop, validation, and model saving.
    """
    
    def __init__(self, model: LSTMModel, learning_rate: float = 0.001,
                 device: str = None):
        """
        Initialize trainer.
        
        Args:
            model: LSTM model to train
            learning_rate: Learning rate for optimizer
            device: Device to use ('cuda' or 'cpu')
        """
        self.model = model
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.model.to(self.device)
        
        # Loss function and optimizer
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        
        # Learning rate scheduler
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5, verbose=True
        )
        
        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_rmse': [],
            'val_rmse': []
        }
    
    def train_epoch(self, train_loader):
        """
        Train for one epoch.
        
        Args:
            train_loader: DataLoader for training data
        
        Returns:
            Average loss for the epoch
        """
        self.model.train()
        total_loss = 0
        
        for batch_X, batch_y in train_loader:
            batch_X = batch_X.to(self.device)
            batch_y = batch_y.to(self.device).view(-1, 1)
            
            # Forward pass
            self.optimizer.zero_grad()
            predictions = self.model(batch_X)
            
            # Calculate loss
            loss = self.criterion(predictions, batch_y)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping to prevent exploding gradients
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            # Update weights
            self.optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_loader)
        return avg_loss
    
    def validate(self, val_loader):
        """
        Validate the model.
        
        Args:
            val_loader: DataLoader for validation data
        
        Returns:
            Tuple of (average loss, RMSE)
        """
        self.model.eval()
        total_loss = 0
        all_predictions = []
        all_targets = []
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device).view(-1, 1)
                
                predictions = self.model(batch_X)
                
                loss = self.criterion(predictions, batch_y)
                total_loss += loss.item()
                
                all_predictions.extend(predictions.cpu().numpy())
                all_targets.extend(batch_y.cpu().numpy())
        
        avg_loss = total_loss / len(val_loader)
        
        # Calculate RMSE
        all_predictions = np.array(all_predictions).flatten()
        all_targets = np.array(all_targets).flatten()
        rmse = np.sqrt(np.mean((all_predictions - all_targets) ** 2))
        
        return avg_loss, rmse
    
    def fit(self, train_loader, val_loader=None, epochs: int = 100,
            early_stopping_patience: int = 10, save_best: bool = True,
            model_path: str = None):
        """
        Train the model for multiple epochs.
        
        Args:
            train_loader: DataLoader for training data
            val_loader: DataLoader for validation data (optional)
            epochs: Number of training epochs
            early_stopping_patience: Epochs to wait before early stopping
            save_best: Whether to save best model
            model_path: Path to save model
        
        Returns:
            Training history dictionary
        """
        best_val_loss = float('inf')
        patience_counter = 0
        
        print(f"Training on device: {self.device}")
        print(f"Starting training for {epochs} epochs...")
        print("-" * 60)
        
        for epoch in range(epochs):
            # Training
            train_loss = self.train_epoch(train_loader)
            
            # Validation
            if val_loader:
                val_loss, val_rmse = self.validate(val_loader)
                
                # Update learning rate
                self.scheduler.step(val_loss)
                
                # Save best model
                if save_best and val_loss < best_val_loss:
                    best_val_loss = val_loss
                    if model_path:
                        self.save_model(model_path)
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                # Print progress
                print(f"Epoch [{epoch+1}/{epochs}] "
                      f"Train Loss: {train_loss:.6f} | "
                      f"Val Loss: {val_loss:.6f} | "
                      f"Val RMSE: {val_rmse:.4f}")
                
                # Store history
                self.history['train_loss'].append(train_loss)
                self.history['val_loss'].append(val_loss)
                self.history['val_rmse'].append(val_rmse)
                
                # Early stopping
                if patience_counter >= early_stopping_patience:
                    print(f"\nEarly stopping at epoch {epoch+1}")
                    break
            else:
                print(f"Epoch [{epoch+1}/{epochs}] Train Loss: {train_loss:.6f}")
                self.history['train_loss'].append(train_loss)
        
        print("-" * 60)
        print("Training completed!")
        
        return self.history
    
    def evaluate(self, test_loader, feature_std: float = 1.0):
        """
        Evaluate model on test data.
        
        Args:
            test_loader: DataLoader for test data
            feature_std: Standard deviation for denormalization
        
        Returns:
            Dictionary with evaluation metrics
        """
        self.model.eval()
        all_predictions = []
        all_targets = []
        
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                batch_X = batch_X.to(self.device)
                predictions = self.model(batch_X)
                
                all_predictions.extend(predictions.cpu().numpy())
                all_targets.extend(batch_y.numpy())
        
        all_predictions = np.array(all_predictions).flatten()
        all_targets = np.array(all_targets).flatten()
        
        # Denormalize if needed
        all_predictions = all_predictions * feature_std
        all_targets = all_targets * feature_std
        
        # Calculate metrics
        mse = np.mean((all_predictions - all_targets) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(all_predictions - all_targets))
        mape = np.mean(np.abs((all_targets - all_predictions) / all_targets)) * 100
        
        metrics = {
            'MSE': mse,
            'RMSE': rmse,
            'MAE': mae,
            'MAPE': mape
        }
        
        print("\nEvaluation Metrics:")
        print(f"  RMSE: {rmse:.4f}")
        print(f"  MAE: {mae:.4f}")
        print(f"  MAPE: {mape:.2f}%")
        
        return metrics
    
    def save_model(self, path: str):
        """
        Save model to file.
        
        Args:
            path: File path to save model
        """
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'history': self.history,
        }, path)
        print(f"✓ Model saved to {path}")
    
    def load_model(self, path: str):
        """
        Load model from file.
        
        Args:
            path: File path to load model from
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.history = checkpoint.get('history', {})
        print(f"✓ Model loaded from {path}")


def create_lstm_model(input_size: int = 14, pretrained: bool = False,
                      model_path: str = None) -> tuple:
    """
    Create and optionally load an LSTM model.
    
    Args:
        input_size: Number of input features
        pretrained: Whether to load pretrained weights
        model_path: Path to pretrained model
    
    Returns:
        Tuple of (model, device)
    """
    # Create model
    model = LSTMModel(input_size=input_size)
    
    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    # Load pretrained weights
    if pretrained and model_path:
        trainer = LSTMTrainer(model, device=device)
        trainer.load_model(model_path)
    
    return model, device


def predict_price(model: LSTMModel, sequence: np.ndarray, device: torch.device) -> float:
    """
    Predict next day's price using trained model.
    
    Args:
        model: Trained LSTM model
        sequence: Input sequence of shape (sequence_length, input_size)
        device: Device to use for inference
    
    Returns:
        Predicted price
    """
    model.eval()
    
    # Prepare input
    if len(sequence.shape) == 2:
        sequence = sequence.unsqueeze(0)  # Add batch dimension
    
    sequence = sequence.to(device)
    
    # Make prediction
    with torch.no_grad():
        prediction = model(sequence)
    
    return prediction.cpu().numpy().flatten()[0]
