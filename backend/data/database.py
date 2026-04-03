"""
MongoDB database connection and operations.
Handles storing and retrieving gold price data, predictions, and signals.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
from utils.config import MONGODB_URL, MONGODB_DB_NAME


class DatabaseConnection:
    """Database connection manager for MongoDB."""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.async_client = None
        self.async_db = None
    
    def connect(self):
        """Establish synchronous connection to MongoDB."""
        try:
            self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
            self.db = self.client[MONGODB_DB_NAME]
            
            # Test connection
            self.client.admin.command('ping')
            print(f"✓ Connected to MongoDB: {MONGODB_DB_NAME}")
            return True
        except Exception as e:
            print(f"✗ MongoDB connection failed: {e}")
            print("⚠ Running without database - using in-memory storage")
            return False
    
    async def connect_async(self):
        """Establish asynchronous connection to MongoDB."""
        try:
            self.async_client = AsyncIOMotorClient(MONGODB_URL)
            self.async_db = self.async_client[MONGODB_DB_NAME]
            
            # Test connection
            await self.async_client.admin.command('ping')
            print(f"✓ Connected to MongoDB (async): {MONGODB_DB_NAME}")
            return True
        except Exception as e:
            print(f"✗ MongoDB async connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connections."""
        if self.client:
            self.client.close()
            print("✓ MongoDB connection closed")
    
    async def disconnect_async(self):
        """Close async database connections."""
        if self.async_client:
            self.async_client.close()
    
    def get_collection(self, collection_name: str):
        """Get a collection from the database."""
        if self.db:
            return self.db[collection_name]
        return None
    
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self.client is not None


# Global database instance
db = DatabaseConnection()


def store_price_data(df: pd.DataFrame, symbol: str = "GLD"):
    """
    Store price data in MongoDB.
    
    Args:
        df: DataFrame with price data
        symbol: Asset symbol (default: GLD)
    """
    collection = db.get_collection("price_data")
    if collection is None:
        return False
    
    records = []
    for date, row in df.iterrows():
        record = {
            "symbol": symbol,
            "date": date,
            "open": float(row.get('Open', 0)),
            "high": float(row.get('High', 0)),
            "low": float(row.get('Low', 0)),
            "close": float(row.get('Close', 0)),
            "volume": int(row.get('Volume', 0)) if 'Volume' in row else 0,
            "timestamp": datetime.now()
        }
        records.append(record)
    
    if records:
        collection.insert_many(records)
        print(f"✓ Stored {len(records)} price records")
        return True
    
    return False


def get_latest_price(symbol: str = "GLD") -> dict:
    """
    Get the latest price from database.
    
    Args:
        symbol: Asset symbol
    
    Returns:
        Dictionary with latest price data or None
    """
    collection = db.get_collection("price_data")
    if collection is None:
        return None
    
    latest = collection.find_one(
        {"symbol": symbol},
        sort=[("date", -1)]
    )
    
    return latest


def get_historical_prices(symbol: str = "GLD", days: int = 365) -> list:
    """
    Get historical prices from database.
    
    Args:
        symbol: Asset symbol
        days: Number of days to retrieve
    
    Returns:
        List of price records
    """
    from datetime import timedelta
    
    collection = db.get_collection("price_data")
    if collection is None:
        return []
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    cursor = collection.find(
        {"symbol": symbol, "date": {"$gte": cutoff_date}}
    ).sort("date", -1)
    
    return list(cursor)


def store_prediction(date: datetime, predicted_price: float, actual_price: float = None,
                     model_type: str = "LSTM", confidence: float = None):
    """
    Store prediction data in MongoDB.
    
    Args:
        date: Prediction date
        predicted_price: Predicted price value
        actual_price: Actual price (if known)
        model_type: Type of model used
        confidence: Prediction confidence score
    """
    collection = db.get_collection("predictions")
    if collection is None:
        return False
    
    record = {
        "date": date,
        "predicted_price": float(predicted_price),
        "actual_price": float(actual_price) if actual_price else None,
        "model_type": model_type,
        "confidence": float(confidence) if confidence else None,
        "timestamp": datetime.now()
    }
    
    collection.insert_one(record)
    print(f"✓ Stored prediction: {predicted_price:.2f}")
    return True


def store_signal(signal: str, price: float, confidence: float = None, 
                 sentiment: float = None, metadata: dict = None):
    """
    Store trading signal in MongoDB.
    
    Args:
        signal: Signal type (BUY/SELL/HOLD)
        price: Current price when signal generated
        confidence: Signal confidence score
        sentiment: Sentiment score
        metadata: Additional metadata
    """
    collection = db.get_collection("signals")
    if collection is None:
        return False
    
    record = {
        "signal": signal,
        "price": float(price),
        "confidence": float(confidence) if confidence else None,
        "sentiment": float(sentiment) if sentiment else None,
        "metadata": metadata or {},
        "timestamp": datetime.now()
    }
    
    collection.insert_one(record)
    print(f"✓ Stored signal: {signal}")
    return True


def get_latest_signal() -> dict:
    """
    Get the latest trading signal from database.
    
    Returns:
        Dictionary with latest signal or None
    """
    collection = db.get_collection("signals")
    if collection is None:
        return None
    
    latest = collection.find_one(sort=[("timestamp", -1)])
    return latest
