import axios, { type AxiosInstance } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('kaats_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('kaats_access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default apiClient
