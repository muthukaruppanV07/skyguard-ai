import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export const stationsApi = {
  list: () => api.get('/stations'),
  get: (id) => api.get(`/stations/${id}`),
}

export const readingsApi = {
  list: (params) => api.get('/readings', { params }),
}

export const anomaliesApi = {
  list: (params) => api.get('/anomalies', { params }),
  get: (id) => api.get(`/anomalies/${id}`),
}

export const healthApi = {
  network: () => api.get('/health'),
  station: (id) => api.get(`/health/${id}`),
}

export const statisticsApi = {
  get: (hours = 24) => api.get('/statistics', { params: { hours } }),
}

export const simulationApi = {
  inject: (data) => api.post('/simulate/anomaly', data),
  reset: () => api.post('/simulate/reset'),
  advancedAction: (action) => api.post('/simulate/advanced', { action }),
}

export const detectionApi = {
  trigger: () => api.post('/detect'),
}

export const explainApi = {
  get: (id) => api.get(`/explanation/${id}`),
}

export const modelsApi = {
  list: () => api.get('/models'),
}

export default api