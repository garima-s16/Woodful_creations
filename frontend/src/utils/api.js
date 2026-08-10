import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// withCredentials sends/receives the HttpOnly auth cookie automatically.
// No token is ever read from or written to localStorage/sessionStorage -
// that would be readable by any injected script (XSS), which defeats the
// purpose of an HttpOnly cookie.
const client = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/') {
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (email, password) => client.post('/api/auth/login', { email, password }),
  logout: () => client.post('/api/auth/logout'),
  me: () => client.get('/api/auth/me'),
};

export const dashboardAPI = {
  getDashboard: () => client.get('/api/dashboard'),
};

export const inventoryAPI = {
  getInventory: () => client.get('/api/inventory'),
  addProduct: (data) => client.post('/api/inventory', data),
  updateProduct: (id, data) => client.patch(`/api/inventory/${id}`, data),
};

export const clientsAPI = {
  getClients: (params) => client.get('/api/clients', { params }),
  addClient: (data) => client.post('/api/clients', data),
  updateClient: (id, data) => client.put(`/api/clients/${id}`, data),
  deleteClient: (id) => client.delete(`/api/clients/${id}`),
};

export const chatAPI = {
  sendMessage: (message, conversationId) =>
    client.post('/api/chat', { message, conversation_id: conversationId }),
};

export default client;
