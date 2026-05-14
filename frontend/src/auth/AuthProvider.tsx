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
import type { Company, UserRole } from '@/types'

// ── MSAL instance (singleton) ─────────────────────────────────────────────

export const msalInstance = new PublicClientApplication(msalConfig)

// Set active account on login events
msalInstance.addEventCallback((event) => {
  if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
    const payload = event.payload as AuthenticationResult
    msalInstance.setActiveAccount(payload.account)
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
  const { instance, accounts } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const { setMsalToken, currentCompany, user, roles } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated || accounts.length === 0) {
      setIsLoading(false)
      return
    }

    instance
      .acquireTokenSilent({
        ...loginRequest,
        account: accounts[0] as AccountInfo,
      })
      .then((response) => {
        setMsalToken(response.accessToken, accounts[0] as AccountInfo)
      })
      .catch(() => {
        // Silent token acquisition failed — require re-login
        instance.logoutRedirect()
      })
      .finally(() => setIsLoading(false))
  }, [isAuthenticated, accounts, instance, setMsalToken])

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
