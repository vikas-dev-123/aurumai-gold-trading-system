# API Testing Guide

## Quick Test Commands

### 1. Health Check
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "database_connected": false,
  "lstm_model_loaded": false,
  "data_loaded": true
}
```

---

### 2. Get Current Price
```bash
curl http://localhost:8000/price
```

**Expected Response:**
```json
{
  "price": 1850.50,
  "currency": "USD",
  "unit": "per troy ounce",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "GLD ETF"
}
```

---

### 3. Get LSTM Prediction
```bash
curl http://localhost:8000/predict
```

**Expected Response:**
```json
{
  "prediction": {
    "predicted_price": 1865.20,
    "current_price": 1850.50,
    "change_percent": 0.79
  },
  "model": "LSTM",
  "sequence_length": 60,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 4. Get Trading Signal
```bash
curl http://localhost:8000/signal
```

**Expected Response:**
```json
{
  "signal": "BUY",
  "confidence": 0.85,
  "current_price": 1850.50,
  "target_price": 1865.20,
  "sentiment": 0.45,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 5. Get Market Sentiment
```bash
curl http://localhost:8000/sentiment
```

**Expected Response:**
```json
{
  "sentiment_score": 0.45,
  "sentiment_label": "positive",
  "articles_analyzed": 5,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### 6. Get Historical Data (Last 30 Days)
```bash
curl "http://localhost:8000/historical?days=30"
```

**Expected Response:**
```json
{
  "data": [
    {
      "date": "2024-01-15",
      "open": 1848.20,
      "high": 1855.30,
      "low": 1845.10,
      "close": 1850.50,
      "volume": 8500000
    },
    // ... more records
  ],
  "count": 30,
  "period_days": 30
}
```

---

### 7. Get Market Statistics
```bash
curl http://localhost:8000/stats
```

**Expected Response:**
```json
{
  "current_price": 1850.50,
  "day_high": 1855.30,
  "day_low": 1845.10,
  "week_change": 1.25,
  "month_change": 2.34,
  "year_high": 1900.00,
  "year_low": 1750.00,
  "average_volume": 8200000,
  "volatility": 1.45
}
```

---

## PowerShell Commands (Windows)

### Test All Endpoints
```powershell
# Health Check
Invoke-RestMethod -Uri "http://localhost:8000/health" | ConvertTo-Json

# Get Price
Invoke-RestMethod -Uri "http://localhost:8000/price" | ConvertTo-Json

# Get Prediction
Invoke-RestMethod -Uri "http://localhost:8000/predict" | ConvertTo-Json

# Get Signal
Invoke-RestMethod -Uri "http://localhost:8000/signal" | ConvertTo-Json

# Get Sentiment
Invoke-RestMethod -Uri "http://localhost:8000/sentiment" | ConvertTo-Json

# Get Historical Data
Invoke-RestMethod -Uri "http://localhost:8000/historical?days=30" | ConvertTo-Json

# Get Stats
Invoke-RestMethod -Uri "http://localhost:8000/stats" | ConvertTo-Json
```

---

## Python Test Script

Create `test_api.py`:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint: str, method: str = "GET"):
    """Test an API endpoint."""
    try:
        url = f"{BASE_URL}/{endpoint}"
        response = requests.get(url)
        response.raise_for_status()
        
        print(f"\n{'='*60}")
        print(f"Endpoint: {endpoint}")
        print(f"Status: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        
        return response.json()
    except Exception as e:
        print(f"\n❌ Error testing {endpoint}: {e}")
        return None

def main():
    """Test all endpoints."""
    print("🧪 Testing Gold Price Prediction API")
    print("="*60)
    
    endpoints = [
        "health",
        "price",
        "predict",
        "signal",
        "sentiment",
        "historical?days=30",
        "stats"
    ]
    
    results = {}
    
    for endpoint in endpoints:
        results[endpoint] = test_endpoint(endpoint)
    
    print("\n" + "="*60)
    print("✅ Testing Complete!")
    print("="*60)
    
    # Summary
    successful = sum(1 for r in results.values() if r is not None)
    print(f"\nSuccessful: {successful}/{len(endpoints)}")
    
    return results

if __name__ == "__main__":
    main()
```

Run with:
```bash
python test_api.py
```

---

## Interactive API Documentation

FastAPI provides automatic interactive documentation:

### Swagger UI
Visit: **http://localhost:8000/docs**

Features:
- Interactive API explorer
- Try out endpoints directly
- View request/response schemas
- Authentication testing

### ReDoc
Visit: **http://localhost:8000/redoc**

Features:
- Clean, readable documentation
- Search functionality
- Request/response examples

---

## Expected Behavior

### When Everything Works ✅
- All endpoints return 200 status
- Data is populated and realistic
- Predictions are reasonable (< 5% change)
- Signals include confidence scores
- Historical data has correct date range

### Common Issues & Solutions ⚠️

**Issue**: Backend not running
```
Solution: Start FastAPI server
cd backend
uvicorn api.main:app --reload
```

**Issue**: No data loaded
```
Solution: Wait for initial data fetch or check yfinance connection
Sample data will be auto-generated as fallback
```

**Issue**: Models not loaded
```
Solution: Train models first or run without pre-trained models
System will use rule-based logic as fallback
```

**Issue**: MongoDB error
```
Solution: System works without MongoDB using in-memory storage
Install MongoDB only if persistent storage needed
```

---

## Performance Testing

### Load Test with Apache Bench
```bash
# Test /price endpoint with 100 requests, 10 concurrent
ab -n 100 -c 10 http://localhost:8000/price

# Test /signal endpoint
ab -n 100 -c 10 http://localhost:8000/signal
```

### Expected Performance
- Health check: < 10ms
- Price fetch: < 50ms
- Prediction: < 100ms
- Signal generation: < 200ms
- Sentiment analysis: < 500ms (with cached results)

---

## Monitoring & Debugging

### Check Server Logs
```bash
# Backend logs (when running uvicorn)
# Watch console output for:
- Startup messages
- Request logs
- Error messages
- Model loading status
```

### Enable Debug Mode
Edit `backend/.env`:
```env
DEBUG=true
```

Restart server for changes to take effect.

---

## Integration Testing

### Full System Test

1. **Start Backend**
```bash
cd backend
uvicorn api.main:app --reload
```

2. **Start Frontend** (new terminal)
```bash
cd frontend
npm run dev
```

3. **Open Browser**
```
http://localhost:3000
```

4. **Verify Dashboard Shows**:
- ✅ Current price updating
- ✅ Prediction displayed
- ✅ Trading signal visible
- ✅ Sentiment panel active
- ✅ Chart rendering correctly
- ✅ Auto-refresh working (every 30s)

---

## Production Testing Checklist

Before deploying to production:

- [ ] All endpoints respond correctly
- [ ] Error handling works (test with invalid inputs)
- [ ] CORS configured properly
- [ ] Environment variables set correctly
- [ ] Database connection stable (if using MongoDB)
- [ ] Models load successfully
- [ ] Sample data generated if needed
- [ ] Frontend connects to backend
- [ ] Auto-refresh functioning
- [ ] No console errors in browser
- [ ] Mobile responsive design works
- [ ] API rate limiting considered
- [ ] Logging configured
- [ ] Backup strategies in place

---

## Security Testing

### Test Input Validation
```bash
# Invalid days parameter
curl "http://localhost:8000/historical?days=-1"

# Very large days parameter
curl "http://localhost:8000/historical?days=999999"

# Malformed requests
curl -X POST http://localhost:8000/price
```

All should return appropriate error responses (400/422).

---

**Happy Testing! 🎉**
