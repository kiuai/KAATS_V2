import { useEffect } from 'react'
import { useParams, Link, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorMessage } from '@/services/api'
import { useSystemContext } from '@/contexts/SystemContext'
import type { SystemDetail, UserRole, User } from '@/types'

// ── types ─────────────────────────────────────────────────────────────────

interface TeamMember {
  user: User
  role: UserRole
  business_domain: string | null
}

// ── helpers ───────────────────────────────────────────────────────────────

function typeBadgeClass(type: string): string {
  switch (type) {
    case 'web':       return 'bg-blue-100 text-blue-700'
    case 'sap_fiori': return 'bg-orange-100 text-orange-700'
    case 'api':       return 'bg-purple-100 text-purple-700'
    default:          return 'bg-gray-100 text-gray-600'
  }
}

function roleBadgeClass(role: string): string {
  switch (role) {
    case 'system_manager':    return 'bg-indigo-100 text-indigo-700'
    case 'validation_lead':   return 'bg-violet-100 text-violet-700'
    case 'qa':                return 'bg-green-100 text-green-700'
    case 'validation_tester': return 'bg-yellow-100 text-yellow-700'
    case 'bpo':               return 'bg-orange-100 text-orange-700'
    case 'company_admin':     return 'bg-red-100 text-red-700'
    default:                  return 'bg-gray-100 text-gray-600'
  }
}

function initials(user: User): string {
  if (user.display_name) {
    return user.display_name
      .split(' ')
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? '')
      .join('')
  }
  return user.email.slice(0, 2).toUpperCase()
}

// ── skeleton ──────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto animate-pulse space-y-6">
      <div className="h-8 w-1/3 bg-gray-200 rounded" />
      <div className="h-4 w-1/2 bg-gray-100 rounded" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 bg-gray-100 rounded-2xl" />
        ))}
      </div>
      <div className="h-6 w-2/3 bg-gray-100 rounded" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-12 bg-gray-100 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ── stat card ─────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
  progress?: number
}

function StatCard({ label, value, sub, accent, progress }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        {label}
      </p>
      <p
        className={`text-3xl font-bold ${
          accent ? 'text-blue-600' : 'text-gray-900'
        }`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      {progress !== undefined && (
        <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all"
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      )}
    </div>
  )
}

// ── component ─────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { label: 'Overview',     path: '' },
  { label: 'Requirements', path: '/requirements' },
  { label: 'Scripts',      path: '/scripts' },
  { label: 'Cycles',       path: '/cycles' },
  { label: 'Agents',       path: '/agents' },
  { label: 'Schedules',    path: '/schedules' },
] as const

export default function SystemDetailPage() {
  const { systemId } = useParams<{ systemId: string }>()
  const { setActiveSystem } = useSystemContext()

  const {
    data: system,
    isLoading,
    error,
  } = useQuery<SystemDetail>({
    queryKey: ['systems', systemId, 'detail'],
    queryFn: () =>
      apiClient.get<SystemDetail>(`/systems/${systemId}/detail`).then((r) => r.data),
    enabled: !!systemId,
  })

  const { data: team = [], isLoading: teamLoading } = useQuery<TeamMember[]>({
    queryKey: ['systems', systemId, 'team'],
    queryFn: () =>
      apiClient.get<TeamMember[]>(`/systems/${systemId}/team`).then((r) => r.data),
    enabled: !!systemId,
  })

  useEffect(() => {
    if (system) {
      setActiveSystem(system)
    }
    return () => {
      // Do not clear on unmount — leave active system set for child routes
    }
  }, [system, setActiveSystem])

  if (!systemId) {
    return (
      <div className="p-8 text-sm text-red-600">Invalid system URL.</div>
    )
  }

  if (isLoading) return <PageSkeleton />

  if (error) {
    return (
      <div className="p-8 text-sm text-red-600">{errorMessage(error)}</div>
    )
  }

  if (!system) return null

  const stats = system.stats

  const baseNavPath = `/systems/${systemId}`

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* ── Top section ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 truncate">{system.name}</h1>
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeBadgeClass(system.system_type)}`}
            >
              {system.system_type}
            </span>
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                system.is_active
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              {system.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>

          {system.description && (
            <p className="text-sm text-gray-500 mt-1">{system.description}</p>
          )}

          {system.base_url && (
            <a
              href={system.base_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-1 text-xs text-blue-600 hover:underline truncate max-w-xs"
            >
              {system.base_url}
            </a>
          )}
        </div>

        <Link
          to={`/systems/${systemId}/settings`}
          className="shrink-0 px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-xl transition-colors"
        >
          Edit
        </Link>
      </div>

      {/* ── Stats row ───────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Requirements"
          value={stats?.requirement_count ?? 0}
        />
        <StatCard
          label="Active Reqs"
          value={stats?.active_requirement_count ?? 0}
        />
        <StatCard
          label="Test Scripts"
          value={stats?.script_count ?? 0}
          sub={
            stats
              ? `${stats.approved_script_count} approved`
              : undefined
          }
        />
        <StatCard
          label="Coverage"
          value={stats ? `${stats.coverage_pct.toFixed(1)}%` : '—'}
          accent
          progress={stats?.coverage_pct ?? 0}
        />
      </div>

      {/* ── Tab navigation ──────────────────────────────────────── */}
      <nav className="border-b border-gray-200">
        <div className="flex gap-1 overflow-x-auto -mb-px">
          {NAV_ITEMS.map(({ label, path }) => (
            <NavLink
              key={label}
              to={`${baseNavPath}${path}`}
              end={path === ''}
              className={({ isActive }) =>
                `whitespace-nowrap px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* ── Overview: Team section ───────────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">Team</h2>

        {teamLoading ? (
          <div className="space-y-3 animate-pulse">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 bg-gray-100 rounded-xl" />
            ))}
          </div>
        ) : team.length === 0 ? (
          <p className="text-sm text-gray-500">No team members assigned yet.</p>
        ) : (
          <div className="bg-white border border-gray-200 rounded-2xl divide-y divide-gray-100 overflow-hidden">
            {team.map((member) => (
              <div
                key={member.user.id}
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors"
              >
                {/* Avatar */}
                <div className="shrink-0 h-9 w-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-semibold">
                  {initials(member.user)}
                </div>

                {/* Name + email */}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {member.user.display_name ?? member.user.email}
                  </p>
                  <p className="text-xs text-gray-400 truncate">{member.user.email}</p>
                </div>

                {/* Role */}
                <span
                  className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${roleBadgeClass(
                    member.role.role,
                  )}`}
                >
                  {member.role.role.replace(/_/g, ' ')}
                </span>

                {/* Domain */}
                {member.business_domain && (
                  <span className="shrink-0 text-xs text-gray-400">
                    {member.business_domain}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
