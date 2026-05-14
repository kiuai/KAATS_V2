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

interface QuotaStatus {
  plan_tier: string
  tokens_used: number
  tokens_limit: number | null
  tokens_pct: number | null
  tokens_warning: boolean
  tokens_exceeded: boolean
  runs_used: number
  runs_limit: number | null
  runs_pct: number | null
  runs_warning: boolean
  runs_exceeded: boolean
  max_systems: number | null
  max_users: number | null
  estimated_cost_usd: string
}

// ── Quota components ──────────────────────────────────────────────────────

function QuotaBar({
  label,
  used,
  limit,
  pct,
  warning,
  exceeded,
}: {
  label: string
  used: number
  limit: number | null
  pct: number | null
  warning: boolean
  exceeded: boolean
}) {
  const colour = exceeded
    ? 'bg-red-500'
    : warning
    ? 'bg-amber-400'
    : 'bg-indigo-500'

  const textColour = exceeded ? 'text-red-600' : warning ? 'text-amber-600' : 'text-gray-700'

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${textColour}`}>
          {limit === null
            ? `${used.toLocaleString()} / unlimited`
            : `${used.toLocaleString()} / ${limit.toLocaleString()}`}
          {pct !== null && <span className="ml-1 text-xs font-normal">({pct}%)</span>}
        </span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className={`${colour} h-2 rounded-full transition-all duration-500`}
          style={{ width: `${Math.min(pct ?? 0, 100)}%` }}
        />
      </div>
      {exceeded && (
        <p className="text-xs text-red-600 mt-1">
          Quota exceeded — new agent runs are blocked until next month.
        </p>
      )}
      {warning && !exceeded && (
        <p className="text-xs text-amber-600 mt-1">
          Approaching limit — consider upgrading your plan.
        </p>
      )}
    </div>
  )
}

function PlanTierBadge({ tier }: { tier: string }) {
  const colours: Record<string, string> = {
    free: 'bg-gray-100 text-gray-600',
    pro: 'bg-blue-100 text-blue-700',
    enterprise: 'bg-indigo-100 text-indigo-700',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
        colours[tier] ?? colours.free
      }`}
    >
      {tier}
    </span>
  )
}

function QuotaSection({ companyId }: { companyId: string }) {
  const { data, isLoading } = useQuery<QuotaStatus>({
    queryKey: ['usage', 'quota', companyId],
    queryFn: () => apiClient.get('/usage/quota').then((r) => r.data),
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-6 animate-pulse space-y-3">
        <div className="h-3 w-32 bg-gray-200 rounded" />
        <div className="h-2 w-full bg-gray-100 rounded" />
        <div className="h-2 w-full bg-gray-100 rounded" />
      </div>
    )
  }
  if (!data) return null

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-gray-800">This month's quota</h2>
        <PlanTierBadge tier={data.plan_tier} />
      </div>

      <div className="space-y-5">
        <QuotaBar
          label="AI tokens"
          used={data.tokens_used}
          limit={data.tokens_limit}
          pct={data.tokens_pct}
          warning={data.tokens_warning}
          exceeded={data.tokens_exceeded}
        />
        <QuotaBar
          label="Agent runs"
          used={data.runs_used}
          limit={data.runs_limit}
          pct={data.runs_pct}
          warning={data.runs_warning}
          exceeded={data.runs_exceeded}
        />
      </div>

      <div className="mt-5 pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
        <span>Estimated cost this month</span>
        <span className="font-semibold text-gray-700">
          ${parseFloat(data.estimated_cost_usd).toFixed(4)}
        </span>
      </div>
    </div>
  )
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

      {/* Quota bars */}
      <QuotaSection companyId={companyId} />

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
  return <AIUsageContent />
}
