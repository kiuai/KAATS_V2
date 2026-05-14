import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { apiClient, errorMessage } from '@/services/api'
import { msalInstance } from '@/auth/AuthProvider'
import { loginRequest, isDev } from '@/auth/msalConfig'
import type { User, UserRole, Company } from '@/types'

interface DevAuthResponse {
  access_token: string
  user: {
    id: string
    email: string
    display_name: string
  }
  roles: Array<{
    id: string
    user_id: string
    role: UserRole['role']
    company_id: string | null
    enterprise_id: string | null
    system_id: string | null
    business_domain: string | null
    granted_by: string | null
    expires_at: string | null
    created_at: string
  }>
  company: {
    id: string
    name: string
    slug: string
    enterprise_id: string
    industry: string | null
    default_export_format: string
    is_active: boolean
    is_deleted: boolean
    settings: Record<string, unknown> | null
    created_at: string
    updated_at: string
  }
}

export default function LoginPage() {
  const navigate = useNavigate()
  const setDevAuth = useAuthStore((s) => s.setDevAuth)
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function handleDevLogin() {
    setLoading(true)
    setErrorMsg(null)
    try {
      const { data } = await apiClient.post<DevAuthResponse>('/auth/callback', {
        code: 'dev',
        redirect_uri: window.location.origin,
      })

      const user: User = {
        id: data.user.id,
        email: data.user.email,
        display_name: data.user.display_name,
        azure_oid: null,
        is_active: true,
        is_global_admin: false,
        last_login_at: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }

      const roles: UserRole[] = data.roles.map((r) => ({
        id: r.id,
        user_id: r.user_id,
        enterprise_id: r.enterprise_id,
        company_id: r.company_id,
        system_id: r.system_id,
        role: r.role,
        business_domain: r.business_domain,
        granted_by: r.granted_by,
        expires_at: r.expires_at,
        created_at: r.created_at,
      }))

      const company: Company = {
        id: data.company.id,
        enterprise_id: data.company.enterprise_id,
        name: data.company.name,
        slug: data.company.slug,
        industry: data.company.industry,
        default_export_format: data.company.default_export_format,
        is_active: data.company.is_active,
        is_deleted: data.company.is_deleted,
        settings: data.company.settings,
        created_at: data.company.created_at,
        updated_at: data.company.updated_at,
      }

      localStorage.setItem('kaats_access_token', data.access_token)
      setDevAuth(data.access_token, user, roles, company)
      navigate('/dashboard')
    } catch (err) {
      setErrorMsg(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  function handleMsalLogin() {
    msalInstance.loginRedirect(loginRequest)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Branding */}
        <div className="text-center mb-8">
          <span className="text-5xl font-extrabold tracking-tight text-blue-600">KAATS</span>
          <p className="mt-2 text-sm font-medium text-gray-500 tracking-widest uppercase">
            KIU AI Automated Test System
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-1">Sign in</h1>
          <p className="text-sm text-gray-500 mb-6">Access your testing workspace</p>

          {errorMsg && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {errorMsg}
            </div>
          )}

          {isDev ? (
            <button
              onClick={handleDevLogin}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium rounded-xl transition-colors"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4 text-white"
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
                  Signing in…
                </>
              ) : (
                'Sign in (Dev)'
              )}
            </button>
          ) : (
            <button
              onClick={handleMsalLogin}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl transition-colors shadow-sm"
            >
              {/* Microsoft logo */}
              <svg
                width="18"
                height="18"
                viewBox="0 0 21 21"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
              Sign in with Microsoft
            </button>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          © {new Date().getFullYear()} KIU AI — KAATS Platform
        </p>
      </div>
    </div>
  )
}
