import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { msalInstance } from '@/auth/AuthProvider'

export default function CallbackPage() {
  const navigate = useNavigate()

  useEffect(() => {
    msalInstance
      .handleRedirectPromise()
      .then(() => {
        navigate('/dashboard', { replace: true })
      })
      .catch(() => {
        // If the redirect promise fails, send back to login
        navigate('/login', { replace: true })
      })
  }, [navigate])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        {/* Spinner */}
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
