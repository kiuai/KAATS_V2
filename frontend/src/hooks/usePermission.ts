import { useAuthStore } from '@/store/authStore'
import { hasPermission, type Permission } from '@/auth/permissions'
import type { UserRoleEnum } from '@/types'

export function usePermission(permission: Permission): boolean {
  const roles = useAuthStore((s) => s.roleValues())
  return hasPermission(roles as UserRoleEnum[], permission)
}

export function useHasRole(...requiredRoles: UserRoleEnum[]): boolean {
  const hasRole = useAuthStore((s) => s.hasRole)
  return hasRole(...requiredRoles)
}
