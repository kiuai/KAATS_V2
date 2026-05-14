import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Server, FileText, Code2, CheckCircle, Activity } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { usePermission } from '@/hooks/usePermission'
import type { CompanyOverview } from '@/types'

// ── stat card ─────────────────────────────────────────────────────────────

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: number
  accent?: string
}

function StatCard({ icon, label, value, accent = 'text-gray-800' }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 flex items-start gap-4">
      <div className="shrink-0 w-12 h-12 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center">
        {icon}
      </div>
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
          {label}
        </p>
        <p className={`text-3xl font-bold ${accent}`}>{value.toLocaleString()}</p>
      </div>
    </div>
  )
}

function StatCardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-6 flex items-start gap-4 animate-pulse">
      <div className="shrink-0 w-12 h-12 rounded-xl bg-gray-100" />
      <div className="space-y-2 flex-1">
        <div className="h-3 w-24 bg-gray-200 rounded" />
        <div className="h-7 w-16 bg-gray-100 rounded" />
      </div>
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
          You do not have permission to view company overview reports.
        </p>
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

function CompanyOverviewContent() {
  const companyId = useAuthStore((s) => s.currentCompany?.id)

  const {
    data: overview,
    isLoading,
    error,
  } = useQuery<CompanyOverview>({
    queryKey: ['reports', 'company-overview', companyId],
    queryFn: () =>
      apiClient
        .get<CompanyOverview>(`/reports/companies/${companyId}/overview`)
        .then((r) => r.data),
    enabled: !!companyId,
  })

  if (!companyId) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          No company context available.
        </div>
      </div>
    )
  }

  const coveragePct =
    overview && overview.script_count > 0
      ? Math.round((overview.approved_script_count / overview.script_count) * 100)
      : 0

  const chartData = overview
    ? [
        { name: 'Scripts', value: overview.script_count, fill: '#3b82f6' },
        { name: 'Approved', value: overview.approved_script_count, fill: '#22c55e' },
      ]
    : []

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Company Overview</h1>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      ) : overview ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          <StatCard
            icon={<Server size={22} className="text-gray-600" />}
            label="Systems"
            value={overview.system_count}
          />
          <StatCard
            icon={<FileText size={22} className="text-gray-600" />}
            label="Requirements"
            value={overview.requirement_count}
          />
          <StatCard
            icon={<Code2 size={22} className="text-gray-600" />}
            label="Test Scripts"
            value={overview.script_count}
          />
          <StatCard
            icon={<CheckCircle size={22} className="text-green-600" />}
            label="Approved Scripts"
            value={overview.approved_script_count}
            accent="text-green-700"
          />
          <StatCard
            icon={<Activity size={22} className="text-blue-600" />}
            label="Active Cycles"
            value={overview.active_cycle_count}
            accent="text-blue-700"
          />
        </div>
      ) : null}

      {/* Script coverage chart */}
      {!isLoading && overview && (
        <section>
          <h2 className="text-base font-semibold text-gray-800 mb-3">
            Script Coverage — {coveragePct}% approved
          </h2>
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={chartData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                layout="vertical"
              >
                <XAxis type="number" tick={{ fontSize: 12, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                  width={70}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  )
}

export default function CompanyOverviewPage() {
  const allowed = usePermission('admin:company')
  if (!allowed) return <AccessDenied />
  return <CompanyOverviewContent />
}
