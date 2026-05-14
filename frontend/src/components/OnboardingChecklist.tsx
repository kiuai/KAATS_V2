import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorMessage } from '@/services/api'
import { Link } from 'react-router-dom'

interface OnboardingStatus {
  company_id: string
  has_profile: boolean
  has_team_member: boolean
  has_system: boolean
  has_agent_run: boolean
  is_complete: boolean
  completed_at: string | null
}

interface Step {
  key: keyof Pick<
    OnboardingStatus,
    'has_profile' | 'has_team_member' | 'has_system' | 'has_agent_run'
  >
  label: string
  description: string
  href: string
}

const STEPS: Step[] = [
  {
    key: 'has_profile',
    label: 'Complete company profile',
    description: 'Add industry and default export settings',
    href: '/settings/company',
  },
  {
    key: 'has_team_member',
    label: 'Invite a team member',
    description: 'Send your first invitation',
    href: '/admin/users',
  },
  {
    key: 'has_system',
    label: 'Create your first system',
    description: 'Register the application under test',
    href: '/systems/new',
  },
  {
    key: 'has_agent_run',
    label: 'Run your first agent',
    description: 'Trigger a crawl or generation agent',
    href: '/agents/new',
  },
]

export default function OnboardingChecklist() {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<OnboardingStatus>({
    queryKey: ['onboarding-status'],
    queryFn: () => apiClient.get('/onboarding/status').then((r) => r.data),
    staleTime: 30_000,
  })

  const dismissMutation = useMutation({
    mutationFn: () =>
      apiClient
        .patch('/onboarding/status', {
          has_profile: true,
          has_team_member: true,
          has_system: true,
          has_agent_run: true,
        })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['onboarding-status'] }),
  })

  if (isLoading || !data) return null
  if (data.is_complete) return null

  const completedCount = STEPS.filter((s) => data[s.key]).length
  const pct = Math.round((completedCount / STEPS.length) * 100)

  return (
    <aside className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 w-full">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Getting started</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {completedCount} of {STEPS.length} steps complete
          </p>
        </div>
        <button
          onClick={() => dismissMutation.mutate()}
          className="text-xs text-gray-400 hover:text-gray-600"
          title="Dismiss"
        >
          ✕
        </button>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5 mb-4">
        <div
          className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Steps */}
      <ul className="space-y-2">
        {STEPS.map((step) => {
          const done = data[step.key]
          return (
            <li key={step.key} className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex-shrink-0 h-4 w-4 rounded-full flex items-center justify-center text-xs ${
                  done
                    ? 'bg-green-500 text-white'
                    : 'border-2 border-gray-300 text-transparent'
                }`}
              >
                {done && '✓'}
              </span>
              <div className="min-w-0">
                {done ? (
                  <p className="text-xs font-medium text-gray-400 line-through">
                    {step.label}
                  </p>
                ) : (
                  <Link
                    to={step.href}
                    className="text-xs font-medium text-indigo-600 hover:underline block"
                  >
                    {step.label}
                  </Link>
                )}
                {!done && (
                  <p className="text-xs text-gray-400 mt-0.5">{step.description}</p>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}
