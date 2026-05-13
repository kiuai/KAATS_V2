import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import apiClient from '@/services/api'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setAuth = useAuthStore((s) => s.setAuth)
  const navigate = useNavigate()

  const handleDevLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      // Development-only: exchange a dummy code for a token
      const { data } = await apiClient.post('/auth/callback', {
        code: 'dev',
        redirect_uri: window.location.origin,
      })
      setAuth(data.access_token, 'dev-user', 'dev-company', ['qa_engineer'])
      navigate('/dashboard')
    } catch (err: unknown) {
      setError('Login failed. Check the API is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">KAATS</h1>
          <p className="mt-2 text-sm text-gray-500">KIU AI Agentic Test System</p>
        </div>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
            {error}
          </div>
        )}
        <button
          onClick={handleDevLogin}
          disabled={loading}
          className="w-full py-2.5 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Signing in...' : 'Sign in with Microsoft Entra ID'}
        </button>
      </div>
    </div>
  )
}
