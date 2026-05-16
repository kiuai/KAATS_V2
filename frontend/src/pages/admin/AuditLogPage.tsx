import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Filter } from 'lucide-react'
import api from '@/services/api'
import { usePermission } from '@/hooks/usePermission'

function AccessDenied() {
  return <div className="p-8 text-center text-gray-400">You don't have permission to view this page.</div>
}

interface AuditLog {
  id: string
  actor_user_id: string | null
  actor_email: string | null
  company_id: string | null
  event_type: string
  resource_type: string | null
  resource_id: string | null
  changes: Record<string, unknown> | null
  ip_address: string | null
  correlation_id: string | null
  created_at: string
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  'user.login': 'bg-blue-100 text-blue-700',
  'user.deactivated': 'bg-red-100 text-red-700',
  'user.role_assigned': 'bg-green-100 text-green-700',
  'user.role_revoked': 'bg-orange-100 text-orange-700',
  'invitation.created': 'bg-purple-100 text-purple-700',
  'invitation.accepted': 'bg-teal-100 text-teal-700',
  'agent.dispatched': 'bg-indigo-100 text-indigo-700',
  'plan.updated': 'bg-yellow-100 text-yellow-700',
}

function eventBadge(eventType: string) {
  const cls = EVENT_TYPE_COLORS[eventType] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {eventType}
    </span>
  )
}

export default function AuditLogPage() {
  const canReadGlobal = usePermission('admin:global')
  const canReadEnterprise = usePermission('admin:enterprise')
  const canRead = canReadGlobal || canReadEnterprise
  const [eventTypeFilter, setEventTypeFilter] = useState('')
  const [skip, setSkip] = useState(0)
  const limit = 50

  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) })
  if (eventTypeFilter) params.set('event_type', eventTypeFilter)

  const { data: logs = [], isLoading } = useQuery<AuditLog[]>({
    queryKey: ['audit-logs', eventTypeFilter, skip],
    queryFn: () => api.get(`/audit/logs?${params}`).then((r) => r.data),
    enabled: canRead,
  })

  if (!canRead) return <AccessDenied />

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-sm text-gray-500 mt-1">Immutable record of security-relevant actions</p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative">
          <Filter size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
          <input
            type="text"
            placeholder="Filter by event type…"
            value={eventTypeFilter}
            onChange={(e) => { setEventTypeFilter(e.target.value); setSkip(0) }}
            className="pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
          />
        </div>
        <span className="ml-auto text-sm text-gray-500 self-center">
          Showing {logs.length} entries
        </span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">No audit logs found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 w-44">Timestamp</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Event</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Actor</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Resource</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50 group">
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap font-mono text-xs">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">{eventBadge(log.event_type)}</td>
                    <td className="px-4 py-3 text-gray-700 truncate max-w-xs">
                      {log.actor_email ?? <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {log.resource_type ? (
                        <span>
                          <span className="font-medium text-gray-700">{log.resource_type}</span>
                          {log.resource_id && <span className="ml-1 font-mono">{log.resource_id.slice(0, 8)}…</span>}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs font-mono">
                      {log.ip_address ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center mt-4">
        <button
          disabled={skip === 0}
          onClick={() => setSkip(Math.max(0, skip - limit))}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
        >
          Previous
        </button>
        <span className="text-sm text-gray-500">Page {Math.floor(skip / limit) + 1}</span>
        <button
          disabled={logs.length < limit}
          onClick={() => setSkip(skip + limit)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
