"""
Configuration management for the Gold Price Prediction System.
Loads environment variables and provides configuration constants.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "gold_trading_system")

# API Keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

# LSTM Model Configuration
LSTM_SEQUENCE_LENGTH = int(os.getenv("LSTM_SEQUENCE_LENGTH", "60"))
LSTM_HIDDEN_SIZE = int(os.getenv("LSTM_HIDDEN_SIZE", "128"))
LSTM_NUM_LAYERS = int(os.getenv("LSTM_NUM_LAYERS", "2"))
DROPOUT_RATE = float(os.getenv("DROPOUT_RATE", "0.2"))

# PPO Configuration
PPO_LEARNING_RATE = float(os.getenv("PPO_LEARNING_RATE", "0.0003"))
PPO_GAMMA = float(os.getenv("PPO_GAMMA", "0.99"))
PPO_N_STEPS = int(os.getenv("PPO_N_STEPS", "2048"))
PPO_BATCH_SIZE = int(os.getenv("PPO_BATCH_SIZE", "64"))

# Trading Configuration
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "10000"))
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.001"))

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Model paths
MODEL_DIR = BASE_DIR / "models" / "saved"
DATA_DIR = BASE_DIR / "data"

# Create directories if they don't exist
MODEL_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File paths
LSTM_MODEL_PATH = MODEL_DIR / "lstm_model.pth"
PPO_MODEL_PATH = MODEL_DIR / "ppo_model.zip"
SAMPLE_DATA_PATH = DATA_DIR / "sample_gold_prices.csv"


def get_config():
    """
    Returns a dictionary of all configuration parameters.
    
    Returns:
        dict: Configuration parameters
    """
    return {
        "mongodb": {
            "url": MONGODB_URL,
            "db_name": MONGODB_DB_NAME,
        },
        "lstm": {
            "sequence_length": LSTM_SEQUENCE_LENGTH,
            "hidden_size": LSTM_HIDDEN_SIZE,
            "num_layers": LSTM_NUM_LAYERS,
            "dropout_rate": DROPOUT_RATE,
        },
        "ppo": {
            "learning_rate": PPO_LEARNING_RATE,
            "gamma": PPO_GAMMA,
            "n_steps": PPO_N_STEPS,
            "batch_size": PPO_BATCH_SIZE,
        },
        "trading": {
            "initial_capital": INITIAL_CAPITAL,
            "commission_rate": COMMISSION_RATE,
        },
        "server": {
            "host": HOST,
            "port": PORT,
            "debug": DEBUG,
        },
        "paths": {
            "lstm_model": str(LSTM_MODEL_PATH),
            "ppo_model": str(PPO_MODEL_PATH),
            "sample_data": str(SAMPLE_DATA_PATH),
        },
    }
