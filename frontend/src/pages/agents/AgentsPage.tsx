import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Cpu, Plus, ChevronRight, Clock, DollarSign } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { AgentRun, AgentRunStatus } from '@/types'
import AgentRunStatusBadge from '@/components/AgentRunStatusBadge'
import LiveAgentRunCard from '@/components/LiveAgentRunCard'
import RoleGate from '@/components/RoleGate'

// ── Helpers ───────────────────────────────────────────────────────────────────

const ACTIVE_STATUSES = new Set<AgentRunStatus>(['pending', 'running'])

const AGENT_TYPE_LABELS: Record<string, string> = {
  crawl:      'Crawl',
  generation: 'Generation',
  execution:  'Execution',
}

function formatDuration(started: string | null, completed: string | null): string {
  if (!started) return '—'
  const end = completed ? new Date(completed) : new Date()
  const ms = end.getTime() - new Date(started).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const remaining = s % 60
  return `${m}m ${remaining}s`
}

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return '—'
  return `$${cost.toFixed(4)}`
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-12 bg-gray-100 rounded-lg" />
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const navigate = useNavigate()

  const { data: runs, isLoading, isError, error } = useQuery<AgentRun[]>({
    queryKey: ['agent-runs'],
    queryFn: () =>
      apiClient.get('/agent_runs', { params: { limit: 20 } }).then((r) => r.data),
    refetchInterval: 5_000,
  })

  const activeRuns = (runs ?? []).filter((r) => ACTIVE_STATUSES.has(r.status))
  const historyRuns = (runs ?? []).filter((r) => !ACTIVE_STATUSES.has(r.status))

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Runs</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Monitor active runs and browse execution history.
          </p>
        </div>
        <RoleGate permission="agent:crawl">
          <Link
            to="/agents/start"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus size={16} />
            Start New Agent
          </Link>
        </RoleGate>
      </div>

      {/* Section 1: Active runs */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-gray-800">Active Runs</h2>
          {activeRuns.length > 0 && (
            <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-blue-600 text-white text-xs font-bold">
              {activeRuns.length}
            </span>
          )}
        </div>

        {isLoading && (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="animate-pulse h-16 bg-gray-100 rounded-xl" />
            ))}
          </div>
        )}

        {!isLoading && activeRuns.length === 0 && (
          <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl py-8 text-center">
            <Cpu size={28} className="mx-auto mb-2 text-gray-300" />
            <p className="text-sm text-gray-400">No active agent runs.</p>
          </div>
        )}

        {activeRuns.map((run) => (
          <LiveAgentRunCard key={run.id} runId={run.id} />
        ))}
      </section>

      {/* Section 2: History table */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-gray-800">Run History</h2>

        {isError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            {errorMessage(error)}
          </div>
        )}

        {isLoading ? (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden p-4">
            <TableSkeleton />
          </div>
        ) : historyRuns.length === 0 ? (
          <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl py-8 text-center text-sm text-gray-400">
            No completed runs yet.
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <tr>
                    <th className="px-4 py-3 text-left">Type</th>
                    <th className="px-4 py-3 text-left">System</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Trigger</th>
                    <th className="px-4 py-3 text-left">Started</th>
                    <th className="px-4 py-3 text-left">
                      <span className="inline-flex items-center gap-1">
                        <Clock size={11} /> Duration
                      </span>
                    </th>
                    <th className="px-4 py-3 text-left">
                      <span className="inline-flex items-center gap-1">
                        <DollarSign size={11} /> Cost
                      </span>
                    </th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {historyRuns.map((run) => (
                    <tr
                      key={run.id}
                      onClick={() => navigate(`/agents/${run.id}`)}
                      className="hover:bg-gray-50 cursor-pointer transition-colors group"
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {AGENT_TYPE_LABELS[run.agent_type] ?? run.agent_type}
                      </td>
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                        {run.system_id ? run.system_id.slice(0, 8) + '…' : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <AgentRunStatusBadge status={run.status} size="sm" />
                      </td>
                      <td className="px-4 py-3 text-gray-500 capitalize">
                        {run.trigger_type}
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {run.started_at
                          ? new Date(run.started_at).toLocaleString()
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {formatDuration(run.started_at, run.completed_at)}
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {formatCost(run.total_cost_usd)}
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight
                          size={16}
                          className="text-gray-300 group-hover:text-blue-400 transition-colors"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
