# Quick Start Guide

## Windows PowerShell Script

### Prerequisites Check
```powershell
# Check Python version (need 3.8+)
python --version

# Check Node.js version (need 18+)
node --version
```

### Backend Setup & Start
```powershell
# Navigate to backend
cd backend

# Create virtual environment if not exists
if (-not (Test-Path "venv")) {
    python -m venv venv
}

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup & Start (New Terminal)
```powershell
# Navigate to frontend
cd frontend

# Install dependencies (first time only)
npm install

# Start Next.js development server
npm run dev
```

## Access the Application

1. **Backend API**: http://localhost:8000
2. **API Documentation**: http://localhost:8000/docs
3. **Frontend Dashboard**: http://localhost:3000

---

## Optional: Train Models First

### Train LSTM Model
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python training/train_lstm.py --epochs 50
```

### Train PPO Agent
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python training/train_ppo.py --episodes 500
```

---

## Troubleshooting

### If MongoDB is not installed:
The system will work in memory-only mode without persistence.

### If yfinance fails:
Sample data will be auto-generated as fallback.

### If port 8000 is busy:
Change PORT in backend/.env file

### If port 3000 is busy:
Next.js will automatically use port 3001
