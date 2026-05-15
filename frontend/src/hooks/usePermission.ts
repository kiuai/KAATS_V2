import { useAuthStore } from '@/store/authStore'
import { hasPermission, type Permission } from '@/auth/permissions'
import type { UserRoleEnum } from '@/types'

export function usePermission(permission: Permission): boolean {
  const isGlobalAdmin = useAuthStore((s) => s.user?.is_global_admin ?? false)
  const roles = useAuthStore((s) => s.roleValues())
  // Global admins hold every permission without needing explicit UserRole records.
  if (isGlobalAdmin) return true
  return hasPermission(roles as UserRoleEnum[], permission)
}

export function useHasRole(...requiredRoles: UserRoleEnum[]): boolean {
  const hasRole = useAuthStore((s) => s.hasRole)
  return hasRole(...requiredRoles)
}
