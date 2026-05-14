import { useNavigate, useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient, errorMessage } from '@/services/api'
import type { ExecutionRun } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  return `${mins}m ${secs % 60}s`
}

// ── status badge ──────────────────────────────────────────────────────────

interface StatusBadgeProps {
  status: ExecutionRun['status']
}

function StatusBadge({ status }: StatusBadgeProps) {
  const map: Record<ExecutionRun['status'], string> = {
    passed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    error: 'bg-red-100 text-red-700',
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status]}`}
    >
      {status === 'running' && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500" />
        </span>
      )}
      {status}
    </span>
  )
}

// ── skeleton ──────────────────────────────────────────────────────────────

function TableRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-gray-50">
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function ExecutionRunsPage() {
  const { scriptId, systemId } = useParams<{ scriptId?: string; systemId?: string }>()
  const navigate = useNavigate()

  const queryKey = scriptId
    ? ['executions', 'script', scriptId]
    : ['executions', 'system', systemId]

  const queryFn = scriptId
    ? () =>
        apiClient
          .get<ExecutionRun[]>(`/scripts/${scriptId}/executions`)
          .then((r) => r.data)
    : () =>
        apiClient
          .get<ExecutionRun[]>('/agent_runs', {
            params: { system_id: systemId, agent_type: 'execution' },
          })
          .then((r) => r.data)

  const {
    data: runs = [],
    isLoading,
    error,
  } = useQuery<ExecutionRun[]>({
    queryKey,
    queryFn,
    enabled: !!(scriptId ?? systemId),
  })

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Execution Runs</h1>
        {scriptId && (
          <p className="mt-1 text-sm text-gray-500">
            Script:{' '}
            <span className="font-mono text-gray-700">{scriptId}</span>
          </p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left">
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Script ID
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Status
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Passed
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Failed
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Skipped
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
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
            ) : runs.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-sm text-gray-500"
                >
                  No execution runs found.
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr
                  key={run.id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => navigate(`/evidence/${run.id}`)}
                >
                  <td className="px-4 py-3 font-mono text-gray-700 text-xs">
                    <Link
                      to={`/scripts/${run.script_id}`}
                      className="hover:underline text-blue-600"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {run.script_id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-green-700 font-medium">
                    {run.passed_count}
                  </td>
                  <td className="px-4 py-3 text-red-700 font-medium">
                    {run.failed_count}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {run.skipped_count}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {formatDate(run.started_at)}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {formatDuration(run.duration_ms)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
