"""
Training script for LSTM gold price prediction model.
Handles data loading, preprocessing, training, and evaluation.
"""

import torch
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

from data.data_pipeline import (
    load_or_fetch_data, 
    preprocess_data, 
    prepare_lstm_features,
    create_sequences,
    save_processed_data
)
from models.lstm_model import LSTMModel, LSTMTrainer, create_lstm_model
from utils.config import (
    LSTM_SEQUENCE_LENGTH, 
    LSTM_HIDDEN_SIZE, 
    LSTM_NUM_LAYERS,
    DROPOUT_RATE,
    LSTM_MODEL_PATH,
    DATA_DIR
)


def prepare_training_data(df: pd.DataFrame, sequence_length: int = LSTM_SEQUENCE_LENGTH,
                          train_ratio: float = 0.7, val_ratio: float = 0.15):
    """
    Prepare data for LSTM training.
    
    Args:
        df: Preprocessed DataFrame
        sequence_length: Length of input sequences
        train_ratio: Ratio of data for training
        val_ratio: Ratio of data for validation
    
    Returns:
        Tuple of (train_loader, val_loader, test_loader, scaler_params)
    """
    print("\nPreparing training data...")
    
    # Prepare features
    features, feature_columns, scaler_params = prepare_lstm_features(df)
    
    # Target: next day's close price (index 3 in features)
    target = features[:, 3]  # Close price column
    
    # Create sequences
    X, y = create_sequences(features, target, sequence_length)
    
    print(f"Total sequences: {len(X)}")
    print(f"Sequence shape: {X.shape}")
    
    # Split data
    n_samples = len(X)
    train_size = int(n_samples * train_ratio)
    val_size = int(n_samples * val_ratio)
    test_size = n_samples - train_size - val_size
    
    X_train, X_val, X_test = np.split(X, [train_size, train_size + val_size])
    y_train, y_val, y_test = np.split(y, [train_size, train_size + val_size])
    
    print(f"\nData split:")
    print(f"  Training: {len(X_train)} samples ({len(X_train)/n_samples*100:.1f}%)")
    print(f"  Validation: {len(X_val)} samples ({len(X_val)/n_samples*100:.1f}%)")
    print(f"  Test: {len(X_test)} samples ({len(X_test)/n_samples*100:.1f}%)")
    
    # Convert to tensors
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.FloatTensor(y_train)
    X_val_tensor = torch.FloatTensor(X_val)
    y_val_tensor = torch.FloatTensor(y_val)
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.FloatTensor(y_test)
    
    # Create datasets
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
    test_dataset = TensorDataset(X_test_tensor, y_test_tensor)
    
    # Create dataloaders
    batch_size = 32
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader, test_loader, scaler_params


def plot_training_history(history: dict, save_path: str = None):
    """
    Plot training history.
    
    Args:
        history: Training history dictionary
        save_path: Path to save plot (optional)
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot loss
    axes[0].plot(history['train_loss'], label='Train Loss')
    if 'val_loss' in history and history['val_loss']:
        axes[0].plot(history['val_loss'], label='Val Loss')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('MSE Loss')
    axes[0].set_title('Training and Validation Loss')
    axes[0].legend()
    axes[0].grid(True)
    
    # Plot RMSE
    if 'val_rmse' in history and history['val_rmse']:
        axes[1].plot(history['val_rmse'], label='Validation RMSE', color='orange')
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel('RMSE')
        axes[1].set_title('Validation RMSE')
        axes[1].legend()
        axes[1].grid(True)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✓ Training history plot saved to {save_path}")
    
    plt.show()


def plot_predictions(model: LSTMModel, test_loader: DataLoader, 
                     scaler_params: dict, device: torch.device,
                     sample_indices: list = None):
    """
    Plot actual vs predicted prices.
    
    Args:
        model: Trained model
        test_loader: Test data loader
        scaler_params: Scaler parameters for denormalization
        device: Device for inference
        sample_indices: Indices to plot (default: random 100 samples)
    """
    model.eval()
    
    all_predictions = []
    all_targets = []
    
    with torch.no_grad():
        for batch_X, batch_y in test_loader:
            batch_X = batch_X.to(device)
            predictions = model(batch_X)
            
            all_predictions.extend(predictions.cpu().numpy())
            all_targets.extend(batch_y.numpy())
    
    all_predictions = np.array(all_predictions).flatten()
    all_targets = np.array(all_targets).flatten()
    
    # Denormalize
    close_min = scaler_params['min'][3]
    close_range = scaler_params['range'][3]
    
    all_predictions_denorm = all_predictions * close_range + close_min
    all_targets_denorm = all_targets * close_range + close_min
    
    # Sample indices
    if sample_indices is None:
        sample_indices = np.random.choice(len(all_predictions), min(100, len(all_predictions)), replace=False)
    
    # Plot
    plt.figure(figsize=(14, 6))
    plt.plot(sample_indices, all_targets_denorm[sample_indices], 'b-', label='Actual Price', alpha=0.7)
    plt.plot(sample_indices, all_predictions_denorm[sample_indices], 'r--', label='Predicted Price', alpha=0.7)
    plt.xlabel('Sample Index')
    plt.ylabel('Price ($)')
    plt.title('Actual vs Predicted Gold Prices')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    save_path = DATA_DIR / "predictions_plot.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✓ Predictions plot saved to {save_path}")
    
    plt.show()
    
    # Calculate error statistics
    errors = np.abs(all_predictions_denorm - all_targets_denorm)
    print(f"\nPrediction Error Statistics:")
    print(f"  Mean Error: ${np.mean(errors):.2f}")
    print(f"  Median Error: ${np.median(errors):.2f}")
    print(f"  Max Error: ${np.max(errors):.2f}")
    print(f"  Min Error: ${np.min(errors):.2f}")


def train_lstm_model(data_df: pd.DataFrame = None, epochs: int = 100,
                     early_stopping_patience: int = 15, use_pretrained: bool = False):
    """
    Main training function for LSTM model.
    
    Args:
        data_df: Preprocessed DataFrame (optional, loads from file if None)
        epochs: Number of training epochs
        early_stopping_patience: Early stopping patience
        use_pretrained: Whether to use pretrained model
    """
    print("=" * 60)
    print("LSTM Model Training")
    print("=" * 60)
    
    # Load data if not provided
    if data_df is None:
        print("\nLoading data...")
        raw_df = load_or_fetch_data()
        
        if raw_df.empty:
            print("✗ No data available. Exiting.")
            return None
        
        data_df = preprocess_data(raw_df)
        save_processed_data(data_df)
    
    print(f"\nDataset shape: {data_df.shape}")
    print(f"Date range: {data_df.index.min()} to {data_df.index.max()}")
    
    # Prepare training data
    train_loader, val_loader, test_loader, scaler_params = prepare_training_data(data_df)
    
    # Create model
    input_size = train_loader.dataset.tensors[0].shape[2]
    print(f"\nInput size: {input_size} features")
    
    model = LSTMModel(
        input_size=input_size,
        hidden_size=LSTM_HIDDEN_SIZE,
        num_layers=LSTM_NUM_LAYERS,
        dropout=DROPOUT_RATE
    )
    
    print(f"\nModel architecture:")
    print(model)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nTotal parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    # Initialize trainer
    trainer = LSTMTrainer(
        model=model,
        learning_rate=0.001,
        device=None  # Auto-detect
    )
    
    # Train model
    history = trainer.fit(
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=epochs,
        early_stopping_patience=early_stopping_patience,
        save_best=True,
        model_path=str(LSTM_MODEL_PATH)
    )
    
    # Evaluate on test set
    print("\n" + "=" * 60)
    print("Evaluating on Test Set")
    print("=" * 60)
    
    metrics = trainer.evaluate(test_loader, feature_std=scaler_params['range'][3])
    
    # Plot training history
    plot_training_history(history, save_path=str(DATA_DIR / "training_history.png"))
    
    # Plot predictions
    plot_predictions(model, test_loader, scaler_params, trainer.device)
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"✓ Model saved to: {LSTM_MODEL_PATH}")
    
    return trainer


if __name__ == "__main__":
    # Run training
    trainer = train_lstm_model(epochs=100, early_stopping_patience=15)
