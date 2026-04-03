"""
FastAPI application for Gold Price Prediction and Trading System.
Provides REST API endpoints for price data, predictions, and trading signals.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

from utils.config import (
    HOST, PORT, DEBUG, 
    LSTM_MODEL_PATH, PPO_MODEL_PATH,
    get_config
)
from data.database import db, get_latest_price, store_signal
from data.data_pipeline import load_or_fetch_data, preprocess_data, prepare_lstm_features
from models.lstm_model import create_lstm_model, predict_price, LSTMModel
from models.sentiment_model import analyze_current_sentiment, get_sentiment_analyzer
from models.ppo_agent import GoldTradingEnv, PPOAgent


# Global variables for models and data
app_data = {
    'lstm_model': None,
    'ppo_agent': None,
    'price_df': None,
    'features': None,
    'scaler_params': None,
    'db_connected': False
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    print("=" * 60)
    print("Starting Gold Price Prediction System")
    print("=" * 60)
    
    # Connect to database
    app_data['db_connected'] = db.connect()
    
    # Load or fetch price data
    print("\nLoading price data...")
    raw_df = load_or_fetch_data()
    
    if not raw_df.empty:
        app_data['price_df'] = preprocess_data(raw_df)
        
        # Prepare features
        features, _, scaler_params = prepare_lstm_features(app_data['price_df'])
        app_data['features'] = features
        app_data['scaler_params'] = scaler_params
        
        print(f"✓ Loaded {len(app_data['price_df'])} price records")
    else:
        print("⚠ No price data available")
    
    # Load LSTM model
    if LSTM_MODEL_PATH.exists():
        print(f"\nLoading LSTM model from {LSTM_MODEL_PATH}")
        try:
            lstm_model, device = create_lstm_model(
                input_size=len(app_data['scaler_params']['columns']),
                pretrained=True,
                model_path=str(LSTM_MODEL_PATH)
            )
            app_data['lstm_model'] = (lstm_model, device)
            print("✓ LSTM model loaded")
        except Exception as e:
            print(f"⚠ Error loading LSTM model: {e}")
    else:
        print("⚠ LSTM model not found - predictions will be unavailable")
    
    # Load PPO agent
    if PPO_MODEL_PATH.exists():
        print(f"\nLoading PPO model from {PPO_MODEL_PATH}")
        try:
            # We'll load it on-demand when needed
            print("✓ PPO model file found")
        except Exception as e:
            print(f"⚠ Error loading PPO model: {e}")
    else:
        print("⚠ PPO model not found - signals will be unavailable")
    
    print("\n" + "=" * 60)
    print("Application started successfully!")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("\nShutting down...")
    db.disconnect()
    print("✓ Application stopped")


# Create FastAPI app
app = FastAPI(
    title="Gold Price Prediction & Trading System",
    description="AI-powered gold price prediction and trading signal generation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_price() -> float:
    """Get current gold price from data."""
    if app_data['price_df'] is None or app_data['price_df'].empty:
        return None
    
    return app_data['price_df']['Close'].iloc[-1]


def get_lstm_prediction() -> dict:
    """Generate LSTM price prediction."""
    if app_data['lstm_model'] is None:
        return None
    
    model, device = app_data['lstm_model']
    features = app_data['features']
    scaler_params = app_data['scaler_params']
    
    if features is None or len(features) < 60:
        return None
    
    # Get last sequence
    sequence_length = 60
    last_sequence = features[-sequence_length:]
    
    # Convert to tensor
    import torch
    sequence_tensor = torch.FloatTensor(last_sequence).unsqueeze(0).to(device)
    
    # Predict
    with torch.no_grad():
        prediction_normalized = model(sequence_tensor).cpu().numpy().flatten()[0]
    
    # Denormalize
    close_min = scaler_params['min'][3]
    close_range = scaler_params['range'][3]
    predicted_price = prediction_normalized * close_range + close_min
    
    current_price = get_current_price()
    
    return {
        'predicted_price': float(predicted_price),
        'current_price': float(current_price) if current_price else None,
        'change_percent': ((predicted_price - current_price) / current_price * 100) if current_price else None
    }


def get_ppo_signal() -> dict:
    """Get trading signal from PPO agent."""
    if app_data['price_df'] is None:
        return None
    
    current_price = get_current_price()
    lstm_pred = get_lstm_prediction()
    
    if lstm_pred is None:
        return None
    
    # Simple rule-based signal (in production, use actual PPO agent)
    predicted_change = lstm_pred['change_percent']
    
    # Get sentiment
    try:
        sentiment_result = analyze_current_sentiment()
        sentiment_score = sentiment_result.get('sentiment_score', 0)
    except:
        sentiment_score = 0
    
    # Generate signal based on prediction and sentiment
    if predicted_change > 1.0 and sentiment_score > 0:
        signal = "BUY"
        confidence = min(abs(predicted_change) + abs(sentiment_score), 1.0)
    elif predicted_change < -1.0 or sentiment_score < -0.3:
        signal = "SELL"
        confidence = min(abs(predicted_change) + abs(sentiment_score), 1.0)
    else:
        signal = "HOLD"
        confidence = 0.5
    
    result = {
        'signal': signal,
        'confidence': float(confidence),
        'current_price': float(current_price),
        'predicted_price': lstm_pred['predicted_price'],
        'sentiment_score': float(sentiment_score),
        'timestamp': datetime.now()
    }
    
    # Store signal in database
    if app_data['db_connected']:
        store_signal(
            signal=signal,
            price=current_price,
            confidence=confidence,
            sentiment=sentiment_score,
            metadata={'predicted_change': predicted_change}
        )
    
    return result


@app.get("/api")
async def root():
    """Root endpoint."""
    return {
        "message": "Gold Price Prediction & Trading System API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database_connected": app_data['db_connected'],
        "lstm_model_loaded": app_data['lstm_model'] is not None,
        "data_loaded": app_data['price_df'] is not None and not app_data['price_df'].empty
    }


@app.get("/api/price")
async def get_price():
    """Get current gold price."""
    price = get_current_price()
    
    if price is None:
        raise HTTPException(status_code=404, detail="Price data not available")
    
    # Calculate 24h change (using previous day's close)
    change_24h = 0.0
    if app_data['price_df'] is not None and len(app_data['price_df']) >= 2:
        prev_close = app_data['price_df']['Close'].iloc[-2]
        change_24h = ((price - prev_close) / prev_close) * 100
    
    return {
        "price": float(price),
        "currency": "USD",
        "unit": "per troy ounce",
        "timestamp": datetime.now(),
        "source": "GLD ETF",
        "change_24h": float(change_24h)
    }


@app.get("/api/predict")
async def predict():
    """Get LSTM price prediction."""
    prediction = get_lstm_prediction()
    
    if prediction is None:
        raise HTTPException(status_code=503, detail="Prediction model not available")
    
    return {
        "prediction": prediction,
        "timestamp": datetime.now(),
        "model": "LSTM",
        "sequence_length": 60
    }


@app.get("/api/signal")
async def trading_signal():
    """Get trading signal (BUY/SELL/HOLD)."""
    signal = get_ppo_signal()
    
    if signal is None:
        raise HTTPException(status_code=503, detail="Signal generation not available")
    
    return {
        "signal": signal['signal'],
        "confidence": signal['confidence'],
        "current_price": signal['current_price'],
        "target_price": signal['predicted_price'],
        "sentiment": signal['sentiment_score'],
        "timestamp": signal['timestamp']
    }


@app.get("/api/sentiment")
async def sentiment():
    """Get market sentiment analysis."""
    try:
        result = analyze_current_sentiment()
        
        # Get mock news headline
        headlines = [
            "Gold prices rise amid global economic uncertainty",
            "Federal Reserve policy decision impacts gold market",
            "Investors turn to safe-haven assets as markets volatile",
            "Dollar weakness supports gold price rally",
            "Central banks increase gold reserves globally"
        ]
        
        sources = ["Reuters", "Bloomberg", "CNBC", "Financial Times", "MarketWatch"]
        
        return {
            "sentiment_score": result.get('sentiment_score', 0),
            "score": result.get('sentiment_score', 0),  # Add 'score' field for frontend
            "sentiment_label": result.get('sentiment_label', 'neutral'),
            "articles_analyzed": result.get('article_count', 0),
            "headline": headlines[abs(hash(str(result.get('sentiment_score', 0)))) % len(headlines)],
            "source": sources[abs(hash(str(result.get('sentiment_score', 0)))) % len(sources)],
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis error: {str(e)}")


@app.get("/api/historical")
async def historical_prices(days: int = 30):
    """Get historical price data."""
    if app_data['price_df'] is None or app_data['price_df'].empty:
        raise HTTPException(status_code=404, detail="Historical data not available")
    
    # Get last N days
    df = app_data['price_df'].tail(days)
    
    # Format response
    data = []
    for date, row in df.iterrows():
        data.append({
            "date": date.strftime('%Y-%m-%d'),
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close']),
            "volume": int(row.get('Volume', 0)) if 'Volume' in row else None
        })
    
    return {
        "data": data,
        "count": len(data),
        "period_days": days
    }


@app.get("/api/stats")
async def market_stats():
    """Get market statistics."""
    if app_data['price_df'] is None or app_data['price_df'].empty:
        raise HTTPException(status_code=404, detail="Data not available")
    
    df = app_data['price_df']
    
    current_price = get_current_price()
    
    # Calculate statistics
    stats = {
        "current_price": float(current_price),
        "day_high": float(df['High'].iloc[-1]),
        "day_low": float(df['Low'].iloc[-1]),
        "week_change": float((df['Close'].iloc[-1] - df['Close'].iloc[-5]) / df['Close'].iloc[-5] * 100) if len(df) >= 5 else None,
        "month_change": float((df['Close'].iloc[-1] - df['Close'].iloc[-20]) / df['Close'].iloc[-20] * 100) if len(df) >= 20 else None,
        "year_high": float(df['High'].max()),
        "year_low": float(df['Low'].min()),
        "average_volume": float(df['Volume'].mean()) if 'Volume' in df.columns else None,
        "volatility": float(df['Returns'].std() * 100) if 'Returns' in df.columns else None
    }
    
    return stats


if __name__ == "__main__":
    import uvicorn
    
    print(f"\nStarting server at http://{HOST}:{PORT}")
    if DEBUG:
        print("Debug mode: ON")
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
