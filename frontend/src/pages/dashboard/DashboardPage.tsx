import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import { apiClient, errorMessage } from '@/services/api'
import AgentRunStatusBadge from '@/components/AgentRunStatusBadge'
import RoleGate from '@/components/RoleGate'
import type { System, AgentRun } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function typeBadgeClass(type: string): string {
  switch (type) {
    case 'web':       return 'bg-blue-100 text-blue-700'
    case 'sap_fiori': return 'bg-orange-100 text-orange-700'
    case 'api':       return 'bg-purple-100 text-purple-700'
    default:          return 'bg-gray-100 text-gray-600'
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return '—'
  const from = new Date(start).getTime()
  const to = end ? new Date(end).getTime() : Date.now()
  const secs = Math.round((to - from) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  return `${mins}m ${secs % 60}s`
}

// ── skeleton primitives ───────────────────────────────────────────────────

function SystemCardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 animate-pulse">
      <div className="h-4 w-2/3 bg-gray-200 rounded mb-2" />
      <div className="h-3 w-1/3 bg-gray-100 rounded mb-4" />
      <div className="h-3 w-1/2 bg-gray-100 rounded mb-1" />
      <div className="h-3 w-1/4 bg-gray-100 rounded" />
    </div>
  )
}

function TableRowSkeleton() {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

// ── component ─────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate()
  const companyName = useAuthStore((s) => s.currentCompany?.name)

  // ── systems query ──────────────────────────────────────────────────────
  const {
    data: systems = [],
    isLoading: systemsLoading,
    error: systemsError,
  } = useQuery<System[]>({
    queryKey: ['systems'],
    queryFn: () => apiClient.get<System[]>('/systems').then((r) => r.data),
  })

  // ── agent runs query ───────────────────────────────────────────────────
  const hasRunningRun = (runs: AgentRun[]) =>
    runs.some((r) => r.status === 'running')

  const {
    data: agentRuns = [],
    isLoading: runsLoading,
    error: runsError,
  } = useQuery<AgentRun[]>({
    queryKey: ['agent_runs', 'recent'],
    queryFn: () =>
      apiClient.get<AgentRun[]>('/agent_runs', { params: { limit: 10 } }).then((r) => r.data),
    refetchInterval: (query) => {
      const runs = query.state.data ?? []
      return hasRunningRun(runs) ? 10_000 : false
    },
  })

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-10">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        {companyName && (
          <p className="mt-1 text-sm text-gray-500">{companyName}</p>
        )}
      </div>

      {/* ── Section 1: Systems ─────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-800">Systems</h2>
          <Link
            to="/systems"
            className="text-sm text-blue-600 hover:underline font-medium"
          >
            View all
          </Link>
        </div>

        {systemsError && (
          <p className="text-sm text-red-600">{errorMessage(systemsError)}</p>
        )}

        {systemsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <SystemCardSkeleton key={i} />
            ))}
          </div>
        ) : systems.length === 0 ? (
          <div className="rounded-2xl border-2 border-dashed border-gray-200 p-10 text-center">
            <p className="text-sm text-gray-500 mb-3">No systems configured yet.</p>
            <RoleGate permission="system:create">
              <Link
                to="/systems"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors"
              >
                Add your first system
              </Link>
            </RoleGate>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {systems.map((system) => (
              <div
                key={system.id}
                className="bg-white border border-gray-200 rounded-2xl p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 truncate pr-2">
                    {system.name}
                  </h3>
                  <span
                    className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${typeBadgeClass(system.system_type)}`}
                  >
                    {system.system_type}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 mb-3">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      system.is_active ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  />
                  <span className="text-xs text-gray-500">
                    {system.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {system.base_url && (
                  <p className="text-xs text-gray-400 truncate mb-3">
                    {system.base_url}
                  </p>
                )}

                <p className="text-xs text-gray-400 mb-4">
                  Updated {formatDate(system.updated_at)}
                </p>

                <Link
                  to={`/systems/${system.id}`}
                  className="text-xs font-medium text-blue-600 hover:underline"
                >
                  View →
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Section 2: Recent Agent Runs ─────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">
          Recent Agent Runs
        </h2>

        {runsError && (
          <p className="text-sm text-red-600">{errorMessage(runsError)}</p>
        )}

        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Agent Type
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  System
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Started
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {runsLoading ? (
                Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
              ) : agentRuns.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                    No agent runs yet. Start by running an agent on a system.
                  </td>
                </tr>
              ) : (
                agentRuns.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-800 capitalize">
                      {run.agent_type}
                    </td>
                    <td className="px-4 py-3">
                      <AgentRunStatusBadge status={run.status} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {run.system_id ? (
                        <Link
                          to={`/systems/${run.system_id}`}
                          className="hover:underline text-blue-600"
                        >
                          {run.system_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {formatDate(run.started_at)}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {formatDuration(run.started_at, run.completed_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Section 3: Quick Actions ────────────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <RoleGate permission="agent:crawl">
            <button
              onClick={() => navigate('/agents/start')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl transition-colors"
            >
              Start Crawl
            </button>
          </RoleGate>

          <RoleGate permission="agent:generate">
            <button
              onClick={() => navigate('/agents/start')}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-xl transition-colors"
            >
              Generate Scripts
            </button>
          </RoleGate>

          <RoleGate permission="agent:execute">
            <button
              onClick={() => navigate('/agents/start')}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-xl transition-colors"
            >
              Run Execution
            </button>
          </RoleGate>
        </div>
      </section>
    </div>
  )
}
