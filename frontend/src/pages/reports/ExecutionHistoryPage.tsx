import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { apiClient, errorMessage } from '@/services/api'

// ── API response shape ────────────────────────────────────────────────────

interface ExecutionHistoryEntry {
  id: string
  status: string
  started_at: string | null
  completed_at: string | null
  prompt_tokens: number
  completion_tokens: number
  error_message: string | null
}

interface ExecutionHistoryResponse {
  system_id: string
  executions: ExecutionHistoryEntry[]
}

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

function formatDateShort(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

function durationLabel(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 1000) return `${ms}ms`
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  return `${mins}m ${secs % 60}s`
}

function buildDailyChart(
  executions: ExecutionHistoryEntry[],
): { date: string; completions: number }[] {
  const map = new Map<string, number>()
  for (const e of executions) {
    if (!e.completed_at) continue
    const day = new Date(e.completed_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
    map.set(day, (map.get(day) ?? 0) + 1)
  }
  return Array.from(map.entries())
    .map(([date, completions]) => ({ date, completions }))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
}

// ── status badge ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  let cls = 'bg-gray-100 text-gray-600'
  if (status === 'completed') cls = 'bg-green-100 text-green-700'
  else if (status === 'failed' || status === 'error') cls = 'bg-red-100 text-red-700'
  else if (status === 'running') cls = 'bg-yellow-100 text-yellow-700'
  else if (status === 'pending') cls = 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

// ── skeletons ─────────────────────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 animate-pulse">
      <div className="h-3 w-24 bg-gray-200 rounded mb-3" />
      <div className="h-7 w-16 bg-gray-100 rounded" />
    </div>
  )
}

function TableRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-gray-50">
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

const DAY_OPTIONS = [7, 14, 30, 90] as const
type DayOption = (typeof DAY_OPTIONS)[number]

export default function ExecutionHistoryPage() {
  const { systemId } = useParams<{ systemId?: string }>()
  const [days, setDays] = useState<DayOption>(30)

  const {
    data,
    isLoading,
    error,
  } = useQuery<ExecutionHistoryResponse>({
    queryKey: ['reports', 'execution-history', systemId, days],
    queryFn: () =>
      apiClient
        .get<ExecutionHistoryResponse>(
          `/reports/systems/${systemId}/execution-history`,
          { params: { days, limit: 50 } },
        )
        .then((r) => r.data),
    enabled: !!systemId,
  })

  const executions = data?.executions ?? []

  const totalRuns = executions.length
  const completed = executions.filter((e) => e.status === 'completed').length
  const failed = executions.filter(
    (e) => e.status === 'failed' || e.status === 'error',
  ).length
  const avgTokens =
    totalRuns > 0
      ? Math.round(
          executions.reduce((s, e) => s + e.prompt_tokens + e.completion_tokens, 0) /
            totalRuns,
        )
      : 0

  const chartData = buildDailyChart(executions)

  if (!systemId) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          No system selected. Navigate to a system to view its execution history.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Header + filter */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Execution History</h1>
          <p className="mt-1 text-sm text-gray-500 font-mono">System: {systemId}</p>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="days-filter"
            className="text-sm font-medium text-gray-600"
          >
            Last
          </label>
          <select
            id="days-filter"
            value={days}
            onChange={(e) => setDays(Number(e.target.value) as DayOption)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {DAY_OPTIONS.map((d) => (
              <option key={d} value={d}>
                {d} days
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Summary stats */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Runs
            </p>
            <p className="text-3xl font-bold text-gray-900">{totalRuns}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Completed
            </p>
            <p className="text-3xl font-bold text-green-700">{completed}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Failed
            </p>
            <p className="text-3xl font-bold text-red-600">{failed}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Avg Tokens / Run
            </p>
            <p className="text-3xl font-bold text-gray-900">
              {avgTokens.toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Line chart */}
      {!isLoading && chartData.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-gray-800 mb-3">
            Completions per Day
          </h2>
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="completions"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#3b82f6' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Table */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3">
          Execution Log
        </h2>
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  ID
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Started
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Completed
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Duration
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Tokens
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Error
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
              ) : executions.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-10 text-center text-sm text-gray-500"
                  >
                    No executions found for this period.
                  </td>
                </tr>
              ) : (
                executions.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {e.id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDateShort(e.started_at)}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDate(e.completed_at)}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {durationLabel(e.started_at, e.completed_at)}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {(e.prompt_tokens + e.completion_tokens).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-red-600 text-xs max-w-xs truncate">
                      {e.error_message ? (
                        <span title={e.error_message}>
                          {e.error_message.slice(0, 60)}
                          {e.error_message.length > 60 ? '…' : ''}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
