import { useParams } from 'react-router-dom'
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
import type { DomainCoverage } from '@/types'

// ── API response shape ────────────────────────────────────────────────────

interface CoverageByDomainResponse {
  system_id: string
  breakdown: DomainCoverage[]
}

// ── helpers ───────────────────────────────────────────────────────────────

function domainLabel(domain: string | null): string {
  return domain ?? 'Unassigned'
}

function avgCoverage(breakdown: DomainCoverage[]): number {
  if (breakdown.length === 0) return 0
  const total = breakdown.reduce((sum, d) => sum + d.coverage_pct, 0)
  return Math.round(total / breakdown.length)
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
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

function ChartSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 animate-pulse">
      <div className="h-4 w-32 bg-gray-200 rounded mb-4" />
      <div className="h-56 bg-gray-100 rounded-xl" />
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function CoverageReportPage() {
  const { systemId } = useParams<{ systemId?: string }>()

  const {
    data,
    isLoading,
    error,
  } = useQuery<CoverageByDomainResponse>({
    queryKey: ['reports', 'coverage', systemId],
    queryFn: () =>
      apiClient
        .get<CoverageByDomainResponse>(`/reports/systems/${systemId}/coverage-by-domain`)
        .then((r) => r.data),
    enabled: !!systemId,
  })

  const breakdown = data?.breakdown ?? []
  const totalRequirements = breakdown.reduce((s, d) => s + d.requirement_count, 0)
  const totalScripts = breakdown.reduce((s, d) => s + d.script_count, 0)
  const overallCoverage = avgCoverage(breakdown)

  const chartData = breakdown.map((d) => ({
    domain: domainLabel(d.domain),
    'Requirements': d.requirement_count,
    'Approved Scripts': d.approved_script_count,
  }))

  if (!systemId) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          No system selected. Navigate to a system to view its coverage report.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Coverage Report</h1>
        <p className="mt-1 text-sm text-gray-500 font-mono">System: {systemId}</p>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Summary stats */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Requirements
            </p>
            <p className="text-3xl font-bold text-gray-900">{totalRequirements}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Total Scripts
            </p>
            <p className="text-3xl font-bold text-gray-900">{totalScripts}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-2xl p-5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Overall Coverage
            </p>
            <p className="text-3xl font-bold text-blue-600">{overallCoverage}%</p>
          </div>
        </div>
      )}

      {/* Domain table */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3">
          Domain Breakdown
        </h2>
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Domain
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Requirements
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Scripts
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Approved
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide w-48">
                  Coverage
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
              ) : breakdown.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                    No coverage data available.
                  </td>
                </tr>
              ) : (
                breakdown.map((d, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-800">
                      {domainLabel(d.domain)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{d.requirement_count}</td>
                    <td className="px-4 py-3 text-gray-600">{d.script_count}</td>
                    <td className="px-4 py-3 text-gray-600">{d.approved_script_count}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: `${Math.min(d.coverage_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-600 font-medium w-10 text-right">
                          {d.coverage_pct.toFixed(1)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bar chart */}
      {isLoading ? (
        <ChartSkeleton />
      ) : breakdown.length > 0 ? (
        <section>
          <h2 className="text-base font-semibold text-gray-800 mb-3">
            Requirements vs Approved Scripts by Domain
          </h2>
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="domain"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: 12 }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12 }}
                />
                <Bar dataKey="Requirements" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Approved Scripts" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
    </div>
  )
}
