import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Building2,
  Users,
  Bot,
  Zap,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { usePermission } from '@/hooks/usePermission'
import type { PlatformOverview, CompanyAdminRead, Enterprise } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-gray-100 text-gray-600',
  pro: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
}

function PlanBadge({ tier }: { tier: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
        PLAN_COLORS[tier] ?? 'bg-gray-100 text-gray-600'
      }`}
    >
      {tier}
    </span>
  )
}

// ── stat card ────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  icon: React.ReactNode
  color: string
}

function StatCard({ label, value, sub, icon, color }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${color}`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── skeleton ──────────────────────────────────────────────────────────────

function RowSkeleton({ cols }: { cols: number }) {
  return (
    <tr className="animate-pulse border-b border-gray-50">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded" />
        </td>
      ))}
    </tr>
  )
}

// ── access denied ─────────────────────────────────────────────────────────

function AccessDenied() {
  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
      <div className="rounded-2xl bg-red-50 border border-red-200 p-10 text-center">
        <p className="text-lg font-semibold text-red-700 mb-2">Access Denied</p>
        <p className="text-sm text-red-600">This page requires global admin privileges.</p>
      </div>
    </div>
  )
}

// ── main content ──────────────────────────────────────────────────────────

function AdminDashboardContent() {
  const navigate = useNavigate()
  const [planFilter, setPlanFilter] = useState<string>('')
  const [enterpriseFilter, setEnterpriseFilter] = useState<string>('')
  const [activeOnly, setActiveOnly] = useState(false)

  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery<PlatformOverview>({
    queryKey: ['admin-overview'],
    queryFn: () => apiClient.get<PlatformOverview>('/admin/overview').then((r) => r.data),
  })

  const {
    data: companies = [],
    isLoading: companiesLoading,
    error: companiesError,
    refetch: refetchCompanies,
  } = useQuery<CompanyAdminRead[]>({
    queryKey: ['admin-companies', enterpriseFilter, planFilter, activeOnly],
    queryFn: () => {
      const params = new URLSearchParams()
      if (enterpriseFilter) params.set('enterprise_id', enterpriseFilter)
      if (planFilter) params.set('plan_tier', planFilter)
      if (activeOnly) params.set('active_only', 'true')
      const qs = params.toString()
      return apiClient
        .get<CompanyAdminRead[]>(`/admin/companies${qs ? `?${qs}` : ''}`)
        .then((r) => r.data)
    },
  })

  const { data: enterprises = [] } = useQuery<Enterprise[]>({
    queryKey: ['enterprises'],
    queryFn: () => apiClient.get<Enterprise[]>('/admin/enterprises').then((r) => r.data),
  })

  const error = overviewError || companiesError

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Platform Admin</h1>
          <p className="mt-1 text-sm text-gray-500">
            Overview of all tenants, companies, and usage across KAATS.
          </p>
        </div>
        <button
          onClick={() => { void refetchOverview(); void refetchCompanies() }}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Stat cards */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {overviewLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-2xl p-5 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-1/2 mb-3" />
              <div className="h-8 bg-gray-100 rounded w-3/4" />
            </div>
          ))
        ) : overview ? (
          <>
            <StatCard
              label="Enterprises"
              value={overview.total_enterprises}
              sub={`${overview.active_enterprises} active`}
              icon={<Building2 size={18} className="text-indigo-600" />}
              color="bg-indigo-50"
            />
            <StatCard
              label="Companies"
              value={overview.total_companies}
              sub={`${overview.active_companies} active`}
              icon={<Building2 size={18} className="text-blue-600" />}
              color="bg-blue-50"
            />
            <StatCard
              label="Users"
              value={formatNumber(overview.total_users)}
              sub="across all companies"
              icon={<Users size={18} className="text-green-600" />}
              color="bg-green-50"
            />
            <StatCard
              label="Agent Runs (MTD)"
              value={formatNumber(overview.agent_runs_this_month)}
              sub={`${formatNumber(overview.tokens_this_month)} tokens`}
              icon={<Bot size={18} className="text-orange-600" />}
              color="bg-orange-50"
            />
          </>
        ) : null}
      </section>

      {/* Companies table */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-base font-semibold text-gray-800">
            Companies
            {!companiesLoading && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({companies.length})
              </span>
            )}
          </h2>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={enterpriseFilter}
              onChange={(e) => setEnterpriseFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All enterprises</option>
              {enterprises.map((e) => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>

            <select
              value={planFilter}
              onChange={(e) => setPlanFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All plans</option>
              <option value="free">Free</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>

            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              Active only
            </label>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Enterprise</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Plan</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Users</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Systems</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Tokens (MTD)</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Runs (MTD)</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {companiesLoading ? (
                Array.from({ length: 5 }).map((_, i) => <RowSkeleton key={i} cols={10} />)
              ) : companies.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-10 text-center text-sm text-gray-500">
                    No companies found.
                  </td>
                </tr>
              ) : (
                companies.map((co) => (
                  <tr
                    key={co.id}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => navigate(`/admin/companies/${co.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900">{co.name}</p>
                        <p className="text-xs text-gray-400 font-mono">{co.slug}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{co.enterprise_name}</td>
                    <td className="px-4 py-3">
                      <PlanBadge tier={co.plan_tier} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                      {co.user_count}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                      {co.system_count}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                      <span title={String(co.tokens_this_month)}>
                        {formatNumber(co.tokens_this_month)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 tabular-nums">
                      {co.runs_this_month}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          co.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {co.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">{formatDate(co.created_at)}</td>
                    <td className="px-4 py-3">
                      <ChevronRight size={14} className="text-gray-400" />
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

export default function AdminDashboardPage() {
  const allowed = usePermission('admin:global')
  if (!allowed) return <AccessDenied />
  return <AdminDashboardContent />
}
