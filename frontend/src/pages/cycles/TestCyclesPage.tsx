import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X, Calendar, CheckCircle2, ChevronRight } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { TestCycleWithProgress, TestCycleStatus, User } from '@/types'
import RoleGate from '@/components/RoleGate'

// ── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  TestCycleStatus,
  { label: string; className: string }
> = {
  planned:     { label: 'Planned',     className: 'bg-blue-100 text-blue-700' },
  in_progress: { label: 'In Progress', className: 'bg-yellow-100 text-yellow-700' },
  completed:   { label: 'Completed',   className: 'bg-green-100 text-green-700' },
  aborted:     { label: 'Aborted',     className: 'bg-gray-100 text-gray-500' },
}

function StatusBadge({ status }: { status: TestCycleStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.planned
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function ProgressBar({
  progress,
}: {
  progress: TestCycleWithProgress['progress']
}) {
  const { total, passed, failed, blocked, pending } = progress
  if (total === 0) {
    return <div className="h-2 rounded-full bg-gray-100 w-full" />
  }
  const pct = (n: number) => `${Math.round((n / total) * 100)}%`
  return (
    <div className="h-2 rounded-full overflow-hidden flex w-full bg-gray-100">
      <div className="bg-green-500 h-full transition-all" style={{ width: pct(passed) }} />
      <div className="bg-red-500 h-full transition-all" style={{ width: pct(failed) }} />
      <div className="bg-orange-400 h-full transition-all" style={{ width: pct(blocked) }} />
      <div className="bg-gray-300 h-full transition-all" style={{ width: pct(pending) }} />
    </div>
  )
}

function CycleSkeleton() {
  return (
    <div className="animate-pulse bg-white border border-gray-200 rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="h-5 bg-gray-200 rounded w-48" />
        <div className="h-5 bg-gray-200 rounded w-20" />
      </div>
      <div className="h-2 bg-gray-200 rounded w-full" />
      <div className="flex gap-3">
        <div className="h-4 bg-gray-100 rounded w-24" />
        <div className="h-4 bg-gray-100 rounded w-24" />
      </div>
    </div>
  )
}

// ── New Cycle Form ────────────────────────────────────────────────────────────

interface NewCycleFormValues {
  name: string
  description: string
  planned_start: string
  planned_end: string
  lead_user_id: string
}

interface NewCycleModalProps {
  systemId: string
  onClose: () => void
  onCreated: () => void
}

function NewCycleModal({ systemId, onClose, onCreated }: NewCycleModalProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState<NewCycleFormValues>({
    name: '',
    description: '',
    planned_start: '',
    planned_end: '',
    lead_user_id: '',
  })
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { data: users } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => apiClient.get('/users').then((r) => r.data),
  })

  interface CreateCycleBody {
    name: string
    description: string
    system_id: string
    planned_start?: string
    planned_end?: string
    lead_user_id?: string
  }

  const mutation = useMutation({
    mutationFn: (body: CreateCycleBody) =>
      apiClient.post(`/systems/${systemId}/test-cycles`, body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['test-cycles', systemId] })
      onCreated()
    },
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    const body: CreateCycleBody = {
      name: form.name,
      description: form.description,
      system_id: systemId,
    }
    if (form.planned_start) body.planned_start = form.planned_start
    if (form.planned_end)   body.planned_end   = form.planned_end
    if (form.lead_user_id)  body.lead_user_id  = form.lead_user_id
    mutation.mutate(body)
  }

  function set(field: keyof NewCycleFormValues) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-cycle-title"
      >
        <button
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          onClick={onClose}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 id="new-cycle-title" className="text-lg font-semibold text-gray-900 mb-5">
          New Test Cycle
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={set('name')}
              required
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Sprint 24 Regression"
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Description</label>
            <textarea
              value={form.description}
              onChange={set('description')}
              rows={2}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Optional description…"
            />
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Planned Start</label>
              <input
                type="date"
                value={form.planned_start}
                onChange={set('planned_start')}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Planned End</label>
              <input
                type="date"
                value={form.planned_end}
                onChange={set('planned_end')}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Lead user */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Lead User</label>
            <select
              value={form.lead_user_id}
              onChange={set('lead_user_id')}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">— None —</option>
              {(users ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name ?? u.email}
                </option>
              ))}
            </select>
          </div>

          {submitError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {submitError}
            </p>
          )}

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
              type="submit"
              disabled={mutation.isPending || !form.name.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating…' : 'Create Cycle'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TestCyclesPage() {
  const { systemId } = useParams<{ systemId: string }>()
  const [showModal, setShowModal] = useState(false)

  const { data: cycles, isLoading, isError, error } = useQuery<TestCycleWithProgress[]>({
    queryKey: ['test-cycles', systemId],
    queryFn: () =>
      apiClient.get(`/systems/${systemId}/test-cycles`).then((r) => r.data),
    enabled: !!systemId,
  })

  if (!systemId) {
    return (
      <div className="p-8 text-center text-gray-500">System ID is missing from the URL.</div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Test Cycles</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage and track test execution cycles for this system.
          </p>
        </div>
        <RoleGate permission="cycle:create">
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
          >
            <Plus size={16} />
            New Cycle
          </button>
        </RoleGate>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <CycleSkeleton key={i} />
          ))}
        </div>
      )}

      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {!isLoading && !isError && cycles?.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <CheckCircle2 size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="text-base font-medium">No test cycles yet.</p>
          <p className="text-sm mt-1">Create the first cycle to start tracking test execution.</p>
        </div>
      )}

      {!isLoading && !isError && (cycles?.length ?? 0) > 0 && (
        <div className="space-y-3">
          {cycles!.map((cycle) => {
            const { total, passed } = cycle.progress
            const passRate = total > 0 ? Math.round((passed / total) * 100) : 0
            return (
              <Link
                key={cycle.id}
                to={`/test-cycles/${cycle.id}`}
                className="block bg-white border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-sm transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Row 1: name + status */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-base font-semibold text-gray-900 truncate">
                        {cycle.name}
                      </span>
                      <StatusBadge status={cycle.status} />
                    </div>

                    {/* Row 2: progress bar */}
                    <ProgressBar progress={cycle.progress} />

                    {/* Row 3: metric chips */}
                    <div className="flex items-center gap-4 flex-wrap text-xs text-gray-500">
                      <span className="inline-flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                        {passed}/{total} passed ({passRate}%)
                      </span>
                      {cycle.progress.failed > 0 && (
                        <span className="inline-flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                          {cycle.progress.failed} failed
                        </span>
                      )}
                      {cycle.progress.blocked > 0 && (
                        <span className="inline-flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-orange-400 inline-block" />
                          {cycle.progress.blocked} blocked
                        </span>
                      )}
                      {cycle.planned_end && (
                        <span className="inline-flex items-center gap-1 ml-auto">
                          <Calendar size={11} />
                          Due {new Date(cycle.planned_end).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>

                  <ChevronRight
                    size={18}
                    className="text-gray-300 group-hover:text-blue-400 transition-colors shrink-0 mt-1"
                  />
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <NewCycleModal
          systemId={systemId}
          onClose={() => setShowModal(false)}
          onCreated={() => setShowModal(false)}
        />
      )}
    </div>
  )
}
