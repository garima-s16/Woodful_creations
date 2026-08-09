import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
});

client.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `******;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (email, password) =>
    client.post('/api/auth/login', { email, password }),
};

export const inventoryAPI = {
  getInventory: (params) => client.get('/api/inventory', { params }),
  addProduct: (data) => client.post('/api/inventory', data),
  updateProduct: (id, data) => client.patch(`/api/inventory/${id}`, data),
  getMaterials: () => client.get('/api/inventory/materials'),
};

export const salesAPI = {
  getOrders: (params) => client.get('/api/sales', { params }),
  getOrder: (id) => client.get(`/api/sales/${id}`),
  createOrder: (data) => client.post('/api/sales', data),
  updateOrder: (id, data) => client.patch(`/api/sales/${id}`, data),
  deleteOrder: (id) => client.delete(`/api/sales/${id}`),
};

export default client;
