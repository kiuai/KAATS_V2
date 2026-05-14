import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AccountInfo } from '@azure/msal-browser'
import type { Company, User, UserRole, UserRoleEnum } from '@/types'

interface AuthState {
  // Token
  accessToken: string | null
  // User profile (fetched from /users/me after login)
  user: User | null
  // Roles from backend UserRole records
  roles: UserRole[]
  // Active company tenant (stored in X-Company-Slug header)
  currentCompany: Company | null
  // Available companies for this user
  companies: Company[]

  // Actions
  setMsalToken: (token: string, account: AccountInfo) => void
  setDevAuth: (token: string, user: User, roles: UserRole[], company: Company) => void
  setUser: (user: User) => void
  setRoles: (roles: UserRole[]) => void
  setCurrentCompany: (company: Company) => void
  setCompanies: (companies: Company[]) => void
  clearAuth: () => void

  // Computed helpers
  isAuthenticated: () => boolean
  hasRole: (...roles: UserRoleEnum[]) => boolean
  roleValues: () => UserRoleEnum[]
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,
      roles: [],
      currentCompany: null,
      companies: [],

      setMsalToken: (token, account) => {
        set({
          accessToken: token,
          user: (get().user ?? {
            id: account.localAccountId,
            email: account.username,
            display_name: account.name ?? null,
            azure_oid: account.localAccountId,
            is_active: true,
            is_global_admin: false,
            last_login_at: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }) as User,
        })
      },

      setDevAuth: (token, user, roles, company) => {
        set({ accessToken: token, user, roles, currentCompany: company })
      },

      setUser: (user) => set({ user }),
      setRoles: (roles) => set({ roles }),
      setCurrentCompany: (company) => set({ currentCompany: company }),
      setCompanies: (companies) => set({ companies }),

      clearAuth: () => {
        set({ accessToken: null, user: null, roles: [], currentCompany: null, companies: [] })
      },

      isAuthenticated: () => get().accessToken !== null,

      hasRole: (...requiredRoles) => {
        const userRoles = get().roles.map((r) => r.role)
        return requiredRoles.some((r) => userRoles.includes(r))
      },

      roleValues: () => get().roles.map((r) => r.role),
    }),
    {
      name: 'kaats-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
        roles: state.roles,
        currentCompany: state.currentCompany,
        companies: state.companies,
      }),
    },
  ),
)
