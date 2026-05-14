import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { apiClient, errorMessage } from '@/services/api'
import RoleGate from '@/components/RoleGate'
import { useAuthStore } from '@/store/authStore'
import { usePermission } from '@/hooks/usePermission'
import type { AgentType } from '@/types'

// ── API response shape ────────────────────────────────────────────────────

interface AIUsageBreakdown {
  agent_type: AgentType | string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

interface AIUsageResponse {
  company_id: string
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  breakdown: AIUsageBreakdown[]
}

// ── helpers ───────────────────────────────────────────────────────────────

function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

function thirtyDaysAgoISO(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

// ── skeletons ─────────────────────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 animate-pulse">
      <div className="h-3 w-32 bg-gray-200 rounded mb-3" />
      <div className="h-7 w-20 bg-gray-100 rounded" />
    </div>
  )
}

// ── 403 fallback ──────────────────────────────────────────────────────────

function AccessDenied() {
  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
      <div className="rounded-2xl bg-red-50 border border-red-200 p-10 text-center">
        <p className="text-lg font-semibold text-red-700 mb-2">Access Denied</p>
        <p className="text-sm text-red-600">
          You do not have permission to view AI usage reports.
        </p>
      </div>
    </div>
  )
}

// ── agent type options ────────────────────────────────────────────────────

const AGENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All types' },
  { value: 'crawl', label: 'Crawl' },
  { value: 'generation', label: 'Generation' },
  { value: 'execution', label: 'Execution' },
]

// ── content ───────────────────────────────────────────────────────────────

function AIUsageContent() {
  const companyId = useAuthStore((s) => s.currentCompany?.id)

  const [dateFrom, setDateFrom] = useState<string>(thirtyDaysAgoISO())
  const [dateTo, setDateTo] = useState<string>(todayISO())
  const [agentType, setAgentType] = useState<string>('')

  const {
    data,
    isLoading,
    error,
  } = useQuery<AIUsageResponse>({
    queryKey: ['reports', 'ai-usage', companyId, dateFrom, dateTo, agentType],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      if (agentType) params.agent_type = agentType
      return apiClient
        .get<AIUsageResponse>(`/reports/companies/${companyId}/ai-usage`, { params })
        .then((r) => r.data)
    },
    enabled: !!companyId,
  })

  const breakdown = data?.breakdown ?? []

  const chartData = breakdown.map((b) => ({
    agent_type: b.agent_type,
    'Prompt Tokens': b.prompt_tokens,
    'Completion Tokens': b.completion_tokens,
  }))

  if (!companyId) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          No company context available.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Usage</h1>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-4 bg-white border border-gray-200 rounded-2xl p-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="date-from" className="text-xs font-medium text-gray-600">
            From
          </label>
          <input
            id="date-from"
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="date-to" className="text-xs font-medium text-gray-600">
            To
          </label>
          <input
            id="date-to"
            type="date"
            value={dateTo}
            min={dateFrom}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="agent-type" className="text-xs font-medium text-gray-600">
            Agent Type
          </label>
          <select
            id="agent-type"
            value={agentType}
            onChange={(e) => setAgentType(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {AGENT_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary stat cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Prompt Tokens
            </p>
            <p className="text-3xl font-bold text-blue-700">
              {data.total_prompt_tokens.toLocaleString()}
            </p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Completion Tokens
            </p>
            <p className="text-3xl font-bold text-purple-700">
              {data.total_completion_tokens.toLocaleString()}
            </p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Tokens
            </p>
            <p className="text-3xl font-bold text-gray-900">
              {data.total_tokens.toLocaleString()}
            </p>
          </div>
        </div>
      ) : null}

      {/* Bar chart */}
      {!isLoading && chartData.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-gray-800 mb-3">
            Token Usage by Agent Type
          </h2>
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="agent_type"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: number) =>
                    v >= 1_000_000
                      ? `${(v / 1_000_000).toFixed(1)}M`
                      : v >= 1_000
                      ? `${(v / 1_000).toFixed(0)}k`
                      : String(v)
                  }
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: 12,
                  }}
                  formatter={(value: number) => value.toLocaleString()}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Prompt Tokens" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Completion Tokens" fill="#a855f7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {!isLoading && chartData.length === 0 && !error && (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 p-10 text-center">
          <p className="text-sm text-gray-500">No AI usage data found for the selected filters.</p>
        </div>
      )}
    </div>
  )
}

export default function AIUsagePage() {
  const allowed = usePermission('ai:usage_read')
  if (!allowed) return <AccessDenied />
  return (
    <RoleGate permission="ai:usage_read" fallback={<AccessDenied />}>
      <AIUsageContent />
    </RoleGate>
  )
}
