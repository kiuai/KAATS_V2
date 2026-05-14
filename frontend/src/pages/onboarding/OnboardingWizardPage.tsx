/**
 * OnboardingWizardPage — 4-step first-run experience for new companies.
 *
 * Steps:
 *   1. Company profile  (industry + default export format)
 *   2. Invite team      (send invite emails)
 *   3. First system     (redirect to system creation)
 *   4. First agent run  (redirect to agent start)
 *
 * The wizard reads /onboarding/status and skips already-completed steps.
 * It patches /onboarding/status as each step is confirmed.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorMessage } from '@/services/api'

interface OnboardingStatus {
  has_profile: boolean
  has_team_member: boolean
  has_system: boolean
  has_agent_run: boolean
  is_complete: boolean
}

interface InviteCreate {
  email: string
  role: string
}

// ── Step 1 payload ────────────────────────────────────────────────────────────

interface ProfileFormState {
  industry: string
  default_export_format: string
}

const EXPORT_FORMATS = [
  { value: 'playwright', label: 'Playwright (TypeScript)' },
  { value: 'selenium', label: 'Selenium (Python)' },
  { value: 'pytest', label: 'pytest' },
  { value: 'robot_framework', label: 'Robot Framework' },
  { value: 'gherkin', label: 'Gherkin / Cucumber' },
]

const ROLES = [
  { value: 'qa', label: 'QA Engineer' },
  { value: 'validation_lead', label: 'Validation Lead' },
  { value: 'validation_tester', label: 'Validation Tester' },
  { value: 'system_manager', label: 'System Manager' },
  { value: 'company_admin', label: 'Company Admin' },
  { value: 'bpo', label: 'BPO' },
]

// ── Step indicators ───────────────────────────────────────────────────────────

const STEP_LABELS = [
  'Company profile',
  'Invite team',
  'Create system',
  'Run agent',
]

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-colors ${
              i < current
                ? 'bg-indigo-600 border-indigo-600 text-white'
                : i === current
                ? 'border-indigo-600 text-indigo-600 bg-white'
                : 'border-gray-300 text-gray-400 bg-white'
            }`}
          >
            {i < current ? '✓' : i + 1}
          </div>
          {i < total - 1 && (
            <div
              className={`h-0.5 w-12 ${i < current ? 'bg-indigo-600' : 'bg-gray-200'}`}
            />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Step components ───────────────────────────────────────────────────────────

function Step1Profile({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<ProfileFormState>({
    industry: '',
    default_export_format: 'playwright',
  })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: async () => {
      // Update company settings (best-effort; don't block wizard on API shape)
      await apiClient.patch('/tenants/companies/me', form).catch(() => null)
      await apiClient.patch('/onboarding/status', { has_profile: true })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['onboarding-status'] })
      onDone()
    },
    onError: (err) => setError(errorMessage(err)),
  })

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Company profile</h2>
      <p className="text-sm text-gray-500 mb-6">
        Tell us a bit about your company so we can tailor the experience.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Industry</label>
          <input
            type="text"
            value={form.industry}
            onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
            placeholder="e.g. Financial Services, Life Sciences…"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Default test export format
          </label>
          <select
            value={form.default_export_format}
            onChange={(e) => setForm((f) => ({ ...f, default_export_format: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {EXPORT_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <WizardNav
        onNext={() => mutation.mutate()}
        nextLabel="Save & continue"
        isLoading={mutation.isPending}
      />
    </div>
  )
}

function Step2Invite({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('qa')
  const [sent, setSent] = useState<string[]>([])
  const [error, setError] = useState('')

  const inviteMutation = useMutation({
    mutationFn: (body: InviteCreate) => apiClient.post('/onboarding/invitations', body),
    onSuccess: (_, body) => {
      setSent((prev) => [...prev, body.email])
      setEmail('')
      setError('')
    },
    onError: (err) => setError(errorMessage(err)),
  })

  const doneMutation = useMutation({
    mutationFn: () => apiClient.patch('/onboarding/status', { has_team_member: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['onboarding-status'] })
      onDone()
    },
  })

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Invite your team</h2>
      <p className="text-sm text-gray-500 mb-6">
        Send email invitations to colleagues. You can skip this and invite later from Users.
      </p>

      <div className="flex gap-2 mb-3">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="colleague@company.com"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && email) {
              e.preventDefault()
              inviteMutation.mutate({ email, role })
            }
          }}
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="border border-gray-300 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button
          onClick={() => email && inviteMutation.mutate({ email, role })}
          disabled={!email || inviteMutation.isPending}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          Send
        </button>
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      {sent.length > 0 && (
        <ul className="mb-4 space-y-1">
          {sent.map((e) => (
            <li key={e} className="flex items-center gap-2 text-sm text-gray-600">
              <span className="text-green-500">✓</span> {e}
            </li>
          ))}
        </ul>
      )}

      <WizardNav
        onNext={() => doneMutation.mutate()}
        nextLabel={sent.length > 0 ? 'Continue' : 'Skip for now'}
        isLoading={doneMutation.isPending}
      />
    </div>
  )
}

function Step3System({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const skipMutation = useMutation({
    mutationFn: () => apiClient.patch('/onboarding/status', { has_system: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['onboarding-status'] })
      onDone()
    },
  })

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Create your first system</h2>
      <p className="text-sm text-gray-500 mb-6">
        A <em>system</em> represents the application you want to test — its URL, type, and
        credentials. Register one now to start crawling and generating scripts.
      </p>

      <button
        onClick={() => navigate('/systems/new')}
        className="w-full bg-indigo-600 text-white py-2.5 rounded-lg font-medium hover:bg-indigo-700 transition-colors mb-3"
      >
        Create system →
      </button>

      <button
        onClick={() => skipMutation.mutate()}
        disabled={skipMutation.isPending}
        className="w-full text-sm text-gray-500 hover:text-gray-700 py-2"
      >
        Skip for now
      </button>
    </div>
  )
}

function Step4Agent({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const skipMutation = useMutation({
    mutationFn: () => apiClient.patch('/onboarding/status', { has_agent_run: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['onboarding-status'] })
      onDone()
    },
  })

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Run your first agent</h2>
      <p className="text-sm text-gray-500 mb-6">
        Start a crawl agent to automatically discover pages and generate test requirements,
        or launch a generation agent to produce test scripts from existing requirements.
      </p>

      <button
        onClick={() => navigate('/agents/new')}
        className="w-full bg-indigo-600 text-white py-2.5 rounded-lg font-medium hover:bg-indigo-700 transition-colors mb-3"
      >
        Start an agent →
      </button>

      <button
        onClick={() => skipMutation.mutate()}
        disabled={skipMutation.isPending}
        className="w-full text-sm text-gray-500 hover:text-gray-700 py-2"
      >
        Skip for now
      </button>
    </div>
  )
}

function WizardNav({
  onNext,
  nextLabel,
  isLoading,
}: {
  onNext: () => void
  nextLabel: string
  isLoading: boolean
}) {
  return (
    <div className="mt-8 flex justify-end">
      <button
        onClick={onNext}
        disabled={isLoading}
        className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {isLoading ? '…' : nextLabel}
      </button>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OnboardingWizardPage() {
  const navigate = useNavigate()
  const { data: status } = useQuery<OnboardingStatus>({
    queryKey: ['onboarding-status'],
    queryFn: () => apiClient.get('/onboarding/status').then((r) => r.data),
  })

  // Start at the first incomplete step
  const firstIncomplete = (): number => {
    if (!status) return 0
    if (!status.has_profile) return 0
    if (!status.has_team_member) return 1
    if (!status.has_system) return 2
    if (!status.has_agent_run) return 3
    return 4
  }

  const [step, setStep] = useState<number>(() => firstIncomplete())

  function advance() {
    if (step >= 3) {
      navigate('/')
    } else {
      setStep((s) => s + 1)
    }
  }

  if (status?.is_complete) {
    navigate('/')
    return null
  }

  const stepComponents = [
    <Step1Profile onDone={advance} />,
    <Step2Invite onDone={advance} />,
    <Step3System onDone={advance} />,
    <Step4Agent onDone={advance} />,
  ]

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="flex justify-center mb-8">
          <span className="text-2xl font-bold text-indigo-700 tracking-tight">KAATS</span>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-8">
          <div className="mb-1 text-xs font-medium text-indigo-600 uppercase tracking-wider">
            {STEP_LABELS[step]}
          </div>
          <StepIndicator current={step} total={STEP_LABELS.length} />
          {stepComponents[step]}
        </div>
      </div>
    </div>
  )
}
