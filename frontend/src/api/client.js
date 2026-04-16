import axios from 'axios';

const BASE_URL = '/api/v1';

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Inject JWT on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('aml_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Global 401 handler → redirect to login
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('aml_token');
      localStorage.removeItem('aml_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default client;

// ---- API Methods ----

export const authAPI = {
  login: (data) => client.post('/auth/login', data),
  sendVerification: (email) => client.post('/auth/send-verification', { email }),
  register: (data) => client.post('/auth/register', data),
  me: () => client.get('/auth/me'),
  logout: () => client.post('/auth/logout'),
  getUsers: () => client.get('/auth/users'),
  createUser: (data) => client.post('/auth/users', data),
  updateProfile: (data) => client.put('/auth/profile', data),
  sendPasswordReset: () => client.post('/auth/send-password-reset', {}),
  changePassword: (data) => client.put('/auth/change-password', data),
};

export const dashboardAPI = {
  get: () => client.get('/dashboard'),
};

export const customersAPI = {
  list: (params) => client.get('/customers', { params }),
  get: (id) => client.get(`/customers/${id}`),
  create: (data) => client.post('/customers', data),
  update: (id, data) => client.put(`/customers/${id}`, data),
  getAccounts: (id) => client.get(`/customers/${id}/accounts`),
  createAccount: (data) => client.post('/customers/accounts', data),
};

export const transactionsAPI = {
  list: (params) => client.get('/transactions', { params }),
  get: (id) => client.get(`/transactions/${id}`),
  create: (data) => client.post('/transactions', data),
};

export const alertsAPI = {
  list: (params) => client.get('/alerts', { params }),
  get: (id) => client.get(`/alerts/${id}`),
  update: (id, data) => client.put(`/alerts/${id}`, data),
  stats: () => client.get('/alerts/stats'),
  markAllRead: () => client.put('/alerts/mark-all-read'),
};

export const casesAPI = {
  list: (params) => client.get('/cases', { params }),
  get: (id) => client.get(`/cases/${id}`),
  create: (data) => client.post('/cases', data),
  update: (id, data) => client.put(`/cases/${id}`, data),
  getNotes: (id) => client.get(`/cases/${id}/notes`),
  addNote: (id, data) => client.post(`/cases/${id}/notes`, data),
  getAiSummary: (id) => client.get(`/cases/${id}/ai-summary`),
};

export const riskScoringAPI = {
  allScores: () => client.get('/risk-scoring/customers'),
  customerScore: (id) => client.get(`/risk-scoring/customers/${id}`),
  predictRisk: (id) => client.get(`/risk-scoring/customers/${id}/predict`),
};

export const sanctionsAPI = {
  search: (data) => client.post('/sanctions/search', data),
  stats: () => client.get('/sanctions/stats'),
  listEntries: (params) => client.get('/sanctions/entries', { params }),
};

export const rulesAPI = {
  list: () => client.get('/rules'),
  create: (data) => client.post('/rules', data),
  update: (id, data) => client.put(`/rules/${id}`, data),
  toggle: (id) => client.patch(`/rules/${id}/toggle`),
};

export const auditAPI = {
  list: (params) => client.get('/audit', { params }),
  actions: () => client.get('/audit/actions'),
};

export const chatAPI = {
  send: (message, history) => client.post('/demo/chat', { message, history }),
};

export const blacklistAPI = {
  list:    (params) => client.get('/blacklist', { params }),
  stats:   ()       => client.get('/blacklist/stats'),
  create:  (data)   => client.post('/blacklist', data),
  move:    (id, data) => client.put(`/blacklist/${id}/move`, data),
  history: (id)     => client.get(`/blacklist/${id}/history`),
  remove:  (id)     => client.delete(`/blacklist/${id}`),
};
