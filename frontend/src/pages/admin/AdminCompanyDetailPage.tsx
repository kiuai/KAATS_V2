import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Users,
  Server,
  Bot,
  Zap,
  Pencil,
  X,
  Check,
} from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { usePermission } from '@/hooks/usePermission'
import type { CompanyAdminDetail } from '@/types'

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

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-gray-100 text-gray-600',
  pro: 'bg-blue-100 text-blue-700',
  enterprise: 'bg-purple-100 text-purple-700',
}

function PlanBadge({ tier }: { tier: string }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${
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
  value: string
  icon: React.ReactNode
  color: string
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-lg font-bold text-gray-900">{value}</p>
      </div>
    </div>
  )
}

// ── usage history bars ────────────────────────────────────────────────────

interface UsageHistoryProps {
  history: CompanyAdminDetail['usage_history']
}

function UsageHistory({ history }: UsageHistoryProps) {
  if (history.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-6">No usage data yet.</p>
    )
  }

  const maxTokens = Math.max(...history.map((h) => h.total_tokens), 1)

  return (
    <div className="space-y-3">
      {[...history].reverse().map((h) => {
        const pct = Math.max((h.total_tokens / maxTokens) * 100, 2)
        const label = `${MONTH_NAMES[h.month - 1]} ${h.year}`
        return (
          <div key={`${h.year}-${h.month}`} className="flex items-center gap-3">
            <span className="text-xs text-gray-400 w-14 shrink-0 text-right">{label}</span>
            <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300 flex items-center"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 w-16 shrink-0 tabular-nums">
              {formatNumber(h.total_tokens)}
            </span>
            <span className="text-xs text-gray-400 w-14 shrink-0 tabular-nums">
              {h.agent_runs} run{h.agent_runs !== 1 ? 's' : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── change plan modal ────────────────────────────────────────────────────

interface ChangePlanModalProps {
  companyId: string
  currentTier: string
  onClose: () => void
}

function ChangePlanModal({ companyId, currentTier, onClose }: ChangePlanModalProps) {
  const qc = useQueryClient()
  const [tier, setTier] = useState(currentTier)
  const [reason, setReason] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      apiClient
        .patch(`/admin/companies/${companyId}/plan`, {
          plan_tier: tier,
          override_reason: reason || null,
        })
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin-company', companyId] })
      await qc.invalidateQueries({ queryKey: ['admin-companies'] })
      onClose()
    },
    onError: (err) => setFormError(errorMessage(err)),
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="change-plan-title"
      >
        <button
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          onClick={onClose}
        >
          <X size={18} />
        </button>

        <h2 id="change-plan-title" className="text-base font-semibold text-gray-900 mb-5">
          Change Plan
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Plan tier</label>
            <div className="grid grid-cols-3 gap-2">
              {(['free', 'pro', 'enterprise'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTier(t)}
                  className={`py-2 px-3 rounded-lg text-sm font-medium border transition-colors capitalize ${
                    tier === t
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="override-reason" className="block text-sm font-medium text-gray-700 mb-1">
              Reason <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              id="override-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Annual contract, trial extension"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {formError && <p className="text-sm text-red-600">{formError}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={mutation.isPending}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending || tier === currentTier}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check size={14} />
              {mutation.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
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

// ── page ──────────────────────────────────────────────────────────────────

function AdminCompanyDetailContent({ companyId }: { companyId: string }) {
  const navigate = useNavigate()
  const [showChangePlan, setShowChangePlan] = useState(false)

  const {
    data: company,
    isLoading,
    error,
  } = useQuery<CompanyAdminDetail>({
    queryKey: ['admin-company', companyId],
    queryFn: () =>
      apiClient.get<CompanyAdminDetail>(`/admin/companies/${companyId}`).then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-6 animate-pulse">
        <div className="h-6 bg-gray-100 rounded w-48" />
        <div className="h-32 bg-gray-100 rounded-2xl" />
        <div className="h-48 bg-gray-100 rounded-2xl" />
      </div>
    )
  }

  if (error || !company) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error ? errorMessage(error) : 'Company not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate('/admin')}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-4"
        >
          <ArrowLeft size={14} />
          Platform Admin
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900">{company.name}</h1>
              <span
                className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                  company.is_active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-500'
                }`}
              >
                {company.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              <span className="font-mono">{company.slug}</span>
              {' · '}
              {company.enterprise_name}
              {company.industry ? ` · ${company.industry}` : ''}
              {' · '}
              Created {formatDate(company.created_at)}
            </p>
          </div>

          {/* Plan card */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Current plan</p>
              <PlanBadge tier={company.plan_tier} />
              {company.monthly_token_limit != null && (
                <p className="text-xs text-gray-400 mt-1">
                  {formatNumber(company.monthly_token_limit)} tokens/mo
                </p>
              )}
            </div>
            <button
              onClick={() => setShowChangePlan(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <Pencil size={11} />
              Change
            </button>
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Users"
          value={String(company.user_count)}
          icon={<Users size={16} className="text-blue-600" />}
          color="bg-blue-50"
        />
        <StatCard
          label="Systems"
          value={String(company.system_count)}
          icon={<Server size={16} className="text-indigo-600" />}
          color="bg-indigo-50"
        />
        <StatCard
          label="Tokens (MTD)"
          value={formatNumber(company.tokens_this_month)}
          icon={<Zap size={16} className="text-amber-600" />}
          color="bg-amber-50"
        />
        <StatCard
          label="Agent Runs (MTD)"
          value={String(company.runs_this_month)}
          icon={<Bot size={16} className="text-green-600" />}
          color="bg-green-50"
        />
      </section>

      {/* Usage history */}
      <section className="bg-white border border-gray-200 rounded-2xl p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-5">
          Token Usage — Last 6 Months
        </h2>
        <UsageHistory history={company.usage_history} />
      </section>

      {/* Change plan modal */}
      {showChangePlan && (
        <ChangePlanModal
          companyId={company.id}
          currentTier={company.plan_tier}
          onClose={() => setShowChangePlan(false)}
        />
      )}
    </div>
  )
}

export default function AdminCompanyDetailPage() {
  const { companyId } = useParams<{ companyId: string }>()
  const allowed = usePermission('admin:global')
  if (!allowed) return <AccessDenied />
  if (!companyId) return null
  return <AdminCompanyDetailContent companyId={companyId} />
}
