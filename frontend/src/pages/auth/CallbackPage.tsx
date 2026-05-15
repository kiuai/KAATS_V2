import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import { useAuthStore } from '@/store/authStore'
import { useAuthenticatedUser } from '@/auth/AuthProvider'

export default function CallbackPage() {
  const navigate = useNavigate()
  const { inProgress } = useMsal()
  const accessToken = useAuthStore((s) => s.accessToken)
  // isLoading becomes false only after InnerAuthProvider finishes fetching
  // companies — so currentCompany is guaranteed to be set before we navigate.
  const { isLoading } = useAuthenticatedUser()

  // Navigate once the token is set AND the post-login bootstrap has completed.
  // Global admins land on /admin (no mandatory company context).
  // Everyone else lands on /dashboard.
  useEffect(() => {
    if (accessToken && !isLoading) {
      const { user, currentCompany } = useAuthStore.getState()
      const dest = (user?.is_global_admin && !currentCompany) ? '/admin' : '/dashboard'
      navigate(dest, { replace: true })
    }
  }, [accessToken, isLoading, navigate])

  // Safety-valve: if MSAL finishes with no token after 10 s, fall back to login.
  useEffect(() => {
    if (inProgress !== InteractionStatus.None) return

    const timer = setTimeout(() => {
      if (!useAuthStore.getState().isAuthenticated()) {
        navigate('/login', { replace: true })
      }
    }, 10_000)

    return () => clearTimeout(timer)
  }, [inProgress, navigate])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <svg
          className="animate-spin h-10 w-10 text-blue-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
        <p className="text-sm font-medium text-gray-600">Completing sign in…</p>
        <p className="text-xs text-gray-400">You will be redirected automatically.</p>
      </div>
    </div>
  )
}
