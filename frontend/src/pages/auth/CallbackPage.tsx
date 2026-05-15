import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import { loginRequest } from '@/auth/msalConfig'
import { useAuthStore } from '@/store/authStore'

export default function CallbackPage() {
  const navigate = useNavigate()
  const { instance, inProgress, accounts } = useMsal()
  const setMsalToken = useAuthStore((s) => s.setMsalToken)
  const attempted = useRef(false)

  useEffect(() => {
    // Wait for MsalProvider to finish handling the redirect internally
    if (inProgress !== InteractionStatus.None) return
    // Only attempt once
    if (attempted.current) return
    attempted.current = true

    const account = accounts[0] ?? instance.getActiveAccount() ?? null

    if (!account) {
      navigate('/login', { replace: true })
      return
    }

    instance.setActiveAccount(account)

    instance
      .acquireTokenSilent({ ...loginRequest, account })
      .then((result) => {
        setMsalToken(result.accessToken, account)
        navigate('/dashboard', { replace: true })
      })
      .catch(() => {
        // Silent acquisition failed — trigger interactive login again
        instance.loginRedirect(loginRequest)
      })
  }, [inProgress, accounts, instance, navigate, setMsalToken])

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
