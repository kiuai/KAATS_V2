import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Calendar, Clock } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { ScheduledJob, AgentType } from '@/types'
import RoleGate from '@/components/RoleGate'
import ConfirmDialog from '@/components/ConfirmDialog'
import { useSchedulePreview } from '@/hooks/useSchedulePreview'

// ── Helpers ───────────────────────────────────────────────────────────────────

const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  crawl:      'Crawl',
  generation: 'Generation',
  execution:  'Execution',
}

const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  crawl:      'bg-purple-100 text-purple-700',
  generation: 'bg-blue-100 text-blue-700',
  execution:  'bg-green-100 text-green-700',
}

function AgentTypeBadge({ type }: { type: AgentType }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${AGENT_TYPE_COLORS[type]}`}>
      {AGENT_TYPE_LABELS[type]}
    </span>
  )
}

function TableSkeleton() {
  return (
    <div className="animate-pulse divide-y divide-gray-100">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-4">
          <div className="h-4 bg-gray-200 rounded w-36" />
          <div className="h-5 bg-gray-100 rounded w-20" />
          <div className="h-4 bg-gray-100 rounded w-32 ml-auto" />
        </div>
      ))}
    </div>
  )
}

// ── Schedule row ──────────────────────────────────────────────────────────────

interface ScheduleRowProps {
  job: ScheduledJob
  onToggle: (job: ScheduledJob) => void
  onDelete: (job: ScheduledJob) => void
  isToggling: boolean
}

function ScheduleRow({ job, onToggle, onDelete, isToggling }: ScheduleRowProps) {
  const preview = useSchedulePreview(job.cron_expression)

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      {/* Name */}
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-gray-900">{job.name}</p>
          {job.description && (
            <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{job.description}</p>
          )}
        </div>
      </td>

      {/* Agent type */}
      <td className="px-4 py-3">
        <AgentTypeBadge type={job.agent_type} />
      </td>

      {/* Schedule */}
      <td className="px-4 py-3">
        <div>
          <p className="text-sm text-gray-700">{preview}</p>
          <p className="text-xs text-gray-400 font-mono mt-0.5">{job.cron_expression}</p>
        </div>
      </td>

      {/* Next run */}
      <td className="px-4 py-3 text-sm text-gray-600">
        {job.next_run_at ? (
          <span className="inline-flex items-center gap-1">
            <Clock size={12} className="text-gray-400" />
            {new Date(job.next_run_at).toLocaleString()}
          </span>
        ) : (
          '—'
        )}
      </td>

      {/* Last run */}
      <td className="px-4 py-3 text-sm text-gray-600">
        {job.last_run_at ? (
          <span className="inline-flex items-center gap-1">
            <Calendar size={12} className="text-gray-400" />
            {new Date(job.last_run_at).toLocaleString()}
          </span>
        ) : (
          '—'
        )}
      </td>

      {/* Enabled toggle */}
      <td className="px-4 py-3">
        <RoleGate permission="schedule:update">
          <button
            type="button"
            onClick={() => onToggle(job)}
            disabled={isToggling}
            aria-checked={job.is_enabled}
            role="switch"
            aria-label={job.is_enabled ? 'Disable schedule' : 'Enable schedule'}
            className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${
              job.is_enabled ? 'bg-blue-600' : 'bg-gray-200'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                job.is_enabled ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </RoleGate>
      </td>

      {/* Delete */}
      <td className="px-4 py-3">
        <RoleGate permission="schedule:delete">
          <button
            type="button"
            onClick={() => onDelete(job)}
            className="text-gray-400 hover:text-red-500 transition-colors"
            aria-label="Delete schedule"
          >
            <Trash2 size={15} />
          </button>
        </RoleGate>
      </td>
    </tr>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SchedulesPage() {
  const { systemId } = useParams<{ systemId: string }>()
  const qc = useQueryClient()
  const [jobToDelete, setJobToDelete] = useState<ScheduledJob | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)

  const { data: jobs, isLoading, isError, error } = useQuery<ScheduledJob[]>({
    queryKey: ['scheduled-jobs', systemId],
    queryFn: () =>
      apiClient.get(`/systems/${systemId}/scheduled-jobs`).then((r) => r.data),
    enabled: !!systemId,
  })

  const toggleMutation = useMutation({
    mutationFn: ({ jobId, is_enabled }: { jobId: string; is_enabled: boolean }) =>
      apiClient.patch(`/scheduled-jobs/${jobId}`, { is_enabled }).then((r) => r.data),
    onMutate: ({ jobId }) => setTogglingId(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scheduled-jobs', systemId] })
      setTogglingId(null)
    },
    onError: (err) => {
      setPageError(errorMessage(err))
      setTogglingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) =>
      apiClient.delete(`/scheduled-jobs/${jobId}`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scheduled-jobs', systemId] })
      setJobToDelete(null)
    },
    onError: (err) => {
      setPageError(errorMessage(err))
      setJobToDelete(null)
    },
  })

  if (!systemId) {
    return (
      <div className="p-8 text-center text-gray-500">System ID is missing from the URL.</div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Schedules</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Automate agent runs on a recurring schedule.
          </p>
        </div>
        <RoleGate permission="schedule:create">
          <Link
            to={`/systems/${systemId}/schedules/new`}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus size={16} />
            New Schedule
          </Link>
        </RoleGate>
      </div>

      {/* Page-level error */}
      {pageError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {pageError}
        </div>
      )}

      {/* Content */}
      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {isLoading ? (
          <TableSkeleton />
        ) : !isError && (jobs?.length ?? 0) === 0 ? (
          <div className="py-16 text-center text-gray-400">
            <Calendar size={36} className="mx-auto mb-3 text-gray-300" />
            <p className="text-base font-medium">No schedules configured.</p>
            <p className="text-sm mt-1">Create a schedule to automate agent runs.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Agent Type</th>
                  <th className="px-4 py-3 text-left">Schedule</th>
                  <th className="px-4 py-3 text-left">Next Run</th>
                  <th className="px-4 py-3 text-left">Last Run</th>
                  <th className="px-4 py-3 text-left">Enabled</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(jobs ?? []).map((job) => (
                  <ScheduleRow
                    key={job.id}
                    job={job}
                    onToggle={(j) =>
                      toggleMutation.mutate({ jobId: j.id, is_enabled: !j.is_enabled })
                    }
                    onDelete={(j) => setJobToDelete(j)}
                    isToggling={togglingId === job.id}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!jobToDelete}
        title="Delete Schedule"
        description={`Are you sure you want to delete "${jobToDelete?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => jobToDelete && deleteMutation.mutate(jobToDelete.id)}
        onCancel={() => setJobToDelete(null)}
      />
    </div>
  )
}
