import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (email, password) =>
    client.post('/api/auth/login', { email, password }),
};

export const dashboardAPI = {
  getDashboard: () => client.get('/api/dashboard'),
};

export const inventoryAPI = {
  getInventory: () => client.get('/api/inventory'),
  addProduct: (data) => client.post('/api/inventory', data),
  updateProduct: (id, data) => client.patch(`/api/inventory/${id}`, data),
};

export const chatAPI = {
  sendMessage: (message, conversationId) =>
    client.post('/api/chat', { message, conversation_id: conversationId }),
};

export default client;
export const salesAPI = {
  getOrders: (params) => client.get('/api/sales', { params }),
  getOrder: (id) => client.get(`/api/sales/${id}`),
  createOrder: (data) => client.post('/api/sales', data),
  updateOrder: (id, data) => client.patch(`/api/sales/${id}`, data),
  deleteOrder: (id) => client.delete(`/api/sales/${id}`),
};

export const reportsAPI = {
  downloadInventoryExcel: () =>
    client.get('/api/reports/inventory/excel', { responseType: 'blob' }),
  downloadSalesExcel: () =>
    client.get('/api/reports/sales/excel', { responseType: 'blob' }),
};
