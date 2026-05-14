import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { hasPermission } from '@/auth/permissions'
import type { Permission } from '@/auth/permissions'

interface ProtectedRouteProps {
  children: React.ReactNode
  permission?: Permission
}

export default function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const location = useLocation()
  const { accessToken, roles } = useAuthStore()

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (permission && !hasPermission(roles.map((r) => r.role), permission)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <>{children}</>
}
