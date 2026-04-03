"""
Technical indicators for gold price analysis.
Implements RSI, Moving Averages, and other trading indicators.
"""

import numpy as np
import pandas as pd


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        prices: Series of closing prices
        period: RSI calculation period (default: 14)
    
    Returns:
        RSI values as a Series
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_sma(prices: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).
    
    Args:
        prices: Series of prices
        period: SMA period (default: 20)
    
    Returns:
        SMA values as a Series
    """
    return prices.rolling(window=period).mean()


def calculate_ema(prices: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).
    
    Args:
        prices: Series of prices
        period: EMA period (default: 20)
    
    Returns:
        EMA values as a Series
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        prices: Series of prices
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)
    
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
    """
    Calculate Bollinger Bands.
    
    Args:
        prices: Series of prices
        period: Rolling window period (default: 20)
        std_dev: Number of standard deviations (default: 2)
    
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = calculate_sma(prices, period)
    rolling_std = prices.rolling(window=period).std()
    
    upper_band = middle_band + (std_dev * rolling_std)
    lower_band = middle_band - (std_dev * rolling_std)
    
    return upper_band, middle_band, lower_band


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of closing prices
        period: ATR period (default: 14)
    
    Returns:
        ATR values as a Series
    """
    prev_close = close.shift(1)
    
    true_range_1 = high - low
    true_range_2 = abs(high - prev_close)
    true_range_3 = abs(low - prev_close)
    
    true_range = pd.concat([true_range_1, true_range_2, true_range_3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators to a DataFrame.
    
    Args:
        df: DataFrame with OHLC columns (Open, High, Low, Close)
    
    Returns:
        DataFrame with added technical indicators
    """
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # Moving averages
    df['SMA_20'] = calculate_sma(df['Close'], 20)
    df['SMA_50'] = calculate_sma(df['Close'], 50)
    df['EMA_12'] = calculate_ema(df['Close'], 12)
    df['EMA_26'] = calculate_ema(df['Close'], 26)
    
    # RSI
    df['RSI'] = calculate_rsi(df['Close'], 14)
    
    # MACD
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['Close'])
    
    # Bollinger Bands
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = calculate_bollinger_bands(df['Close'])
    
    # ATR
    df['ATR'] = calculate_atr(df['High'], df['Low'], df['Close'])
    
    # Price returns
    df['Returns'] = df['Close'].pct_change()
    df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
    
    # Volatility (rolling standard deviation of returns)
    df['Volatility'] = df['Returns'].rolling(window=20).std()
    
    return df


def normalize_features(df: pd.DataFrame, feature_columns: list) -> pd.DataFrame:
    """
    Normalize features using min-max scaling.
    
    Args:
        df: DataFrame with features
        feature_columns: List of column names to normalize
    
    Returns:
        DataFrame with normalized features
    """
    df = df.copy()
    
    for col in feature_columns:
        min_val = df[col].min()
        max_val = df[col].max()
        
        if max_val - min_val > 0:
            df[col] = (df[col] - min_val) / (max_val - min_val)
        else:
            df[col] = 0.0
    
    return df


def standardize_features(df: pd.DataFrame, feature_columns: list, 
                         mean: np.ndarray = None, std: np.ndarray = None) -> tuple:
    """
    Standardize features using z-score normalization.
    
    Args:
        df: DataFrame with features
        feature_columns: List of column names to standardize
        mean: Pre-computed mean (optional)
        std: Pre-computed std (optional)
    
    Returns:
        Tuple of (DataFrame with standardized features, mean, std)
    """
    df = df.copy()
    
    if mean is None:
        mean = df[feature_columns].mean()
    
    if std is None:
        std = df[feature_columns].std()
    
    df[feature_columns] = (df[feature_columns] - mean) / std
    
    return df, mean, std
