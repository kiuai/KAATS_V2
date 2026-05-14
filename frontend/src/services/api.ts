import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'
import type { ApiError } from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

// ── Axios instance ────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ── Request interceptors ──────────────────────────────────────────────────

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Bearer token — pulled fresh each request so MSAL token refresh is transparent
  const token = localStorage.getItem('kaats_access_token')
    ?? sessionStorage.getItem('kaats_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // Company tenant context
  try {
    const raw = localStorage.getItem('kaats-auth')
    if (raw) {
      const parsed = JSON.parse(raw) as { state?: { currentCompany?: { slug?: string } } }
      const slug = parsed?.state?.currentCompany?.slug
      if (slug) {
        config.headers['X-Company-Slug'] = slug
      }
    }
  } catch {
    // ignore parse errors
  }

  // Correlation ID for distributed tracing
  config.headers['X-Request-ID'] = crypto.randomUUID()

  return config
})

// ── Response interceptors ─────────────────────────────────────────────────

let _retryCount = 0

apiClient.interceptors.response.use(
  (response) => {
    _retryCount = 0
    return response
  },
  async (error: AxiosError) => {
    const status = error.response?.status

    // Auto-redirect on 401
    if (status === 401) {
      localStorage.removeItem('kaats_access_token')
      sessionStorage.removeItem('kaats_access_token')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // Retry on 429 with exponential backoff (max 3 attempts)
    if (status === 429 && _retryCount < 3) {
      _retryCount++
      const retryAfter = Number(error.response?.headers['retry-after'] ?? 1)
      const delay = (retryAfter || _retryCount) * 1000
      await new Promise((res) => setTimeout(res, delay))
      return apiClient(error.config!)
    }

    _retryCount = 0
    return Promise.reject(normalizeError(error))
  },
)

// ── Error normalisation ───────────────────────────────────────────────────

export function normalizeError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Partial<ApiError> | undefined
    return {
      error: {
        code: String(error.response?.status ?? 'NETWORK_ERROR'),
        message:
          (data?.error?.message as string | undefined) ??
          error.message ??
          'An unexpected error occurred',
        details: (data?.error?.details as Record<string, unknown> | null | undefined) ?? null,
        request_id:
          (error.response?.headers['x-request-id'] as string | undefined) ?? null,
      },
    }
  }
  return {
    error: {
      code: 'UNKNOWN',
      message: error instanceof Error ? error.message : 'An unexpected error occurred',
      details: null,
      request_id: null,
    },
  }
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Partial<ApiError> | undefined
    return (
      (data?.error?.message as string | undefined) ??
      error.message ??
      'An unexpected error occurred'
    )
  }
  return error instanceof Error ? error.message : 'An unexpected error occurred'
}

export default apiClient
