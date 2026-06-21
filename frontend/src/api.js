import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const repoApi = {
  list: (params = {}) => api.get('/repos/', { params }),
  get: (id) => api.get(`/repos/${id}`),
  create: (data) => api.post('/repos/', data),
  update: (id, data) => api.patch(`/repos/${id}`, data),
  remove: (id) => api.delete(`/repos/${id}`),
  tasks: (id, params = {}) => api.get(`/repos/${id}/tasks`, { params }),
}

export const taskApi = {
  list: (params = {}) => api.get('/tasks/', { params }),
  get: (id) => api.get(`/tasks/${id}`),
  logs: (id, params = {}) => api.get(`/tasks/${id}/logs`, { params }),
}

export const syncApi = {
  start: (data) => api.post('/sync/start', data),
  startSingle: (repoId) => api.post(`/sync/start/${repoId}`),
  status: () => api.get('/sync/status'),
}

export default api
