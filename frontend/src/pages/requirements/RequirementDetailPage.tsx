import { useState, useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Lightbulb,
  Zap,
  Trash2,
  Save,
  X,
  CheckCircle,
} from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type {
  RequirementWithScripts,
  QualityCheckResult,
  RequirementPriority,
  RequirementStatus,
  Page,
  TestScript,
} from '@/types'
import RoleGate from '@/components/RoleGate'
import ConfirmDialog from '@/components/ConfirmDialog'
import { usePermission } from '@/hooks/usePermission'

// ── Grade helpers ──────────────────────────────────────────────────────────

function gradeBg(grade: string): string {
  switch (grade) {
    case 'A': return 'bg-green-100 text-green-700'
    case 'B': return 'bg-blue-100 text-blue-700'
    case 'C': return 'bg-yellow-100 text-yellow-700'
    case 'D': return 'bg-orange-100 text-orange-700'
    default:  return 'bg-red-100 text-red-700'
  }
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

// ── Quality check panel ────────────────────────────────────────────────────

function QualityCheckPanel({ requirementId }: { requirementId: string }) {
  const { data, isLoading, error } = useQuery<QualityCheckResult>({
    queryKey: ['quality-check', requirementId],
    queryFn: () =>
      apiClient
        .get<QualityCheckResult>(`/requirements/${requirementId}/quality-check`)
        .then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-20 bg-gray-100 rounded-xl" />
        <div className="h-4 bg-gray-100 rounded w-3/4" />
        <div className="h-4 bg-gray-100 rounded w-2/3" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {errorMessage(error)}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-4">
      {/* Score gauge */}
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className={`text-5xl font-bold ${scoreColor(data.score)}`}>
            {data.score}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">/ 100</div>
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-bold ${gradeBg(data.grade)}`}
            >
              Grade {data.grade}
            </span>
            {data.cached && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">
                cached
              </span>
            )}
          </div>
          {/* Score bar */}
          <div className="w-40 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                data.score >= 80
                  ? 'bg-green-500'
                  : data.score >= 60
                  ? 'bg-yellow-500'
                  : 'bg-red-500'
              }`}
              style={{ width: `${data.score}%` }}
            />
          </div>
        </div>
      </div>

      {/* Suggestions */}
      {data.suggestions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Suggestions
          </p>
          <ul className="space-y-2">
            {data.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <Lightbulb size={14} className="text-yellow-500 mt-0.5 shrink-0" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Generate Script Modal ──────────────────────────────────────────────────

const EXPORT_FORMATS = ['playwright', 'selenium', 'pytest', 'robot', 'gherkin'] as const
type ExportFormat = (typeof EXPORT_FORMATS)[number]

interface GenerateScriptModalProps {
  open: boolean
  requirementId: string
  onClose: () => void
}

function GenerateScriptModal({ open, requirementId, onClose }: GenerateScriptModalProps) {
  const [format, setFormat] = useState<ExportFormat>('playwright')
  const [agentRunId, setAgentRunId] = useState<string | null>(null)
  const [genError, setGenError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      apiClient
        .post<{ agent_run_id: string }>(`/requirements/${requirementId}/generate-script`, {
          export_format: format,
        })
        .then((r) => r.data),
    onSuccess: (data) => setAgentRunId(data.agent_run_id),
    onError: (err) => setGenError(errorMessage(err)),
  })

  const handleClose = () => {
    setAgentRunId(null)
    setGenError(null)
    mutation.reset()
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900">Generate Test Script</h3>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {agentRunId ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle size={16} className="text-green-600 shrink-0" />
              <div>
                <p className="text-sm font-medium text-green-800">Generation started</p>
                <p className="text-xs text-green-600 font-mono mt-0.5">{agentRunId}</p>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Close
              </button>
              <Link
                to={`/agents/${agentRunId}`}
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                View Agent Run
              </Link>
            </div>
          </div>
        ) : (
          <>
            {genError && (
              <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {genError}
              </div>
            )}
            <div className="mb-5">
              <label className="block text-sm font-medium text-gray-700 mb-1">Export Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {EXPORT_FORMATS.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Zap size={14} />
                {mutation.isPending ? 'Dispatching…' : 'Generate'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function RequirementDetailPage() {
  const { requirementId = '' } = useParams<{ requirementId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const canUpdate = usePermission('req:update')

  // Form state (mirrors fetched data)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<RequirementStatus>('draft')
  const [priority, setPriority] = useState<RequirementPriority>('medium')
  const [businessDomain, setBusinessDomain] = useState('')
  const [sourceReference, setSourceReference] = useState('')

  const [formDirty, setFormDirty] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [generateModalOpen, setGenerateModalOpen] = useState(false)

  const { data: requirement, isLoading, error } = useQuery<RequirementWithScripts>({
    queryKey: ['requirement', requirementId],
    queryFn: () =>
      apiClient
        .get<RequirementWithScripts>(`/requirements/${requirementId}`)
        .then((r) => r.data),
    enabled: !!requirementId,
  })

  // Initialise form fields when data first loads (not on every re-render)
  useEffect(() => {
    if (requirement && !formDirty) {
      setTitle(requirement.title)
      setDescription(requirement.description)
      setStatus(requirement.status)
      setPriority(requirement.priority)
      setBusinessDomain(requirement.business_domain ?? '')
      setSourceReference(requirement.source_reference ?? '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requirement?.id])

  // Fetch linked scripts
  const { data: scriptsPage } = useQuery<Page<TestScript>>({
    queryKey: ['test-scripts', requirement?.system_id, requirementId],
    queryFn: () =>
      apiClient
        .get<Page<TestScript>>(
          `/systems/${requirement!.system_id}/test-scripts?limit=10&offset=0`,
        )
        .then((r) => r.data),
    enabled: !!requirement?.system_id,
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      apiClient.patch(`/requirements/${requirementId}`, {
        title,
        description,
        status,
        priority,
        business_domain: businessDomain || null,
        source_reference: sourceReference || null,
      }),
    onSuccess: () => {
      setSaveError(null)
      setFormDirty(false)
      queryClient.invalidateQueries({ queryKey: ['requirement', requirementId] })
    },
    onError: (err) => setSaveError(errorMessage(err)),
  })

  const deleteMutation = useMutation({
    mutationFn: () => apiClient.delete(`/requirements/${requirementId}`),
    onSuccess: () => {
      if (requirement?.system_id) {
        navigate(`/systems/${requirement.system_id}/requirements`)
      } else {
        navigate(-1)
      }
    },
    onError: (err) => setSaveError(errorMessage(err)),
  })

  if (isLoading) {
    return (
      <div className="p-6 animate-pulse space-y-4">
        <div className="h-6 bg-gray-200 rounded w-1/3" />
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-3">
            <div className="h-10 bg-gray-100 rounded" />
            <div className="h-32 bg-gray-100 rounded" />
            <div className="h-10 bg-gray-100 rounded w-1/2" />
          </div>
          <div className="space-y-3">
            <div className="h-24 bg-gray-100 rounded" />
            <div className="h-16 bg-gray-100 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      </div>
    )
  }

  if (!requirement) return null

  const field = (setter: (v: string) => void) => (v: string) => {
    setter(v)
    setFormDirty(true)
  }

  const linkedScripts = scriptsPage?.items.filter(
    (s) => s.requirement_id === requirementId,
  ) ?? []

  return (
    <div className="p-6 space-y-5">
      {/* Back link */}
      <Link
        to={`/systems/${requirement.system_id}/requirements`}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft size={14} />
        Back to Requirements
      </Link>

      {saveError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {saveError}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6 items-start">
        {/* Left panel — form */}
        <div className="col-span-2 bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold text-gray-900 truncate">{requirement.title}</h1>
            <div className="flex items-center gap-2">
              {canUpdate && formDirty && (
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  <Save size={14} />
                  {saveMutation.isPending ? 'Saving…' : 'Save Changes'}
                </button>
              )}
              <RoleGate permission="req:delete">
                <button
                  onClick={() => setDeleteDialogOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50"
                >
                  <Trash2 size={14} />
                  Delete
                </button>
              </RoleGate>
            </div>
          </div>

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => field(setTitle)(e.target.value)}
              disabled={!canUpdate}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => field(setDescription)(e.target.value)}
              disabled={!canUpdate}
              rows={6}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500 resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Status */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => field(setStatus)(e.target.value as RequirementStatus)}
                disabled={!canUpdate}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="deprecated">Deprecated</option>
              </select>
            </div>

            {/* Priority */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => field(setPriority)(e.target.value as RequirementPriority)}
                disabled={!canUpdate}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Source type (read-only display) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Type</label>
              <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
                {requirement.source_type}
              </div>
            </div>

            {/* Source reference */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source Reference</label>
              <input
                type="text"
                value={sourceReference}
                onChange={(e) => field(setSourceReference)(e.target.value)}
                disabled={!canUpdate}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
                placeholder="e.g. JIRA-123"
              />
            </div>
          </div>

          {/* Business domain */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Business Domain</label>
            <input
              type="text"
              value={businessDomain}
              onChange={(e) => field(setBusinessDomain)(e.target.value)}
              disabled={!canUpdate}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Tags */}
          {requirement.tags && requirement.tags.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Tags</label>
              <div className="flex flex-wrap gap-1.5">
                {requirement.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Meta row */}
          <div className="pt-2 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
            <span>ID: <span className="font-mono">{requirement.id}</span></span>
            <span>Created: {new Date(requirement.created_at).toLocaleString()}</span>
            <span>Updated: {new Date(requirement.updated_at).toLocaleString()}</span>
          </div>
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Quality check */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">AI Quality Check</h2>
            <QualityCheckPanel requirementId={requirementId} />
          </div>

          {/* Linked scripts */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700">Test Scripts</h2>
              <RoleGate permission="agent:generate">
                <button
                  onClick={() => setGenerateModalOpen(true)}
                  className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
                >
                  <Zap size={12} />
                  Generate
                </button>
              </RoleGate>
            </div>

            {/* Counts */}
            <div className="flex items-center gap-3 mb-3">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{requirement.script_count}</div>
                <div className="text-xs text-gray-500">Total</div>
              </div>
              <div className="w-px h-8 bg-gray-200" />
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{requirement.approved_script_count}</div>
                <div className="text-xs text-gray-500">Approved</div>
              </div>
            </div>

            {/* Script list */}
            {linkedScripts.length > 0 ? (
              <ul className="space-y-1">
                {linkedScripts.map((script) => (
                  <li key={script.id}>
                    <Link
                      to={`/test-scripts/${script.id}`}
                      className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 group"
                    >
                      <span className="text-sm text-gray-700 truncate group-hover:text-blue-600">
                        {script.title}
                      </span>
                      <span className="ml-2 text-xs text-gray-400 shrink-0">{script.format}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-400 text-center py-2">No scripts yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* Delete dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Requirement"
        description="This will permanently delete the requirement and cannot be undone. Any linked test scripts will remain."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setDeleteDialogOpen(false)}
      />

      {/* Generate modal */}
      <GenerateScriptModal
        open={generateModalOpen}
        requirementId={requirementId}
        onClose={() => setGenerateModalOpen(false)}
      />
    </div>
  )
}
