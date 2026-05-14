import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  RotateCcw,
  Download,
  Send,
  Clock,
  Zap,
  X,
  ChevronDown,
  AlertTriangle,
} from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { TestScript, TestScriptStatus, TestScriptVersion } from '@/types'
import RoleGate from '@/components/RoleGate'
import ScriptEditor from '@/components/ScriptEditor'
import LiveAgentRunCard from '@/components/LiveAgentRunCard'
import { usePermission } from '@/hooks/usePermission'

// ── Constants ──────────────────────────────────────────────────────────────

const EXPORT_FORMATS = ['playwright', 'selenium', 'pytest', 'robot', 'gherkin'] as const
type ExportFormat = (typeof EXPORT_FORMATS)[number]

// ── Badge helpers ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: TestScriptStatus }) {
  const styles: Record<TestScriptStatus, string> = {
    draft: 'bg-gray-100 text-gray-700',
    in_review: 'bg-yellow-100 text-yellow-700',
    approved: 'bg-green-100 text-green-700',
    deprecated: 'bg-red-100 text-red-700',
  }
  const labels: Record<TestScriptStatus, string> = {
    draft: 'Draft',
    in_review: 'In Review',
    approved: 'Approved',
    deprecated: 'Deprecated',
  }
  const dots: Record<TestScriptStatus, string> = {
    draft: 'bg-gray-400',
    in_review: 'bg-yellow-400',
    approved: 'bg-green-500',
    deprecated: 'bg-red-500',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dots[status]}`} />
      {labels[status]}
    </span>
  )
}

function FormatBadge({ format }: { format: string }) {
  const colorMap: Record<string, string> = {
    playwright: 'bg-violet-100 text-violet-700',
    selenium: 'bg-blue-100 text-blue-700',
    pytest: 'bg-sky-100 text-sky-700',
    robot: 'bg-indigo-100 text-indigo-700',
    gherkin: 'bg-emerald-100 text-emerald-700',
  }
  const cls = colorMap[format.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {format}
    </span>
  )
}

// ── Reject Modal ───────────────────────────────────────────────────────────

interface RejectModalProps {
  open: boolean
  loading: boolean
  error: string | null
  onConfirm: (comment: string) => void
  onClose: () => void
}

function RejectModal({ open, loading, error, onConfirm, onClose }: RejectModalProps) {
  const [comment, setComment] = useState('')

  const handleSubmit = () => {
    if (comment.trim()) onConfirm(comment)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900">Reject Script</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <div className="mb-5">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Rejection Comment <span className="text-red-500">*</span>
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
            placeholder="Explain why this script is being rejected…"
          />
        </div>
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !comment.trim()}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            <XCircle size={14} />
            {loading ? 'Rejecting…' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Regenerate Modal ───────────────────────────────────────────────────────

interface RegenerateModalProps {
  open: boolean
  requirementId: string
  onClose: () => void
}

function RegenerateModal({ open, requirementId, onClose }: RegenerateModalProps) {
  const [instructions, setInstructions] = useState('')
  const [format, setFormat] = useState<ExportFormat>('playwright')
  const [agentRunId, setAgentRunId] = useState<string | null>(null)
  const [genError, setGenError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      apiClient
        .post<{ agent_run_id: string }>(`/requirements/${requirementId}/generate-script`, {
          export_format: format,
          ...(instructions.trim() ? { instructions: instructions.trim() } : {}),
        })
        .then((r) => r.data),
    onSuccess: (data) => setAgentRunId(data.agent_run_id),
    onError: (err) => setGenError(errorMessage(err)),
  })

  const handleClose = () => {
    setAgentRunId(null)
    setGenError(null)
    setInstructions('')
    mutation.reset()
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900">Regenerate Script</h3>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {agentRunId ? (
          <div className="space-y-4">
            <LiveAgentRunCard runId={agentRunId} />
            <div className="flex justify-end">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <>
            {genError && (
              <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {genError}
              </div>
            )}
            <div className="space-y-4 mb-5">
              <div>
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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Modification Instructions <span className="text-gray-400">(optional)</span>
                </label>
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="e.g. Add assertions for error handling, use data-testid selectors…"
                />
              </div>
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
                <RotateCcw size={14} />
                {mutation.isPending ? 'Dispatching…' : 'Regenerate'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function TestScriptDetailPage() {
  const { scriptId = '' } = useParams<{ scriptId: string }>()
  const queryClient = useQueryClient()

  const canUpdate = usePermission('script:update')

  const [editorContent, setEditorContent] = useState('')
  const [contentDirty, setContentDirty] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState<string>('')
  const [compareContent, setCompareContent] = useState<string | null>(null)
  const [exportFormat, setExportFormat] = useState<ExportFormat>('playwright')
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [regenerateModalOpen, setRegenerateModalOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

  // ── Fetch script ──────────────────────────────────────────────────────────

  const { data: script, isLoading, error } = useQuery<TestScript>({
    queryKey: ['test-script', scriptId],
    queryFn: () =>
      apiClient.get<TestScript>(`/test-scripts/${scriptId}`).then((r) => r.data),
    enabled: !!scriptId,
  })

  // Initialise editor content when script first loads
  useEffect(() => {
    if (script && !contentDirty) {
      setEditorContent(script.rendered_content ?? '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [script?.id])

  // ── Fetch versions ────────────────────────────────────────────────────────

  const { data: versions } = useQuery<TestScriptVersion[]>({
    queryKey: ['test-script-versions', scriptId],
    queryFn: () =>
      apiClient
        .get<TestScriptVersion[]>(`/test-scripts/${scriptId}/versions`)
        .then((r) => r.data),
    enabled: !!scriptId,
  })

  // Update export format default to match script's format
  useEffect(() => {
    if (script && EXPORT_FORMATS.includes(script.format as ExportFormat)) {
      setExportFormat(script.format as ExportFormat)
    }
  }, [script])

  // ── Workflow mutations ────────────────────────────────────────────────────

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['test-script', scriptId] })

  const saveMutation = useMutation({
    mutationFn: () =>
      apiClient.patch(`/test-scripts/${scriptId}`, { rendered_content: editorContent }),
    onSuccess: () => { setContentDirty(false); invalidate() },
    onError: (err) => setActionError(errorMessage(err)),
  })

  const submitMutation = useMutation({
    mutationFn: () => apiClient.post(`/test-scripts/${scriptId}/submit-for-review`),
    onSuccess: () => { setActionError(null); invalidate() },
    onError: (err) => setActionError(errorMessage(err)),
  })

  const approveMutation = useMutation({
    mutationFn: () => apiClient.post(`/test-scripts/${scriptId}/approve`),
    onSuccess: () => { setActionError(null); invalidate() },
    onError: (err) => setActionError(errorMessage(err)),
  })

  const rejectMutation = useMutation({
    mutationFn: (comment: string) =>
      apiClient.post(`/test-scripts/${scriptId}/reject`, { rejection_comment: comment }),
    onSuccess: () => { setActionError(null); setRejectModalOpen(false); invalidate() },
    onError: (err) => setActionError(errorMessage(err)),
  })

  // ── Version handling ──────────────────────────────────────────────────────

  const handleVersionSelect = (versionId: string) => {
    setSelectedVersionId(versionId)
    const v = versions?.find((ver) => ver.id === versionId)
    setCompareContent(v?.rendered_content ?? null)
  }

  const handleLoadVersion = () => {
    if (compareContent !== null) {
      setEditorContent(compareContent)
      setContentDirty(true)
      setCompareContent(null)
      setSelectedVersionId('')
    }
  }

  // ── Loading / error states ────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="p-6 animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/2" />
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 h-96 bg-gray-100 rounded-xl" />
          <div className="space-y-3">
            <div className="h-32 bg-gray-100 rounded-xl" />
            <div className="h-24 bg-gray-100 rounded-xl" />
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

  if (!script) return null

  return (
    <div className="p-6 space-y-5">
      {/* Top bar */}
      <div className="flex items-start gap-4">
        <Link
          to={`/systems/${script.system_id}/scripts`}
          className="mt-1 text-gray-400 hover:text-gray-600 shrink-0"
        >
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <FormatBadge format={script.format} />
            <StatusBadge status={script.status} />
            <span className="text-xs text-gray-400 font-mono">v{script.version_number}</span>
            {script.ai_generated && (
              <span className="inline-flex items-center gap-1 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-full px-2 py-0.5">
                <Zap size={11} />
                AI-generated
              </span>
            )}
            {script.requirement_id && (
              <Link
                to={`/requirements/${script.requirement_id}`}
                className="inline-flex items-center text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded-full px-2 py-0.5 hover:bg-blue-100"
              >
                Requirement ↗
              </Link>
            )}
          </div>
          <h1 className="text-xl font-bold text-gray-900 truncate">{script.title}</h1>
          {script.description && (
            <p className="text-sm text-gray-500 mt-0.5 truncate">{script.description}</p>
          )}
        </div>
      </div>

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)}><X size={14} /></button>
        </div>
      )}

      {/* Rejection comment notice */}
      {script.rejection_comment && (
        <div className="flex items-start gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
          <AlertTriangle size={16} className="text-red-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-800">Rejection Reason</p>
            <p className="text-sm text-red-700 mt-0.5">{script.rejection_comment}</p>
          </div>
        </div>
      )}

      {/* Two-panel layout */}
      <div className="grid grid-cols-3 gap-6 items-start">
        {/* Left — editor */}
        <div className="col-span-2 space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-700">Script Content</h2>
              {canUpdate && contentDirty && (
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saveMutation.isPending ? 'Saving…' : 'Save Changes'}
                </button>
              )}
            </div>
            <ScriptEditor
              value={editorContent}
              format={script.format}
              readOnly={!canUpdate}
              onChange={(v) => { setEditorContent(v); setContentDirty(true) }}
              height="480px"
            />
          </div>

          {/* Version history */}
          {versions && versions.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <Clock size={14} />
                  Version History
                </h2>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <select
                      value={selectedVersionId}
                      onChange={(e) => handleVersionSelect(e.target.value)}
                      className="appearance-none pl-3 pr-8 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    >
                      <option value="">Select version to compare…</option>
                      {versions.map((v) => (
                        <option key={v.id} value={v.id}>
                          v{v.version_number} — {new Date(v.created_at).toLocaleDateString()}
                          {v.change_summary ? ` · ${v.change_summary.slice(0, 40)}` : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  </div>
                  {compareContent !== null && canUpdate && (
                    <button
                      onClick={handleLoadVersion}
                      className="px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100"
                    >
                      Load this version
                    </button>
                  )}
                </div>
              </div>

              {compareContent !== null && (
                <div>
                  <p className="text-xs text-gray-500 mb-2">Read-only preview:</p>
                  <ScriptEditor
                    value={compareContent}
                    format={script.format}
                    readOnly
                    height="280px"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Status workflow */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Workflow</h2>
              <StatusBadge status={script.status} />
            </div>

            {script.status === 'draft' && (
              <RoleGate permission="script:update">
                <button
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  <Send size={14} />
                  {submitMutation.isPending ? 'Submitting…' : 'Submit for Review'}
                </button>
              </RoleGate>
            )}

            {script.status === 'in_review' && (
              <div className="space-y-2">
                <RoleGate permission="script:approve">
                  <button
                    onClick={() => approveMutation.mutate()}
                    disabled={approveMutation.isPending}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    <CheckCircle size={14} />
                    {approveMutation.isPending ? 'Approving…' : 'Approve'}
                  </button>
                </RoleGate>
                <RoleGate permission="script:approve">
                  <button
                    onClick={() => setRejectModalOpen(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-red-700 border border-red-200 rounded-lg hover:bg-red-50"
                  >
                    <XCircle size={14} />
                    Reject
                  </button>
                </RoleGate>
              </div>
            )}

            {script.status === 'approved' && script.approved_at && (
              <p className="text-xs text-gray-500">
                Approved on {new Date(script.approved_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Export */}
          <RoleGate permission="script:export">
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-gray-700">Export</h2>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Format</label>
                <div className="relative">
                  <select
                    value={exportFormat}
                    onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                    className="w-full appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    {EXPORT_FORMATS.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                </div>
              </div>
              <a
                href={`${BASE_URL}/test-scripts/${scriptId}/export?format=${exportFormat}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                <Download size={14} />
                Download
              </a>
            </div>
          </RoleGate>

          {/* Regenerate */}
          {script.requirement_id && (
            <RoleGate permission="agent:generate">
              <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
                <h2 className="text-sm font-semibold text-gray-700">Regenerate</h2>
                <p className="text-xs text-gray-500">
                  Dispatch a new AI generation run for this script's requirement.
                </p>
                <button
                  onClick={() => setRegenerateModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-50"
                >
                  <RotateCcw size={14} />
                  Regenerate Script
                </button>
              </div>
            </RoleGate>
          )}

          {/* Meta */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2 text-xs text-gray-500">
            <div className="flex justify-between">
              <span>Created</span>
              <span>{new Date(script.created_at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Updated</span>
              <span>{new Date(script.updated_at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Domain</span>
              <span>{script.business_domain ?? '—'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Reject modal */}
      <RejectModal
        open={rejectModalOpen}
        loading={rejectMutation.isPending}
        error={rejectMutation.isError ? errorMessage(rejectMutation.error) : null}
        onConfirm={(comment) => rejectMutation.mutate(comment)}
        onClose={() => setRejectModalOpen(false)}
      />

      {/* Regenerate modal */}
      {script.requirement_id && (
        <RegenerateModal
          open={regenerateModalOpen}
          requirementId={script.requirement_id}
          onClose={() => setRegenerateModalOpen(false)}
        />
      )}
    </div>
  )
}
