import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  accessToken: string | null
  userId: string | null
  companyId: string | null
  roles: string[]
  setAuth: (token: string, userId: string, companyId: string, roles: string[]) => void
  clearAuth: () => void
  isAuthenticated: () => boolean
  hasRole: (...roles: string[]) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      userId: null,
      companyId: null,
      roles: [],

      setAuth: (token, userId, companyId, roles) => {
        localStorage.setItem('kaats_access_token', token)
        set({ accessToken: token, userId, companyId, roles })
      },

      clearAuth: () => {
        localStorage.removeItem('kaats_access_token')
        set({ accessToken: null, userId: null, companyId: null, roles: [] })
      },

      isAuthenticated: () => get().accessToken !== null,

      hasRole: (...roles) => {
        const userRoles = get().roles
        return roles.some((r) => userRoles.includes(r))
      },
    }),
    { name: 'kaats-auth' },
  ),
)
