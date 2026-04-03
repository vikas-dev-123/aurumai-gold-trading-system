import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getCurrentPrice, getPrediction, getTradingSignal, getSentiment, getHistoricalData } from './api';
import './App.css';

function App() {
  const [data, setData] = useState({
    price: null,
    prediction: null,
    signal: null,
    sentiment: null,
    historical: []
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Portfolio state
  const [portfolio, setPortfolio] = useState({
    cash: 10000,
    goldOz: 0
  });

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log('Fetching data from backend...');
      
      const [priceRes, predictionRes, signalRes, sentimentRes, historicalRes] = await Promise.all([
        getCurrentPrice(),
        getPrediction(),
        getTradingSignal(),
        getSentiment(),
        getHistoricalData(30)
      ]);

      console.log('Data received:', {
        price: priceRes,
        prediction: predictionRes,
        signal: signalRes,
        sentiment: sentimentRes,
        historical: historicalRes
      });

      setData({
        price: priceRes,
        prediction: predictionRes,
        signal: signalRes,
        sentiment: sentimentRes,
        historical: historicalRes
      });

      setLastUpdated(new Date());
    } catch (err) {
      console.error('Error fetching data:', err);
      console.error('Error details:', err.message);
      console.error('Backend URL:', 'http://localhost:8000');
      setError(`Failed to load dashboard data: ${err.message}. Make sure backend is running on http://localhost:8000`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Trading functions
  const handleBuy = () => {
    if (data.price && portfolio.cash >= data.price.current_price) {
      setPortfolio(prev => ({
        cash: prev.cash - data.price.current_price,
        goldOz: prev.goldOz + 1
      }));
    }
  };

  const handleSell = () => {
    if (data.price && portfolio.goldOz >= 1) {
      setPortfolio(prev => ({
        cash: prev.cash + data.price.current_price,
        goldOz: prev.goldOz - 1
      }));
    }
  };

  const calculatePortfolioValue = () => {
    return portfolio.cash + (portfolio.goldOz * (data.price?.current_price || 0));
  };

  const formatChartData = (historical) => {
    if (!historical || !Array.isArray(historical) || historical.length === 0) {
      console.warn('Invalid historical data:', historical);
      return [];
    }
    return historical.map(item => ({
      date: new Date(item.date).toLocaleDateString(),
      price: item.close
    }));
  };

  if (loading && !data.price) {
    return (
      <div className="container" style={{ textAlign: 'center', paddingTop: '100px' }}>
        <div className="spinner"></div>
        <p style={{ color: 'white', fontSize: '1.2rem' }}>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>🏆 Gold Price Prediction System</h1>
        <p>AI-Powered Trading Signals • LSTM + PPO + Sentiment Analysis</p>
        {lastUpdated && (
          <p style={{ fontSize: '0.8rem', marginTop: '8px', color: '#999' }}>
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </header>

      {/* Error Message */}
      {error && (
        <div style={{ 
          background: 'rgba(235, 51, 73, 0.1)', 
          border: '2px solid #eb3349', 
          padding: '16px', 
          borderRadius: '8px',
          marginBottom: '20px',
          color: '#eb3349'
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Debug Info */}
      <div style={{ 
        background: 'rgba(255, 255, 255, 0.9)', 
        padding: '12px', 
        borderRadius: '8px',
        marginBottom: '20px',
        fontSize: '0.85rem'
      }}>
        <strong>Loading State:</strong> {loading ? 'YES' : 'NO'} |{' '}
        <strong>Error:</strong> {error ? 'YES' : 'NO'} |{' '}
        <strong>Price Data:</strong> {data.price ? 'LOADED' : 'NOT LOADED'} |{' '}
        <strong>Historical:</strong> {data.historical?.length > 0 ? `${data.historical.length} records` : 'EMPTY'}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-4" style={{ marginBottom: '30px' }}>
        {/* Current Price */}
        <div className="stat-card">
          <div className="stat-label">Current Price</div>
          <div className="stat-value">
            ${data.price?.current_price?.toFixed(2) || '---'}
          </div>
          <div className={`price-change ${data.price?.change_24h >= 0 ? 'positive' : 'negative'}`}>
            {data.price?.change_24h >= 0 ? '↑' : '↓'} {Math.abs(data.price?.change_24h || 0).toFixed(2)}%
          </div>
        </div>

        {/* Prediction */}
        <div className="stat-card">
          <div className="stat-label">AI Prediction</div>
          <div className="stat-value">
            ${data.prediction?.prediction?.predicted_price?.toFixed(2) || '---'}
          </div>
          <div className={`price-change ${data.prediction?.prediction?.change_percent >= 0 ? 'positive' : 'negative'}`}>
            {data.prediction?.prediction?.change_percent >= 0 ? '↑' : '↓'} {Math.abs(data.prediction?.prediction?.change_percent || 0).toFixed(2)}%
          </div>
        </div>

        {/* Portfolio Value */}
        <div className="stat-card">
          <div className="stat-label">Portfolio Value</div>
          <div className="stat-value">
            ${calculatePortfolioValue().toFixed(2)}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#999', marginTop: '4px' }}>
            Cash: ${portfolio.cash.toFixed(2)} | Gold: {portfolio.goldOz} oz
          </div>
        </div>

        {/* Sentiment */}
        <div className="stat-card">
          <div className="stat-label">Market Sentiment</div>
          <div className="stat-value" style={{ 
            color: data.sentiment?.score > 0.3 ? '#11998e' : data.sentiment?.score < -0.3 ? '#eb3349' : '#f59e0b'
          }}>
            {data.sentiment?.score > 0 ? '+' : ''}{(data.sentiment?.score * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: '0.9rem', marginTop: '4px' }}>
            {data.sentiment?.score > 0.3 ? '😊 Positive' : data.sentiment?.score < -0.3 ? '😟 Negative' : '😐 Neutral'}
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-2" style={{ marginBottom: '30px' }}>
        {/* Price Chart */}
        <div className="card">
          <h2 style={{ marginBottom: '20px', color: '#667eea' }}>📊 Price Chart (30 Days)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={formatChartData(data.historical)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="price" stroke="#667eea" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Trading Signal & Actions */}
        <div className="card">
          <h2 style={{ marginBottom: '20px', color: '#667eea' }}>🎯 Trading Signal</h2>
          
          {data.signal?.signal && (
            <div style={{ textAlign: 'center' }}>
              <div className={`signal-badge signal-${data.signal.signal.toLowerCase()}`}>
                {data.signal.signal}
              </div>
              <div style={{ marginTop: '16px', marginBottom: '16px' }}>
                <p style={{ color: '#666', marginBottom: '8px' }}>Confidence: {(data.signal.confidence * 100).toFixed(0)}%</p>
                <div style={{ background: '#e0e0e0', borderRadius: '10px', height: '10px', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${data.signal.confidence * 100}%`,
                    background: `linear-gradient(135deg, ${data.signal.signal === 'BUY' ? '#11998e' : data.signal.signal === 'SELL' ? '#eb3349' : '#f093fb'} 0%, ${data.signal.signal === 'BUY' ? '#38ef7d' : data.signal.signal === 'SELL' ? '#f45c43' : '#f5576c'} 100%)`,
                    height: '100%',
                    transition: 'width 0.5s ease'
                  }}></div>
                </div>
              </div>
            </div>
          )}

          {/* Trading Buttons */}
          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button 
              className="btn btn-success" 
              onClick={handleBuy}
              disabled={!data.price}
              style={{ flex: 1 }}
            >
              💰 Buy 1 oz
            </button>
            <button 
              className="btn btn-danger" 
              onClick={handleSell}
              disabled={!data.price || portfolio.goldOz < 1}
              style={{ flex: 1 }}
            >
              💸 Sell 1 oz
            </button>
          </div>

          {/* Quick Stats */}
          <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #e0e0e0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ color: '#666' }}>Week Change:</span>
              <span style={{ color: '#11998e', fontWeight: 'bold' }}>+2.5%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#666' }}>Month Change:</span>
              <span style={{ color: '#eb3349', fontWeight: 'bold' }}>-1.2%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sentiment & News */}
      <div className="card" style={{ marginBottom: '30px' }}>
        <h2 style={{ marginBottom: '20px', color: '#667eea' }}>💭 Market Sentiment Analysis</h2>
        {data.sentiment?.headline ? (
          <div style={{ padding: '16px', background: 'rgba(102, 126, 234, 0.05)', borderRadius: '8px' }}>
            <h3 style={{ color: '#667eea', marginBottom: '8px' }}>📰 Latest News</h3>
            <p style={{ color: '#333', lineHeight: '1.6' }}>{data.sentiment.headline}</p>
            {data.sentiment.source && (
              <p style={{ color: '#999', fontSize: '0.8rem', marginTop: '8px' }}>
                Source: <strong>{data.sentiment.source}</strong>
              </p>
            )}
          </div>
        ) : (
          <p style={{ color: '#999', textAlign: 'center' }}>Loading sentiment analysis...</p>
        )}
      </div>

      {/* Footer */}
      <footer style={{ textAlign: 'center', color: 'white', padding: '20px', opacity: 0.8 }}>
        <p>© 2026 Gold Price Prediction System • Powered by AI & Machine Learning</p>
        <p style={{ fontSize: '0.8rem', marginTop: '8px' }}>
          Backend: http://localhost:8000 • Frontend: http://localhost:3000
        </p>
      </footer>
    </div>
  );
}

export default App;
