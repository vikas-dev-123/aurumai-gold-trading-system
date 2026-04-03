import axios from 'axios';

const API_BASE_URL = '/api';

// Fetch current gold price
export const getCurrentPrice = async () => {
  const response = await axios.get(`${API_BASE_URL}/price`);
  return response.data;
};

// Get AI prediction
export const getPrediction = async () => {
  const response = await axios.get(`${API_BASE_URL}/predict`);
  return response.data;
};

// Get trading signal
export const getTradingSignal = async () => {
  const response = await axios.get(`${API_BASE_URL}/signal`);
  return response.data;
};

// Get sentiment analysis
export const getSentiment = async () => {
  const response = await axios.get(`${API_BASE_URL}/sentiment`);
  return response.data;
};

// Get historical data
export const getHistoricalData = async (days = 30) => {
  const response = await axios.get(`${API_BASE_URL}/historical`, {
    params: { days }
  });
  return response.data.data; // Extract the 'data' array from response
};

// Get statistics
export const getStats = async () => {
  const response = await axios.get(`${API_BASE_URL}/stats`);
  return response.data;
};

// Health check
export const healthCheck = async () => {
  const response = await axios.get(`${API_BASE_URL}/health`);
  return response.data;
};
