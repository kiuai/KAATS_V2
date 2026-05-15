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
import type { Company, User, UserRole } from '@/types'

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

// Shape returned by GET /auth/me
interface MeOut {
  user_id: string
  email: string
  display_name: string | null
  is_global_admin: boolean
  roles: Array<{
    id: string
    role: string
    enterprise_id: string | null
    company_id: string | null
    system_id: string | null
    business_domain: string | null
    expires_at: string | null
  }>
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
  isGlobalAdmin: boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthenticatedUser>({
  id: '',
  email: '',
  displayName: null,
  roles: [],
  currentCompany: null,
  isGlobalAdmin: false,
  isLoading: true,
})

export function useAuthenticatedUser(): AuthenticatedUser {
  return useContext(AuthContext)
}

// ── Inner provider (needs MsalProvider above it) ──────────────────────────

function InnerAuthProvider({ children }: { children: React.ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const { setMsalToken, setUser, setRoles, setCompanies, setCurrentCompany, currentCompany, user, roles } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
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
        // 2. Fetch user profile and accessible companies in parallel
        return Promise.all([
          apiClient.get<MeOut>('/auth/me'),
          apiClient.get<CompanyOut[]>('/auth/companies'),
        ]).then(([meRes, companiesRes]) => {
          const me = meRes.data

          // Hydrate full user profile (is_global_admin, real DB id, roles)
          const fullUser: User = {
            id: me.user_id,
            email: me.email,
            display_name: me.display_name,
            azure_oid: account.localAccountId,
            is_active: true,
            is_global_admin: me.is_global_admin,
            last_login_at: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }
          setUser(fullUser)

          const mappedRoles: UserRole[] = me.roles.map((r) => ({
            id: r.id,
            user_id: me.user_id,
            role: r.role as UserRole['role'],
            enterprise_id: r.enterprise_id,
            company_id: r.company_id,
            system_id: r.system_id,
            business_domain: r.business_domain,
            granted_by: null,
            expires_at: r.expires_at,
            created_at: new Date().toISOString(),
          }))
          setRoles(mappedRoles)

          const cos: Company[] = companiesRes.data.map((c) => ({
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

          // Only auto-select a company if not already set and there's exactly one
          // (or user is not a global admin). Global admins pick via the company switcher.
          if (!useAuthStore.getState().currentCompany && cos.length > 0 && !me.is_global_admin) {
            setCurrentCompany(cos[0])
          }
          if (!useAuthStore.getState().currentCompany && cos.length === 1) {
            setCurrentCompany(cos[0])
          }
        })
      })
      .catch(() => {
        // Bootstrap failed — user can still navigate; pages will show errors
      })
      .finally(() => setIsLoading(false))
  }, [isAuthenticated, accounts, inProgress, instance, setMsalToken, setUser, setRoles, setCompanies, setCurrentCompany])

  return (
    <AuthContext.Provider
      value={{
        id: user?.id ?? '',
        email: user?.email ?? (accounts[0]?.username ?? ''),
        displayName: user?.display_name ?? (accounts[0]?.name ?? null),
        roles: roles,
        currentCompany: currentCompany,
        isGlobalAdmin: user?.is_global_admin ?? false,
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
        isGlobalAdmin: user?.is_global_admin ?? false,
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
