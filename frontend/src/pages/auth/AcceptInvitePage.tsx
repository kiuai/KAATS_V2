import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiClient, errorMessage } from '@/services/api'

interface InvitePublic {
  email: string
  role: string
  company_name: string
  expires_at: string
  is_valid: boolean
}

interface FormState {
  display_name: string
}

type PageState =
  | { phase: 'loading' }
  | { phase: 'invalid'; reason: string }
  | { phase: 'form'; invite: InvitePublic }
  | { phase: 'submitting'; invite: InvitePublic }
  | { phase: 'done'; email: string }
  | { phase: 'error'; message: string }

export default function AcceptInvitePage() {
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const token = search.get('token') ?? ''

  const [state, setState] = useState<PageState>({ phase: 'loading' })
  const [form, setForm] = useState<FormState>({ display_name: '' })

  useEffect(() => {
    if (!token) {
      setState({ phase: 'invalid', reason: 'No invitation token provided.' })
      return
    }
    apiClient
      .get<InvitePublic>(`/onboarding/invitations/${token}`)
      .then((res) => {
        if (!res.data.is_valid) {
          setState({
            phase: 'invalid',
            reason: 'This invitation has expired or already been used.',
          })
        } else {
          setState({ phase: 'form', invite: res.data })
        }
      })
      .catch(() => {
        setState({ phase: 'invalid', reason: 'Invitation not found.' })
      })
  }, [token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (state.phase !== 'form') return
    setState({ phase: 'submitting', invite: state.invite })

    try {
      await apiClient.post(`/onboarding/invitations/${token}/accept`, {
        display_name: form.display_name,
      })
      setState({ phase: 'done', email: state.invite.email })
    } catch (err) {
      setState({ phase: 'error', message: errorMessage(err) })
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (state.phase === 'loading') {
    return (
      <PageShell>
        <p className="text-gray-500 text-center mt-8">Validating invitation…</p>
      </PageShell>
    )
  }

  if (state.phase === 'invalid') {
    return (
      <PageShell>
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-600 font-medium">{state.reason}</p>
          <button
            onClick={() => navigate('/login')}
            className="mt-4 text-sm text-indigo-600 hover:underline"
          >
            Go to login
          </button>
        </div>
      </PageShell>
    )
  }

  if (state.phase === 'done') {
    return (
      <PageShell>
        <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
          <svg
            className="mx-auto mb-4 h-12 w-12 text-green-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Invitation accepted!</h2>
          <p className="text-gray-600 text-sm mb-6">
            Your account for <strong>{state.email}</strong> is ready.
          </p>
          <button
            onClick={() => navigate('/login')}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Sign in
          </button>
        </div>
      </PageShell>
    )
  }

  if (state.phase === 'error') {
    return (
      <PageShell>
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-600">{state.message}</p>
          <button
            onClick={() => setState({ phase: 'loading' })}
            className="mt-4 text-sm text-indigo-600 hover:underline"
          >
            Try again
          </button>
        </div>
      </PageShell>
    )
  }

  // form or submitting
  const invite = state.phase === 'form' ? state.invite : state.invite
  const isSubmitting = state.phase === 'submitting'
  const roleDisplay = invite.role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <PageShell>
      <div className="bg-white shadow-sm border border-gray-200 rounded-xl p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Accept your invitation</h1>
        <p className="text-gray-500 text-sm mb-6">
          You've been invited to join <strong>{invite.company_name}</strong> as a{' '}
          <strong>{roleDisplay}</strong>.
        </p>

        <div className="mb-6 bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-600">
          <span className="font-medium">Email:</span> {invite.email}
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 mb-1">
              Your name
            </label>
            <input
              id="display_name"
              type="text"
              required
              value={form.display_name}
              onChange={(e) => setForm({ display_name: e.target.value })}
              placeholder="Jane Smith"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !form.display_name.trim()}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Accepting…' : 'Accept invitation'}
          </button>
        </form>
      </div>
    </PageShell>
  )
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <span className="text-2xl font-bold text-indigo-700 tracking-tight">KAATS</span>
        </div>
        {children}
      </div>
    </div>
  )
}
