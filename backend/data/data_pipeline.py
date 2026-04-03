"""
Data pipeline for fetching and preprocessing gold price data.
Uses yfinance to fetch historical data and applies technical indicators.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from utils.indicators import add_technical_indicators
from utils.config import SAMPLE_DATA_PATH, DATA_DIR


def fetch_gold_data(symbol: str = "GLD", period: str = "max", 
                    start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Fetch historical gold price data from Yahoo Finance.
    
    Args:
        symbol: ETF symbol (default: GLD - SPDR Gold Shares)
        period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
        start_date: Start date string (YYYY-MM-DD), overrides period if provided
        end_date: End date string (YYYY-MM-DD)
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        ticker = yf.Ticker(symbol)
        
        if start_date:
            df = ticker.history(start=start_date, end=end_date)
        else:
            df = ticker.history(period=period)
        
        if df.empty:
            print(f"⚠ No data retrieved for {symbol}")
            return pd.DataFrame()
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Reset index to have Date as column
        df = df.reset_index()
        
        # Ensure Date is datetime type
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        
        print(f"✓ Fetched {len(df)} records for {symbol}")
        return df
        
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        return pd.DataFrame()


def create_sample_dataset() -> pd.DataFrame:
    """
    Create a sample dataset for testing when API is unavailable.
    Generates realistic gold price data based on historical patterns.
    
    Returns:
        DataFrame with synthetic gold price data
    """
    print("⚠ Creating sample dataset...")
    
    # Generate 2 years of daily data
    dates = pd.date_range(end=datetime.now(), periods=730, freq='D')
    
    # Starting price around $1800
    base_price = 1800
    
    # Generate realistic price movements
    np.random.seed(42)
    
    # Daily returns with slight upward bias and realistic volatility
    daily_returns = np.random.normal(0.0003, 0.015, len(dates))
    
    # Calculate cumulative returns and prices
    cumulative_returns = (1 + daily_returns).cumprod()
    close_prices = base_price * cumulative_returns
    
    # Generate other OHLC columns based on close
    open_prices = close_prices * (1 + np.random.uniform(-0.005, 0.005, len(dates)))
    high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.uniform(0, 0.02, len(dates))))
    low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.uniform(0, 0.02, len(dates))))
    
    # Volume (random with some pattern)
    volume = np.random.randint(5000000, 15000000, len(dates))
    
    # Create DataFrame
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume
    }, index=dates)
    
    df.index.name = 'Date'
    
    # Save to CSV
    df.to_csv(SAMPLE_DATA_PATH)
    print(f"✓ Sample dataset saved to {SAMPLE_DATA_PATH}")
    
    return df


def load_or_fetch_data(use_sample: bool = False) -> pd.DataFrame:
    """
    Load data from sample file or fetch from Yahoo Finance.
    
    Args:
        use_sample: Force use of sample data even if API works
    
    Returns:
        DataFrame with price data
    """
    # Try to fetch real data first
    if not use_sample:
        df = fetch_gold_data(period="max")
        
        if not df.empty:
            return df
    
    # Check if sample data exists
    if SAMPLE_DATA_PATH.exists():
        print(f"✓ Loading sample data from {SAMPLE_DATA_PATH}")
        df = pd.read_csv(SAMPLE_DATA_PATH, index_col='Date', parse_dates=True)
        return df
    
    # Create new sample data
    return create_sample_dataset()


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess price data and add technical indicators.
    
    Args:
        df: Raw price DataFrame
    
    Returns:
        DataFrame with technical indicators added
    """
    if df.empty:
        return df
    
    # Make a copy
    df_processed = df.copy()
    
    # Add technical indicators
    df_processed = add_technical_indicators(df_processed)
    
    # Drop rows with NaN values (from indicator calculations)
    df_processed = df_processed.dropna()
    
    print(f"✓ Preprocessed data: {len(df_processed)} records")
    
    return df_processed


def prepare_lstm_features(df: pd.DataFrame) -> tuple:
    """
    Prepare features for LSTM model training.
    
    Args:
        df: Preprocessed DataFrame with indicators
    
    Returns:
        Tuple of (feature_array, feature_columns, scaler_params)
    """
    # Select features for LSTM
    feature_columns = [
        'Open', 'High', 'Low', 'Close', 'Volume',
        'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26',
        'RSI', 'MACD', 'BB_Upper', 'BB_Lower', 'Volatility'
    ]
    
    # Filter available columns
    available_features = [col for col in feature_columns if col in df.columns]
    
    # Extract features
    features = df[available_features].values
    
    # Normalize features (min-max scaling)
    feature_min = features.min(axis=0)
    feature_max = features.max(axis=0)
    feature_range = feature_max - feature_min
    
    # Avoid division by zero
    feature_range[feature_range == 0] = 1
    
    normalized_features = (features - feature_min) / feature_range
    
    scaler_params = {
        'min': feature_min,
        'max': feature_max,
        'range': feature_range,
        'columns': available_features
    }
    
    return normalized_features, available_features, scaler_params


def create_sequences(data: np.ndarray, target: np.ndarray = None, 
                     sequence_length: int = 60, prediction_horizon: int = 1) -> tuple:
    """
    Create sequences for LSTM training.
    
    Args:
        data: Input feature array
        target: Target values (optional, uses next close price if None)
        sequence_length: Length of input sequences
        prediction_horizon: Number of steps ahead to predict
    
    Returns:
        Tuple of (X, y) sequences
    """
    X, y = [], []
    
    for i in range(len(data) - sequence_length - prediction_horizon + 1):
        X.append(data[i:i + sequence_length])
        
        if target is not None:
            y.append(target[i + sequence_length + prediction_horizon - 1])
        else:
            # Default: predict next day's return
            y.append(data[i + sequence_length + prediction_horizon - 1, 3])  # Close price index
    
    return np.array(X), np.array(y)


def save_processed_data(df: pd.DataFrame, filename: str = "processed_gold_data.csv"):
    """
    Save processed data to CSV.
    
    Args:
        df: Processed DataFrame
        filename: Output filename
    """
    output_path = DATA_DIR / filename
    df.to_csv(output_path)
    print(f"✓ Saved processed data to {output_path}")


def load_processed_data(filename: str = "processed_gold_data.csv") -> pd.DataFrame:
    """
    Load processed data from CSV.
    
    Args:
        filename: Input filename
    
    Returns:
        DataFrame with processed data
    """
    file_path = DATA_DIR / filename
    
    if not file_path.exists():
        print(f"⚠ File not found: {file_path}")
        return pd.DataFrame()
    
    df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
    print(f"✓ Loaded processed data from {file_path}")
    
    return df


# Main execution for testing
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Data Pipeline")
    print("=" * 60)
    
    # Fetch or load data
    df = load_or_fetch_data(use_sample=False)
    
    if not df.empty:
        # Preprocess
        df_processed = preprocess_data(df)
        
        # Display info
        print(f"\nDataset shape: {df_processed.shape}")
        print(f"\nColumns: {df_processed.columns.tolist()}")
        print(f"\nDate range: {df_processed.index.min()} to {df_processed.index.max()}")
        print(f"\nLatest prices:")
        print(df_processed.tail())
        
        # Save processed data
        save_processed_data(df_processed)
