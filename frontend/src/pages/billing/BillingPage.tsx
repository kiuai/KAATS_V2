import { useQuery, useMutation } from '@tanstack/react-query'
import { CreditCard, ExternalLink, Zap, Building2, Package } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import api from '@/lib/api'
import { usePermission } from '@/hooks/usePermission'
import AccessDenied from '@/components/common/AccessDenied'

interface BillingStatus {
  plan_tier: string
  monthly_token_limit: number | null
  monthly_run_limit: number | null
  stripe_configured: boolean
}

const PLAN_DETAILS: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
  free: {
    label: 'Free',
    icon: <Package size={20} className="text-gray-500" />,
    description: 'Perfect for evaluation and small teams.',
  },
  pro: {
    label: 'Pro',
    icon: <Zap size={20} className="text-blue-500" />,
    description: 'Unlimited agent runs and 5M tokens/month.',
  },
  enterprise: {
    label: 'Enterprise',
    icon: <Building2 size={20} className="text-purple-500" />,
    description: 'Custom limits, SLA, and dedicated support.',
  },
}

function PlanCard({
  tier,
  current,
  onUpgrade,
  loading,
}: {
  tier: string
  current: boolean
  onUpgrade: (tier: string) => void
  loading: boolean
}) {
  const details = PLAN_DETAILS[tier] ?? { label: tier, icon: null, description: '' }
  return (
    <div
      className={`border rounded-xl p-5 flex flex-col gap-3 ${
        current ? 'border-blue-500 bg-blue-50/30' : 'border-gray-200 bg-white'
      }`}
    >
      <div className="flex items-center gap-2">
        {details.icon}
        <h3 className="font-semibold text-gray-900">{details.label}</h3>
        {current && (
          <span className="ml-auto text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full">
            Current
          </span>
        )}
      </div>
      <p className="text-sm text-gray-500">{details.description}</p>
      {!current && tier !== 'free' && (
        <button
          disabled={loading}
          onClick={() => onUpgrade(tier)}
          className="mt-auto px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40"
        >
          {loading ? 'Redirecting…' : `Upgrade to ${details.label}`}
        </button>
      )}
    </div>
  )
}

export default function BillingPage() {
  const canManage = usePermission('admin:company')
  const [searchParams] = useSearchParams()
  const success = searchParams.get('success') === '1'
  const cancelled = searchParams.get('cancelled') === '1'

  const { data: status, isLoading } = useQuery<BillingStatus>({
    queryKey: ['billing-status'],
    queryFn: () => api.get('/billing/status').then((r) => r.data),
    enabled: canManage,
  })

  const checkout = useMutation({
    mutationFn: (plan_tier: string) =>
      api.post('/billing/checkout', { plan_tier }).then((r) => r.data),
    onSuccess: (data) => {
      if (data.checkout_url) window.location.href = data.checkout_url
      else alert(data.message ?? 'Billing not configured')
    },
  })

  const portal = useMutation({
    mutationFn: () => api.post('/billing/portal').then((r) => r.data),
    onSuccess: (data) => {
      if (data.portal_url) window.open(data.portal_url, '_blank')
      else alert(data.message ?? 'Billing not configured')
    },
  })

  if (!canManage) return <AccessDenied />

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <CreditCard size={24} className="text-gray-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing & Plans</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage your subscription and usage limits</p>
        </div>
      </div>

      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          Subscription activated successfully. Your plan will be updated shortly.
        </div>
      )}
      {cancelled && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700">
          Checkout cancelled. Your plan was not changed.
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <>
          {/* Current plan summary */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
            <p className="text-sm text-gray-500 mb-1">Current plan</p>
            <p className="text-xl font-bold text-gray-900 capitalize">{status?.plan_tier ?? 'free'}</p>
            <div className="mt-3 flex gap-6 text-sm">
              <div>
                <p className="text-gray-400 text-xs">Token limit / month</p>
                <p className="font-medium text-gray-700">
                  {status?.monthly_token_limit?.toLocaleString() ?? 'Unlimited'}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-xs">Agent run limit / month</p>
                <p className="font-medium text-gray-700">
                  {status?.monthly_run_limit?.toLocaleString() ?? 'Unlimited'}
                </p>
              </div>
            </div>
            {status?.stripe_configured && (
              <button
                onClick={() => portal.mutate()}
                disabled={portal.isPending}
                className="mt-4 flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800"
              >
                <ExternalLink size={14} />
                {portal.isPending ? 'Opening portal…' : 'Manage subscription & invoices'}
              </button>
            )}
          </div>

          {/* Plan cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['free', 'pro', 'enterprise'].map((tier) => (
              <PlanCard
                key={tier}
                tier={tier}
                current={status?.plan_tier === tier}
                onUpgrade={(t) => checkout.mutate(t)}
                loading={checkout.isPending}
              />
            ))}
          </div>

          {!status?.stripe_configured && (
            <p className="text-xs text-gray-400 mt-4 text-center">
              Stripe billing is not configured. Contact your platform administrator to enable self-serve upgrades.
            </p>
          )}
        </>
      )}
    </div>
  )
}
