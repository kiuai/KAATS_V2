import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { X, Plus, Trash2, Play, AlertCircle, Calendar, User } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type {
  TestCycle,
  TestCycleProgress,
  TestAssignment,
  TestAssignmentStatus,
  TestScript,
  User as UserType,
} from '@/types'
import RoleGate from '@/components/RoleGate'
import ConfirmDialog from '@/components/ConfirmDialog'
import { useAuthStore } from '@/store/authStore'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TestCycleDetail extends TestCycle {
  assignments: TestAssignment[]
  progress: TestCycleProgress & { skipped: number }
}

interface ExecuteAllResult {
  script_id: string
  agent_run_id: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const CYCLE_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  planned:     { label: 'Planned',     className: 'bg-blue-100 text-blue-700' },
  in_progress: { label: 'In Progress', className: 'bg-yellow-100 text-yellow-700' },
  completed:   { label: 'Completed',   className: 'bg-green-100 text-green-700' },
  aborted:     { label: 'Aborted',     className: 'bg-gray-100 text-gray-500' },
}

const ASSIGNMENT_STATUS_CONFIG: Record<
  TestAssignmentStatus,
  { label: string; className: string }
> = {
  pending:     { label: 'Pending',     className: 'bg-gray-100 text-gray-600' },
  in_progress: { label: 'In Progress', className: 'bg-yellow-100 text-yellow-700' },
  passed:      { label: 'Passed',      className: 'bg-green-100 text-green-700' },
  failed:      { label: 'Failed',      className: 'bg-red-100 text-red-700' },
  blocked:     { label: 'Blocked',     className: 'bg-orange-100 text-orange-700' },
  skipped:     { label: 'Skipped',     className: 'bg-blue-50 text-blue-500' },
}

const DONUT_COLORS = {
  passed:  '#22c55e',
  failed:  '#ef4444',
  blocked: '#f97316',
  pending: '#e5e7eb',
  skipped: '#3b82f6',
}

function CycleBadge({ status }: { status: string }) {
  const cfg = CYCLE_STATUS_CONFIG[status] ?? CYCLE_STATUS_CONFIG.planned
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function AssignmentBadge({ status }: { status: TestAssignmentStatus }) {
  const cfg = ASSIGNMENT_STATUS_CONFIG[status]
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function MetricCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6 animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-64" />
      <div className="grid grid-cols-2 gap-4 h-40 bg-gray-100 rounded-xl" />
      <div className="h-60 bg-gray-100 rounded-xl" />
    </div>
  )
}

// ── Assign Scripts Modal ──────────────────────────────────────────────────────

interface AssignRow {
  test_script_id: string
  assigned_to: string
  due_date: string
}

interface AssignScriptsModalProps {
  cycleId: string
  systemId: string
  onClose: () => void
  onAssigned: () => void
}

function AssignScriptsModal({ cycleId, systemId, onClose, onAssigned }: AssignScriptsModalProps) {
  const qc = useQueryClient()
  const [rows, setRows] = useState<AssignRow[]>([
    { test_script_id: '', assigned_to: '', due_date: '' },
  ])
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { data: scripts } = useQuery<TestScript[]>({
    queryKey: ['test-scripts', systemId, 'approved'],
    queryFn: () =>
      apiClient
        .get(`/systems/${systemId}/test-scripts`, { params: { status: 'approved' } })
        .then((r) => r.data),
  })

  const { data: users } = useQuery<UserType[]>({
    queryKey: ['users'],
    queryFn: () => apiClient.get('/users').then((r) => r.data),
  })

  const mutation = useMutation({
    mutationFn: (body: AssignRow[]) =>
      apiClient
        .post(`/test-cycles/${cycleId}/assignments`, body)
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['test-cycle', cycleId] })
      onAssigned()
    },
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  function addRow() {
    setRows((prev) => [...prev, { test_script_id: '', assigned_to: '', due_date: '' }])
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  function updateRow(index: number, field: keyof AssignRow, value: string) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    )
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    const valid = rows.filter((r) => r.test_script_id && r.assigned_to)
    if (valid.length === 0) {
      setSubmitError('Add at least one complete assignment row.')
      return
    }
    mutation.mutate(valid)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-scripts-title"
      >
        <button
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          onClick={onClose}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 id="assign-scripts-title" className="text-lg font-semibold text-gray-900 mb-5">
          Assign Scripts
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Column headers */}
          <div className="grid grid-cols-[1fr_1fr_140px_32px] gap-2 text-xs font-medium text-gray-500 uppercase tracking-wide px-1">
            <span>Script</span>
            <span>Tester</span>
            <span>Due Date</span>
            <span />
          </div>

          {rows.map((row, idx) => (
            <div key={idx} className="grid grid-cols-[1fr_1fr_140px_32px] gap-2 items-center">
              <select
                value={row.test_script_id}
                onChange={(e) => updateRow(idx, 'test_script_id', e.target.value)}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">— Select script —</option>
                {(scripts ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>

              <select
                value={row.assigned_to}
                onChange={(e) => updateRow(idx, 'assigned_to', e.target.value)}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">— Select tester —</option>
                {(users ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.display_name ?? u.email}
                  </option>
                ))}
              </select>

              <input
                type="date"
                value={row.due_date}
                onChange={(e) => updateRow(idx, 'due_date', e.target.value)}
                className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              <button
                type="button"
                onClick={() => removeRow(idx)}
                disabled={rows.length === 1}
                className="text-gray-400 hover:text-red-500 disabled:opacity-30"
                aria-label="Remove row"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}

          <button
            type="button"
            onClick={addRow}
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800"
          >
            <Plus size={14} />
            Add Row
          </button>

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
              disabled={mutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
            >
              {mutation.isPending ? 'Assigning…' : 'Assign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TestCycleDetailPage() {
  const { cycleId } = useParams<{ cycleId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)

  const [tab, setTab] = useState<'all' | 'mine'>('all')
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [showExecuteConfirm, setShowExecuteConfirm] = useState(false)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [showEditForm, setShowEditForm] = useState(false)
  const [executeResults, setExecuteResults] = useState<ExecuteAllResult[] | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: cycle, isLoading, isError, error } = useQuery<TestCycleDetail>({
    queryKey: ['test-cycle', cycleId],
    queryFn: () => apiClient.get(`/test-cycles/${cycleId}`).then((r) => r.data),
    enabled: !!cycleId,
  })

  const { data: users } = useQuery<UserType[]>({
    queryKey: ['users'],
    queryFn: () => apiClient.get('/users').then((r) => r.data),
    enabled: !!cycleId,
  })

  const updateMutation = useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      apiClient.patch(`/test-cycles/${cycleId}`, body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['test-cycle', cycleId] })
      setShowEditForm(false)
      setActionError(null)
    },
    onError: (err) => setActionError(errorMessage(err)),
  })

  const cancelMutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/test-cycles/${cycleId}/cancel`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['test-cycle', cycleId] })
      setShowCancelConfirm(false)
    },
    onError: (err) => setActionError(errorMessage(err)),
  })

  const executeMutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/test-cycles/${cycleId}/execute-all`).then((r) => r.data),
    onSuccess: (data: ExecuteAllResult[]) => {
      setExecuteResults(data)
      setShowExecuteConfirm(false)
      qc.invalidateQueries({ queryKey: ['test-cycle', cycleId] })
    },
    onError: (err) => {
      setActionError(errorMessage(err))
      setShowExecuteConfirm(false)
    },
  })

  const startAssignmentMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      apiClient
        .patch(`/test-cycles/${cycleId}/assignments/${assignmentId}`, {
          status: 'in_progress',
        })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['test-cycle', cycleId] }),
    onError: (err) => setActionError(errorMessage(err)),
  })

  function getUserName(userId: string | null): string {
    if (!userId) return '—'
    const u = (users ?? []).find((x) => x.id === userId)
    return u ? (u.display_name ?? u.email) : userId.slice(0, 8) + '…'
  }

  function openEditForm() {
    setEditName(cycle?.name ?? '')
    setEditDescription(cycle?.description ?? '')
    setShowEditForm(true)
  }

  if (isLoading) return <DetailSkeleton />

  if (isError) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      </div>
    )
  }

  if (!cycle) return null

  const progress = cycle.progress
  const passRate = progress.total > 0 ? Math.round((progress.passed / progress.total) * 100) : 0

  const donutData = [
    { name: 'Passed',  value: progress.passed,  color: DONUT_COLORS.passed },
    { name: 'Failed',  value: progress.failed,  color: DONUT_COLORS.failed },
    { name: 'Blocked', value: progress.blocked, color: DONUT_COLORS.blocked },
    { name: 'Pending', value: progress.pending, color: DONUT_COLORS.pending },
    { name: 'Skipped', value: progress.skipped ?? 0, color: DONUT_COLORS.skipped },
  ].filter((d) => d.value > 0)

  const displayedAssignments =
    tab === 'mine'
      ? (cycle.assignments ?? []).filter((a) => a.assigned_to === currentUser?.id)
      : (cycle.assignments ?? [])

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900">{cycle.name}</h1>
            <CycleBadge status={cycle.status} />
          </div>
          {cycle.description && (
            <p className="text-sm text-gray-500">{cycle.description}</p>
          )}
          <div className="flex flex-wrap gap-4 text-xs text-gray-500">
            {cycle.planned_start && (
              <span className="inline-flex items-center gap-1">
                <Calendar size={12} />
                Start: {new Date(cycle.planned_start).toLocaleDateString()}
              </span>
            )}
            {cycle.planned_end && (
              <span className="inline-flex items-center gap-1">
                <Calendar size={12} />
                End: {new Date(cycle.planned_end).toLocaleDateString()}
              </span>
            )}
            {cycle.lead_user_id && (
              <span className="inline-flex items-center gap-1">
                <User size={12} />
                Lead: {getUserName(cycle.lead_user_id)}
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <RoleGate permission="cycle:update">
            <button
              onClick={openEditForm}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Edit
            </button>
          </RoleGate>

          <RoleGate permission="assignment:create">
            <button
              onClick={() => setShowAssignModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
            >
              <Plus size={14} />
              Assign Scripts
            </button>
          </RoleGate>

          <RoleGate permission="agent:execute">
            <button
              onClick={() => setShowExecuteConfirm(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg"
            >
              <Play size={14} />
              Execute All
            </button>
          </RoleGate>

          {cycle.status !== 'completed' && cycle.status !== 'aborted' && (
            <RoleGate permission="cycle:update">
              <button
                onClick={() => setShowCancelConfirm(true)}
                className="px-3 py-1.5 text-sm font-medium text-red-700 border border-red-300 rounded-lg hover:bg-red-50"
              >
                Cancel Cycle
              </button>
            </RoleGate>
          )}
        </div>
      </div>

      {/* Action errors */}
      {actionError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          <AlertCircle size={15} className="shrink-0" />
          {actionError}
          <button
            className="ml-auto text-red-400 hover:text-red-600"
            onClick={() => setActionError(null)}
            aria-label="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Execute all results */}
      {executeResults && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-indigo-800">
              {executeResults.length} agent run(s) dispatched
            </p>
            <button
              onClick={() => setExecuteResults(null)}
              className="text-indigo-400 hover:text-indigo-600"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
          <div className="space-y-1">
            {executeResults.map((r) => (
              <div key={r.agent_run_id} className="flex items-center gap-2 text-xs text-indigo-700">
                <span className="font-mono truncate max-w-[180px]">
                  Script: {r.script_id.slice(0, 8)}…
                </span>
                <span>→</span>
                <Link
                  to={`/agents/${r.agent_run_id}`}
                  className="text-indigo-600 underline hover:text-indigo-800"
                >
                  Run {r.agent_run_id.slice(0, 8)}…
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress dashboard */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Progress</h2>
        <div className="flex flex-col md:flex-row gap-6 items-center">
          {/* Donut */}
          <div className="shrink-0">
            <ResponsiveContainer width={220} height={220}>
              <PieChart>
                <Pie
                  data={donutData.length > 0 ? donutData : [{ name: 'Empty', value: 1, color: '#e5e7eb' }]}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  dataKey="value"
                  paddingAngle={2}
                >
                  {(donutData.length > 0 ? donutData : [{ name: 'Empty', value: 1, color: '#e5e7eb' }]).map(
                    (entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ),
                  )}
                </Pie>
                <Tooltip
                  formatter={(value: number, name: string) => [value, name]}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => (
                    <span className="text-xs text-gray-600">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Metric cards */}
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-3 w-full">
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-center col-span-2 sm:col-span-3">
              <div className="text-3xl font-bold text-blue-700">{passRate}%</div>
              <div className="text-xs text-blue-500 mt-0.5">Pass Rate</div>
            </div>
            <MetricCard label="Total" value={progress.total} color="text-gray-700" />
            <MetricCard label="Passed" value={progress.passed} color="text-green-600" />
            <MetricCard label="Failed" value={progress.failed} color="text-red-600" />
            <MetricCard label="Blocked" value={progress.blocked} color="text-orange-500" />
            <MetricCard label="Pending" value={progress.pending} color="text-gray-500" />
            <MetricCard label="Skipped" value={progress.skipped ?? 0} color="text-blue-500" />
          </div>
        </div>
      </div>

      {/* Assignments table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {/* Tabs */}
        <div className="border-b border-gray-200 flex">
          {(['all', 'mine'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t === 'all' ? 'All Assignments' : 'My Assignments'}
            </button>
          ))}
        </div>

        {/* Table */}
        {displayedAssignments.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">
            No assignments found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">Script</th>
                  <th className="px-4 py-3 text-left">Assigned To</th>
                  <th className="px-4 py-3 text-left">Due Date</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {displayedAssignments.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-gray-800">
                      <Link
                        to={`/test-cycles/${cycleId}/assignments/${a.id}/execute`}
                        className="text-blue-600 hover:underline truncate max-w-[200px] block"
                        title={a.test_script_id}
                      >
                        {a.test_script_id.slice(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {getUserName(a.assigned_to)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {a.due_date
                        ? new Date(a.due_date).toLocaleDateString()
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <AssignmentBadge status={a.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {(a.status === 'pending' || a.status === 'in_progress') && (
                          <RoleGate permission="assignment:update">
                            {a.status === 'pending' && (
                              <button
                                onClick={() => startAssignmentMutation.mutate(a.id)}
                                disabled={startAssignmentMutation.isPending}
                                className="px-2.5 py-1 text-xs font-medium text-white bg-yellow-500 hover:bg-yellow-600 rounded-md disabled:opacity-50"
                              >
                                Start
                              </button>
                            )}
                            <Link
                              to={`/test-cycles/${cycleId}/assignments/${a.id}/execute`}
                              className="px-2.5 py-1 text-xs font-medium text-blue-700 border border-blue-300 rounded-md hover:bg-blue-50"
                            >
                              Execute
                            </Link>
                          </RoleGate>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      {showAssignModal && cycle && (
        <AssignScriptsModal
          cycleId={cycle.id}
          systemId={cycle.system_id}
          onClose={() => setShowAssignModal(false)}
          onAssigned={() => setShowAssignModal(false)}
        />
      )}

      {/* Inline edit form */}
      {showEditForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setShowEditForm(false)}
        >
          <div
            className="relative bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <button
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
              onClick={() => setShowEditForm(false)}
              aria-label="Close"
            >
              <X size={18} />
            </button>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Edit Cycle</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                updateMutation.mutate({ name: editName, description: editDescription })
              }}
              className="space-y-4"
            >
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700">Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowEditForm(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateMutation.isPending || !editName.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
                >
                  {updateMutation.isPending ? 'Saving…' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Execute all confirm */}
      <ConfirmDialog
        open={showExecuteConfirm}
        title="Execute All Scripts"
        description="This will dispatch automated agent runs for all assigned test scripts in this cycle. Continue?"
        confirmLabel="Execute All"
        loading={executeMutation.isPending}
        onConfirm={() => executeMutation.mutate()}
        onCancel={() => setShowExecuteConfirm(false)}
      />

      {/* Cancel cycle confirm */}
      <ConfirmDialog
        open={showCancelConfirm}
        title="Cancel Test Cycle"
        description="This will mark the test cycle as aborted. This action cannot be undone."
        confirmLabel="Cancel Cycle"
        destructive
        loading={cancelMutation.isPending}
        onConfirm={() => cancelMutation.mutate()}
        onCancel={() => setShowCancelConfirm(false)}
      />
    </div>
  )
}
