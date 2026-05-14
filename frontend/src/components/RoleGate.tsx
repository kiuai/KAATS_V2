import { usePermission } from '@/hooks/usePermission'
import type { Permission } from '@/auth/permissions'

interface RoleGateProps {
  permission: Permission
  children: React.ReactNode
  fallback?: React.ReactNode
}

export default function RoleGate({ permission, children, fallback = null }: RoleGateProps) {
  const allowed = usePermission(permission)
  return allowed ? <>{children}</> : <>{fallback}</>
}
