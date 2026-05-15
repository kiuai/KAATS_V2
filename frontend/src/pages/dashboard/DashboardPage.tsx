import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Server, Bot, PlayCircle, Plus,
  ArrowRight, Globe, Layers, Code2,
  Activity,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { apiClient, errorMessage } from '@/services/api'
import AgentRunStatusBadge from '@/components/AgentRunStatusBadge'
import RoleGate from '@/components/RoleGate'
import type { System, AgentRun } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function typeIcon(type: string) {
  switch (type) {
    case 'web':       return <Globe size={14} className="text-blue-500" />
    case 'sap_fiori': return <Layers size={14} className="text-orange-500" />
    case 'api':       return <Code2 size={14} className="text-purple-500" />
    default:          return <Server size={14} className="text-gray-400" />
  }
}

function typeBadgeClass(type: string): string {
  switch (type) {
    case 'web':       return 'bg-blue-50 text-blue-600 ring-1 ring-blue-100'
    case 'sap_fiori': return 'bg-orange-50 text-orange-600 ring-1 ring-orange-100'
    case 'api':       return 'bg-purple-50 text-purple-600 ring-1 ring-purple-100'
    default:          return 'bg-gray-50 text-gray-500 ring-1 ring-gray-100'
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return '—'
  const secs = Math.round((((end ? new Date(end) : new Date()).getTime()) - new Date(start).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

// ── skeletons ─────────────────────────────────────────────────────────────

function SystemCardSkeleton() {
  return (
    <div className="bg-white border border-gray-100 rounded-2xl p-5 animate-pulse space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-xl bg-gray-100" />
        <div className="space-y-1.5 flex-1">
          <div className="h-3.5 w-2/3 bg-gray-100 rounded" />
          <div className="h-2.5 w-1/3 bg-gray-50 rounded" />
        </div>
      </div>
      <div className="h-2.5 w-1/2 bg-gray-50 rounded" />
    </div>
  )
}

function TableRowSkeleton() {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3.5">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

// ── stat card ─────────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, sub, color,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  sub?: string
  color: string
}) {
  return (
    <div className="bg-white border border-gray-100 rounded-2xl px-5 py-4 flex items-center gap-4 shadow-sm">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-gray-900 leading-none">{value}</p>
        <p className="text-xs text-gray-500 mt-1">{label}</p>
        {sub && <p className="text-[11px] text-gray-400">{sub}</p>}
      </div>
    </div>
  )
}

// ── component ─────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate()
  const { currentCompany, user } = useAuthStore()

  const { data: systems = [], isLoading: systemsLoading, error: systemsError } =
    useQuery<System[]>({
      queryKey: ['systems'],
      queryFn: () => apiClient.get<System[]>('/systems').then((r) => r.data),
      enabled: !!currentCompany,
    })

  const { data: agentRuns = [], isLoading: runsLoading, error: runsError } =
    useQuery<AgentRun[]>({
      queryKey: ['agent_runs', 'recent'],
      queryFn: () => apiClient.get<AgentRun[]>('/agent_runs', { params: { limit: 10 } }).then((r) => r.data),
      refetchInterval: (q) => (q.state.data ?? []).some((r) => r.status === 'running') ? 10_000 : false,
      enabled: !!currentCompany,
    })

  const displayName = user?.display_name?.split(' ')[0] ?? user?.email?.split('@')[0] ?? ''
  const activeSystems = systems.filter((s) => s.is_active).length
  const runningAgents = agentRuns.filter((r) => r.status === 'running').length
  const completedToday = agentRuns.filter((r) => {
    if (!r.completed_at) return false
    return new Date(r.completed_at).toDateString() === new Date().toDateString()
  }).length

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">

      {/* ── Page header ───────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {greeting()}{displayName ? `, ${displayName}` : ''}
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {currentCompany?.name
              ? `${currentCompany.name} · `
              : ''}
            {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <RoleGate permission="agent:crawl">
          <button
            onClick={() => navigate('/agents/start')}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-xl transition-colors shadow-sm"
          >
            <Plus size={15} />
            New Run
          </button>
        </RoleGate>
      </div>

      {/* ── Stats ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Server size={18} className="text-blue-600" />}
          label="Active systems"
          value={systemsLoading ? '—' : activeSystems}
          color="bg-blue-50"
        />
        <StatCard
          icon={<Bot size={18} className="text-indigo-600" />}
          label="Agents running"
          value={runsLoading ? '—' : runningAgents}
          color="bg-indigo-50"
        />
        <StatCard
          icon={<Activity size={18} className="text-emerald-600" />}
          label="Completed today"
          value={runsLoading ? '—' : completedToday}
          color="bg-emerald-50"
        />
        <StatCard
          icon={<PlayCircle size={18} className="text-violet-600" />}
          label="Total runs"
          value={runsLoading ? '—' : agentRuns.length}
          sub="last 10 shown"
          color="bg-violet-50"
        />
      </div>

      {/* ── Systems grid ──────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-700">Systems</h2>
            {!systemsLoading && (
              <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">
                {systems.length}
              </span>
            )}
          </div>
          <Link to="/systems" className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
            View all <ArrowRight size={12} />
          </Link>
        </div>

        {systemsError && (
          <p className="text-sm text-red-600 mb-3">{errorMessage(systemsError)}</p>
        )}

        {systemsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => <SystemCardSkeleton key={i} />)}
          </div>
        ) : systems.length === 0 ? (
          <div className="rounded-2xl border-2 border-dashed border-gray-200 p-12 text-center">
            <div className="w-12 h-12 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-3">
              <Server size={22} className="text-gray-400" />
            </div>
            <p className="text-sm font-medium text-gray-700 mb-1">No systems yet</p>
            <p className="text-xs text-gray-400 mb-4">Add a system to start running automated tests.</p>
            <RoleGate permission="system:create">
              <Link
                to="/systems"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 transition-colors"
              >
                <Plus size={14} />
                Add system
              </Link>
            </RoleGate>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {systems.map((system) => (
              <Link
                key={system.id}
                to={`/systems/${system.id}`}
                className="group bg-white border border-gray-100 rounded-2xl p-5 hover:border-indigo-200 hover:shadow-md transition-all duration-150"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-9 h-9 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center shrink-0 group-hover:border-indigo-100 transition-colors">
                    {typeIcon(system.system_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 text-sm truncate">{system.name}</h3>
                    <span className={`inline-flex items-center text-[11px] font-medium px-1.5 py-0.5 rounded-md mt-0.5 ${typeBadgeClass(system.system_type)}`}>
                      {system.system_type}
                    </span>
                  </div>
                  <span className={`shrink-0 flex items-center gap-1 text-[11px] font-medium ${system.is_active ? 'text-emerald-600' : 'text-gray-400'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${system.is_active ? 'bg-emerald-500' : 'bg-gray-300'}`} />
                    {system.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {system.base_url && (
                  <p className="text-xs text-gray-400 truncate mb-2">{system.base_url}</p>
                )}

                <p className="text-xs text-gray-400">Updated {formatDate(system.updated_at)}</p>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ── Recent agent runs ─────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-700">Recent Agent Runs</h2>
            {!runsLoading && agentRuns.length > 0 && (
              <span className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">
                {agentRuns.length}
              </span>
            )}
          </div>
          <Link to="/agents" className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
            View all <ArrowRight size={12} />
          </Link>
        </div>

        {runsError && (
          <p className="text-sm text-red-600 mb-3">{errorMessage(runsError)}</p>
        )}

        <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50">
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wide">Agent</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wide">Status</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wide hidden md:table-cell">System</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wide hidden lg:table-cell">Started</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wide">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {runsLoading ? (
                Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
              ) : agentRuns.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-14 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center">
                        <Bot size={18} className="text-gray-300" />
                      </div>
                      <p className="text-sm text-gray-400">No agent runs yet</p>
                      <p className="text-xs text-gray-300">Start a run from any system to see it here.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                agentRuns.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="px-4 py-3.5 font-medium text-gray-800 capitalize">{run.agent_type}</td>
                    <td className="px-4 py-3.5">
                      <AgentRunStatusBadge status={run.status} size="sm" />
                    </td>
                    <td className="px-4 py-3.5 text-gray-400 hidden md:table-cell">
                      {run.system_id
                        ? <Link to={`/systems/${run.system_id}`} className="hover:text-indigo-600 transition-colors">{run.system_id.slice(0, 8)}…</Link>
                        : '—'}
                    </td>
                    <td className="px-4 py-3.5 text-gray-400 hidden lg:table-cell">{formatDate(run.started_at)}</td>
                    <td className="px-4 py-3.5 text-gray-400">{formatDuration(run.started_at, run.completed_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Quick actions ─────────────────────────────────────────── */}
      <section>
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-2.5">
          <RoleGate permission="agent:crawl">
            <button
              onClick={() => navigate('/agents/start')}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:border-indigo-300 hover:text-indigo-700 hover:bg-indigo-50 transition-all shadow-sm"
            >
              <Globe size={14} className="text-indigo-500" />
              Start Crawl
            </button>
          </RoleGate>
          <RoleGate permission="agent:generate">
            <button
              onClick={() => navigate('/agents/start')}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:border-violet-300 hover:text-violet-700 hover:bg-violet-50 transition-all shadow-sm"
            >
              <Code2 size={14} className="text-violet-500" />
              Generate Scripts
            </button>
          </RoleGate>
          <RoleGate permission="agent:execute">
            <button
              onClick={() => navigate('/agents/start')}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:border-emerald-300 hover:text-emerald-700 hover:bg-emerald-50 transition-all shadow-sm"
            >
              <PlayCircle size={14} className="text-emerald-500" />
              Run Execution
            </button>
          </RoleGate>
        </div>
      </section>
    </div>
  )
}
