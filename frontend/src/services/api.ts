import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'
import type { ApiError } from '@/types'
import { useAuthStore } from '@/store/authStore'
import { msalInstance } from '@/auth/msalInstance'

const runtimeConfig = (window as { __KAATS_CONFIG__?: Record<string, string> }).__KAATS_CONFIG__ ?? {}
const BASE_URL =
  (runtimeConfig.API_URL !== 'VITE_API_URL_PLACEHOLDER' ? runtimeConfig.API_URL : '') ||
  import.meta.env.VITE_API_URL ||
  '/api/v1'

// ── Axios instance ────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ── Request interceptors ──────────────────────────────────────────────────

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Read token directly from Zustand store (the token lives in store memory,
  // persisted to localStorage['kaats-auth'] — NOT to localStorage['kaats_access_token']).
  const { accessToken, currentCompany } = useAuthStore.getState()

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }

  if (currentCompany?.slug) {
    config.headers['X-Company-Slug'] = currentCompany.slug
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

    // On 401: clear auth state then navigate to login.
    // IMPORTANT: We must also clear the MSAL cache so that MSAL cannot silently
    // re-acquire a token on the next page load.  Without this, MSAL's
    // ACQUIRE_TOKEN_SUCCESS event would repopulate accessToken in the Zustand
    // store, causing LoginPage.useEffect to bounce the user straight back to the
    // protected page — creating an infinite redirect loop.
    if (status === 401) {
      useAuthStore.getState().clearAuth()
      // Await clearCache() so sessionStorage is wiped BEFORE the new page loads.
      // Without this, MSAL can silently re-acquire a token on the /login reload,
      // which would cause LoginPage to immediately bounce back to the protected
      // page and create an infinite redirect loop.
      msalInstance.clearCache().finally(() => {
        window.location.replace('/login')
      })
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
