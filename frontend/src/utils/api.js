import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// withCredentials sends/receives the HttpOnly auth cookie automatically.
// No token is ever read from or written to localStorage/sessionStorage.
const client = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (identifier, password) => client.post('/api/auth/login', { identifier, password }),
  logout: () => client.post('/api/auth/logout'),
  me: () => client.get('/api/auth/me'),
};

export const dashboardAPI = {
  stock: () => client.get('/api/dashboard/stock'),
  orders: () => client.get('/api/dashboard/orders'),
  staff: () => client.get('/api/dashboard/staff'),
};

export const suppliersAPI = {
  list: (params) => client.get('/api/suppliers/', { params }),
  get: (id) => client.get(`/api/suppliers/${id}`),
  create: (data) => client.post('/api/suppliers/', data),
  update: (id, data) => client.put(`/api/suppliers/${id}`, data),
  remove: (id) => client.delete(`/api/suppliers/${id}`),
};

export const materialsAPI = {
  list: (params) => client.get('/api/materials/', { params }),
  get: (id) => client.get(`/api/materials/${id}`),
  create: (data) => client.post('/api/materials/', data),
  update: (id, data) => client.put(`/api/materials/${id}`, data),
  remove: (id) => client.delete(`/api/materials/${id}`),
};

export const purchasesAPI = {
  list: (params) => client.get('/api/purchases/', { params }),
  create: (data) => client.post('/api/purchases/', data),
  update: (id, data) => client.put(`/api/purchases/${id}`, data),
};

export const issuesAPI = {
  list: (params) => client.get('/api/issues/', { params }),
  create: (data) => client.post('/api/issues/', data),
};

export const clientsAPI = {
  list: (params) => client.get('/api/clients/', { params }),
  get: (id) => client.get(`/api/clients/${id}`),
  create: (data) => client.post('/api/clients/', data),
  update: (id, data) => client.put(`/api/clients/${id}`, data),
  remove: (id) => client.delete(`/api/clients/${id}`),
};

export const ordersAPI = {
  list: (params) => client.get('/api/orders/', { params }),
  get: (id) => client.get(`/api/orders/${id}`),
  create: (data) => client.post('/api/orders/', data),
  update: (id, data) => client.put(`/api/orders/${id}`, data),
  profitability: (id) => client.get(`/api/orders/${id}/profitability`),
};

export const paymentsAPI = {
  list: (params) => client.get('/api/payments/', { params }),
  create: (data) => client.post('/api/payments/', data),
};

export const projectExpensesAPI = {
  list: (params) => client.get('/api/project-expenses/', { params }),
  create: (data) => client.post('/api/project-expenses/', data),
  update: (id, data) => client.put(`/api/project-expenses/${id}`, data),
};

export const employeesAPI = {
  list: (params) => client.get('/api/employees/', { params }),
  get: (id) => client.get(`/api/employees/${id}`),
  create: (data) => client.post('/api/employees/', data),
  update: (id, data) => client.put(`/api/employees/${id}`, data),
  remove: (id) => client.delete(`/api/employees/${id}`),
};

export const attendanceAPI = {
  list: (params) => client.get('/api/attendance/', { params }),
  create: (data) => client.post('/api/attendance/', data),
  update: (id, data) => client.put(`/api/attendance/${id}`, data),
};

export const leavesAPI = {
  list: (params) => client.get('/api/leaves/', { params }),
  create: (data) => client.post('/api/leaves/', data),
  update: (id, data) => client.put(`/api/leaves/${id}`, data),
};

export const dailyTasksAPI = {
  list: (params) => client.get('/api/daily-tasks/', { params }),
  get: (id) => client.get(`/api/daily-tasks/${id}`),
  create: (data) => client.post('/api/daily-tasks/', data),
  update: (id, data) => client.put(`/api/daily-tasks/${id}`, data),
};

export const productionJobsAPI = {
  list: (params) => client.get('/api/production-jobs/', { params }),
  create: (data) => client.post('/api/production-jobs/', data),
  update: (id, data) => client.put(`/api/production-jobs/${id}`, data),
};

export const settingsAPI = {
  types: () => client.get('/api/settings/'),
  list: (lookupType) => client.get(`/api/settings/${lookupType}`),
  create: (lookupType, data) => client.post(`/api/settings/${lookupType}`, data),
  update: (lookupType, id, data) => client.put(`/api/settings/${lookupType}/${id}`, data),
  remove: (lookupType, id) => client.delete(`/api/settings/${lookupType}/${id}`),
};

export const estimatesAPI = {
  list: (params) => client.get('/api/estimates/', { params }),
  get: (id) => client.get(`/api/estimates/${id}`),
  create: (data) => client.post('/api/estimates/', data),
  update: (id, data) => client.put(`/api/estimates/${id}`, data),
  revise: (id) => client.post(`/api/estimates/${id}/revise`),
  versions: (id) => client.get(`/api/estimates/${id}/versions`),
};

export const clientActivitiesAPI = {
  list: (params) => client.get('/api/client-activities/', { params }),
  create: (data) => client.post('/api/client-activities/', data),
};

export const candidatesAPI = {
  list: (params) => client.get('/api/candidates/', { params }),
  get: (id) => client.get(`/api/candidates/${id}`),
  create: (data) => client.post('/api/candidates/', data),
  update: (id, data) => client.put(`/api/candidates/${id}`, data),
};

export const interviewsAPI = {
  list: (params) => client.get('/api/interviews/', { params }),
  create: (data) => client.post('/api/interviews/', data),
  update: (id, data) => client.put(`/api/interviews/${id}`, data),
};

export const salarySlipsAPI = {
  list: (params) => client.get('/api/salary-slips/', { params }),
  create: (data) => client.post('/api/salary-slips/', data),
  update: (id, data) => client.put(`/api/salary-slips/${id}`, data),
};

export const chatAPI = {
  send: (message, context) => client.post('/api/chat/', { message, context }),
};

export const usersAPI = {
  list: (params) => client.get('/api/users/', { params }),
  create: (data) => client.post('/api/users/', data),
  update: (id, data) => client.put(`/api/users/${id}`, data),
  remove: (id) => client.delete(`/api/users/${id}`),
};

export const auditLogsAPI = {
  list: (params) => client.get('/api/audit-logs/', { params }),
};

export const reportsAPI = {
  downloadUrl: (path) => `${API_URL}/api/reports/${path}`,
};

export default client;
