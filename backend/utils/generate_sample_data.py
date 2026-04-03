"""
Generate comprehensive sample dataset for testing.
Creates realistic gold price movements and technical indicators.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path


def generate_sample_data(n_days: int = 730, seed: int = 42):
    """
    Generate realistic sample gold price data.
    
    Args:
        n_days: Number of days of data to generate
        seed: Random seed for reproducibility
    
    Returns:
        DataFrame with OHLCV data and technical indicators
    """
    np.random.seed(seed)
    
    print(f"Generating {n_days} days of sample gold price data...")
    
    # Generate dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')  # Business days
    
    # Starting price around $1800 (realistic 2023-2024 range)
    base_price = 1800
    
    # Generate realistic daily returns
    # Slight upward bias with realistic volatility
    mu = 0.0003  # Daily drift
    sigma = 0.015  # Daily volatility
    
    daily_returns = np.random.normal(mu, sigma, len(dates))
    
    # Calculate cumulative returns and prices
    cumulative_returns = (1 + daily_returns).cumprod()
    close_prices = base_price * cumulative_returns
    
    # Generate OHLC based on close price
    # Intraday volatility
    intraday_vol = np.random.uniform(0.005, 0.02, len(dates))
    
    open_prices = close_prices * (1 + np.random.uniform(-0.005, 0.005, len(dates)))
    high_prices = np.maximum(open_prices, close_prices) * (1 + intraday_vol)
    low_prices = np.minimum(open_prices, close_prices) * (1 - intraday_vol)
    
    # Volume (random with weekly patterns)
    base_volume = 8000000
    weekly_pattern = np.tile([1.2, 1.0, 1.1, 1.0, 0.8], len(dates) // 5 + 1)[:len(dates)]
    volume = (base_volume * weekly_pattern * np.random.uniform(0.7, 1.3, len(dates))).astype(int)
    
    # Create DataFrame
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume
    }, index=dates)
    
    df.index.name = 'Date'
    
    # Add technical indicators
    print("Calculating technical indicators...")
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # Bollinger Bands
    df['BB_Middle'] = df['SMA_20']
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (2 * bb_std)
    df['BB_Lower'] = df['BB_Middle'] - (2 * bb_std)
    
    # ATR
    prev_close = df['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = abs(df['High'] - prev_close)
    tr3 = abs(df['Low'] - prev_close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=14).mean()
    
    # Returns
    df['Returns'] = df['Close'].pct_change()
    df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
    
    # Volatility (20-day rolling std)
    df['Volatility'] = df['Returns'].rolling(window=20).std()
    
    # Drop NaN values
    df = df.dropna()
    
    print(f"✓ Generated {len(df)} records with {len(df.columns)} features")
    
    return df


def save_sample_data(df: pd.DataFrame, output_path: str):
    """
    Save sample data to CSV.
    
    Args:
        df: DataFrame with price data
        output_path: Output file path
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_file)
    print(f"✓ Sample data saved to: {output_file}")
    
    # Display statistics
    print("\n" + "="*60)
    print("Sample Data Statistics")
    print("="*60)
    print(f"Date Range: {df.index.min().strftime('%Y-%m-%d')} to {df.index.max().strftime('%Y-%m-%d')}")
    print(f"Total Records: {len(df)}")
    print(f"Features: {len(df.columns)}")
    print(f"\nPrice Statistics:")
    print(f"  Min: ${df['Close'].min():.2f}")
    print(f"  Max: ${df['Close'].max():.2f}")
    print(f"  Mean: ${df['Close'].mean():.2f}")
    print(f"  Std: ${df['Close'].std():.2f}")
    print(f"\nLatest Price: ${df['Close'].iloc[-1]:.2f}")
    print("="*60)


if __name__ == "__main__":
    from config import SAMPLE_DATA_PATH
    
    # Generate sample data
    df = generate_sample_data(n_days=730)
    
    # Save to file
    save_sample_data(df, SAMPLE_DATA_PATH)
    
    print("\n✓ Sample data generation complete!")
    print(f"  Location: {SAMPLE_DATA_PATH}")
