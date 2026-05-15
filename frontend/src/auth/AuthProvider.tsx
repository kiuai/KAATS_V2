import React, { createContext, useContext, useEffect, useState } from 'react'
import {
  PublicClientApplication,
  EventType,
  type AccountInfo,
  type AuthenticationResult,
} from '@azure/msal-browser'
import { MsalProvider, useMsal, useIsAuthenticated } from '@azure/msal-react'
import { msalConfig, loginRequest, isDev } from './msalConfig'
import { useAuthStore } from '@/store/authStore'
import { apiClient } from '@/services/api'
import type { Company, UserRole } from '@/types'

// Shape returned by GET /auth/companies
interface CompanyOut {
  id: string
  name: string
  slug: string
  enterprise_id: string
  industry: string | null
  default_export_format: string
  is_active: boolean
  is_deleted: boolean
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

// ── MSAL instance (singleton) ─────────────────────────────────────────────

export const msalInstance = new PublicClientApplication(msalConfig)

// Set active account and store token on login events.
// LOGIN_SUCCESS fires during handleRedirectPromise (inside MsalProvider.initialize)
// and carries the full AuthenticationResult including accessToken.
msalInstance.addEventCallback((event) => {
  if (
    (event.eventType === EventType.LOGIN_SUCCESS ||
      event.eventType === EventType.ACQUIRE_TOKEN_SUCCESS) &&
    event.payload
  ) {
    const payload = event.payload as AuthenticationResult
    msalInstance.setActiveAccount(payload.account)
    // accessToken may be empty for OIDC-only scope requests; fall back to idToken
    const token = payload.accessToken || payload.idToken
    if (token && payload.account) {
      useAuthStore.getState().setMsalToken(token, payload.account)
    }
  }
})

// ── Auth context ──────────────────────────────────────────────────────────

interface AuthenticatedUser {
  id: string
  email: string
  displayName: string | null
  roles: UserRole[]
  currentCompany: Company | null
  isLoading: boolean
}

const AuthContext = createContext<AuthenticatedUser>({
  id: '',
  email: '',
  displayName: null,
  roles: [],
  currentCompany: null,
  isLoading: true,
})

export function useAuthenticatedUser(): AuthenticatedUser {
  return useContext(AuthContext)
}

// ── Inner provider (needs MsalProvider above it) ──────────────────────────

function InnerAuthProvider({ children }: { children: React.ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const { setMsalToken, setCompanies, setCurrentCompany, currentCompany, user, roles } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Wait for MSAL to finish its startup/redirect processing before deciding.
    // If we call setIsLoading(false) too early the CallbackPage navigates before
    // companies have been fetched, sending unauthenticated API requests.
    if (inProgress === 'startup' || inProgress === 'handleRedirect') return

    if (!isAuthenticated || accounts.length === 0) {
      setIsLoading(false)
      return
    }

    const account = accounts[0] as AccountInfo

    // 1. Ensure we have a token in the store
    const ensureToken = useAuthStore.getState().accessToken
      ? Promise.resolve(useAuthStore.getState().accessToken!)
      : instance
          .acquireTokenSilent({ ...loginRequest, account })
          .then((r) => {
            const tok = r.accessToken || r.idToken
            if (tok) setMsalToken(tok, account)
            return tok
          })
          .catch(() => useAuthStore.getState().accessToken ?? null)

    ensureToken
      .then((token) => {
        if (!token) return
        // 2. Fetch accessible companies — sets X-Company-Slug context for subsequent calls
        return apiClient.get<CompanyOut[]>('/auth/companies').then((r) => {
          const cos: Company[] = r.data.map((c) => ({
            id: c.id,
            name: c.name,
            slug: c.slug,
            enterprise_id: c.enterprise_id,
            industry: c.industry,
            default_export_format: c.default_export_format,
            is_active: c.is_active,
            is_deleted: c.is_deleted,
            settings: c.settings,
            created_at: c.created_at,
            updated_at: c.updated_at,
          }))
          setCompanies(cos)
          // Only set currentCompany if not already set (e.g., persisted from last session)
          if (!useAuthStore.getState().currentCompany && cos.length > 0) {
            setCurrentCompany(cos[0])
          }
        })
      })
      .catch(() => {
        // Companies fetch failed — user can still navigate; dashboard will show errors
      })
      .finally(() => setIsLoading(false))
  }, [isAuthenticated, accounts, instance, setMsalToken, setCompanies, setCurrentCompany])

  return (
    <AuthContext.Provider
      value={{
        id: user?.id ?? '',
        email: user?.email ?? (accounts[0]?.username ?? ''),
        displayName: user?.display_name ?? (accounts[0]?.name ?? null),
        roles: roles,
        currentCompany: currentCompany,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ── Dev fallback provider (no MSAL) ──────────────────────────────────────

function DevAuthProvider({ children }: { children: React.ReactNode }) {
  const { currentCompany, user, roles } = useAuthStore()

  return (
    <AuthContext.Provider
      value={{
        id: user?.id ?? 'dev-user',
        email: user?.email ?? 'dev@kaats.local',
        displayName: user?.display_name ?? 'Dev User',
        roles: roles,
        currentCompany: currentCompany,
        isLoading: false,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ── Exported provider ─────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  if (isDev) {
    return <DevAuthProvider>{children}</DevAuthProvider>
  }

  return (
    <MsalProvider instance={msalInstance}>
      <InnerAuthProvider>{children}</InnerAuthProvider>
    </MsalProvider>
  )
}
