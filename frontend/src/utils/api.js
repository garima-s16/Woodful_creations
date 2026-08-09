import axios from 'axios';

const resolveApiBaseUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }

  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname;
    return `http://${host}:8000`;
  }

  return 'http://localhost:8000';
};

const API_URL = resolveApiBaseUrl();

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const stockManagementAPI = {
  getDashboard: () => client.get('/api/stock-management/dashboard'),
  getMaterials: () => client.get('/api/stock-management/materials'),
  createMaterial: (data) => client.post('/api/stock-management/materials', data),
  updateMaterial: (id, data) => client.put(`/api/stock-management/materials/${id}`, data),
  getStockIn: () => client.get('/api/stock-management/stock-in'),
  createStockIn: (data) => client.post('/api/stock-management/stock-in', data),
  getStockOut: () => client.get('/api/stock-management/stock-out'),
  createStockOut: (data) => client.post('/api/stock-management/stock-out', data),
  getSuppliers: () => client.get('/api/stock-management/suppliers'),
  createSupplier: (data) => client.post('/api/stock-management/suppliers', data),
  getSettings: () => client.get('/api/stock-management/settings'),
  updateSettings: (data) => client.put('/api/stock-management/settings', data),
  downloadExcel: () =>
    client.get('/api/stock-management/reports/stock/download', {
      responseType: 'blob',
    }),
};

export default client;
