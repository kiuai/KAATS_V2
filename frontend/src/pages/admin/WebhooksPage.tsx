import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import { format } from 'date-fns'
import api from '@/lib/api'
import { usePermission } from '@/hooks/usePermission'
import AccessDenied from '@/components/common/AccessDenied'

interface WebhookEndpoint {
  id: string
  company_id: string
  url: string
  event_types: string[] | null
  is_active: boolean
  description: string | null
  created_at: string
}

interface WebhookDelivery {
  id: string
  endpoint_id: string
  event_type: string
  response_status: number | null
  status: string
  attempt: number
  created_at: string
}

const ALL_EVENTS = [
  'agent.dispatched',
  'agent.completed',
  'user.deactivated',
  'user.role_assigned',
  'invitation.created',
  'invitation.accepted',
  'plan.updated',
]

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === 'success'
      ? 'bg-green-100 text-green-700'
      : status === 'failed'
      ? 'bg-red-100 text-red-700'
      : 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

function EndpointRow({ ep, onDelete }: { ep: WebhookEndpoint; onDelete: () => void }) {
  const [showDeliveries, setShowDeliveries] = useState(false)
  const { data: deliveries = [] } = useQuery<WebhookDelivery[]>({
    queryKey: ['webhook-deliveries', ep.id],
    queryFn: () => api.get(`/webhooks/${ep.id}/deliveries`).then((r) => r.data),
    enabled: showDeliveries,
  })

  return (
    <div className="border border-gray-200 rounded-xl mb-3 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-white">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{ep.url}</p>
          {ep.description && <p className="text-xs text-gray-500 mt-0.5">{ep.description}</p>}
          <div className="flex gap-1 mt-1 flex-wrap">
            {(ep.event_types ?? ['all events']).map((e) => (
              <span key={e} className="bg-blue-50 text-blue-700 text-[10px] px-1.5 py-0.5 rounded">
                {e}
              </span>
            ))}
          </div>
        </div>
        <StatusBadge status={ep.is_active ? 'active' : 'inactive'} />
        <button
          onClick={() => setShowDeliveries((v) => !v)}
          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 text-xs flex items-center gap-1"
        >
          {showDeliveries ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          Log
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {showDeliveries && (
        <div className="border-t border-gray-100 bg-gray-50 px-4 py-3">
          <p className="text-xs font-semibold text-gray-500 mb-2">Recent Deliveries</p>
          {deliveries.length === 0 ? (
            <p className="text-xs text-gray-400">No deliveries yet.</p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-400">
                  <th className="text-left pb-1">Event</th>
                  <th className="text-left pb-1">Status</th>
                  <th className="text-left pb-1">HTTP</th>
                  <th className="text-left pb-1">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {deliveries.map((d) => (
                  <tr key={d.id}>
                    <td className="py-1 pr-3 text-gray-600">{d.event_type}</td>
                    <td className="py-1 pr-3"><StatusBadge status={d.status} /></td>
                    <td className="py-1 pr-3 font-mono">{d.response_status ?? '—'}</td>
                    <td className="py-1 text-gray-400">{format(new Date(d.created_at), 'HH:mm:ss MM/dd')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default function WebhooksPage() {
  const canManage = usePermission('admin:company')
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [url, setUrl] = useState('')
  const [desc, setDesc] = useState('')
  const [secret, setSecret] = useState('')
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])

  const { data: endpoints = [], isLoading } = useQuery<WebhookEndpoint[]>({
    queryKey: ['webhooks'],
    queryFn: () => api.get('/webhooks').then((r) => r.data),
    enabled: canManage,
  })

  const create = useMutation({
    mutationFn: () =>
      api.post('/webhooks', {
        url,
        description: desc || null,
        secret: secret || null,
        event_types: selectedEvents.length > 0 ? selectedEvents : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
      setShowForm(false)
      setUrl('')
      setDesc('')
      setSecret('')
      setSelectedEvents([])
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/webhooks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  })

  if (!canManage) return <AccessDenied />

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Webhooks</h1>
          <p className="text-sm text-gray-500 mt-1">
            Receive real-time event notifications via HTTP POST
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
        >
          <Plus size={16} /> Add Endpoint
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-800">New Webhook Endpoint</h2>
          <input
            type="url"
            placeholder="https://your-server.com/webhook"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            placeholder="Description (optional)"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            placeholder="Signing secret (optional)"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <div>
            <p className="text-xs font-medium text-gray-600 mb-2">
              Event types (leave empty to receive all)
            </p>
            <div className="flex flex-wrap gap-2">
              {ALL_EVENTS.map((e) => (
                <label key={e} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(e)}
                    onChange={(ev) =>
                      setSelectedEvents((prev) =>
                        ev.target.checked ? [...prev, e] : prev.filter((x) => x !== e)
                      )
                    }
                    className="rounded"
                  />
                  <span className="text-xs text-gray-700">{e}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              disabled={!url || create.isPending}
              onClick={() => create.mutate()}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40"
            >
              {create.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-gray-300 text-sm rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : endpoints.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-sm">No webhook endpoints configured.</p>
          <p className="text-xs mt-1">Add one to receive event notifications.</p>
        </div>
      ) : (
        endpoints.map((ep) => (
          <EndpointRow key={ep.id} ep={ep} onDelete={() => remove.mutate(ep.id)} />
        ))
      )}
    </div>
  )
}
