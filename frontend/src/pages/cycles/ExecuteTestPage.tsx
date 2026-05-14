import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { CheckCircle, XCircle, AlertTriangle, MinusCircle, ChevronLeft } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { TestAssignment, TestScript, TestOutcome } from '@/types'
import ScriptEditor from '@/components/ScriptEditor'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SubmitResultBody {
  outcome: TestOutcome
  actual_result: string
  defect_reference: string
  notes: string
}

// ── Outcome options ───────────────────────────────────────────────────────────

interface OutcomeOption {
  value: TestOutcome
  label: string
  icon: React.ReactNode
  borderClass: string
  activeClass: string
  textClass: string
}

const OUTCOME_OPTIONS: OutcomeOption[] = [
  {
    value: 'passed',
    label: 'Passed',
    icon: <CheckCircle size={18} />,
    borderClass: 'border-green-200 hover:border-green-400',
    activeClass: 'border-green-500 bg-green-50',
    textClass: 'text-green-700',
  },
  {
    value: 'failed',
    label: 'Failed',
    icon: <XCircle size={18} />,
    borderClass: 'border-red-200 hover:border-red-400',
    activeClass: 'border-red-500 bg-red-50',
    textClass: 'text-red-700',
  },
  {
    value: 'blocked',
    label: 'Blocked',
    icon: <AlertTriangle size={18} />,
    borderClass: 'border-orange-200 hover:border-orange-400',
    activeClass: 'border-orange-500 bg-orange-50',
    textClass: 'text-orange-700',
  },
  {
    value: 'skipped',
    label: 'Skipped',
    icon: <MinusCircle size={18} />,
    borderClass: 'border-gray-200 hover:border-gray-400',
    activeClass: 'border-gray-400 bg-gray-50',
    textClass: 'text-gray-600',
  },
]

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ExecuteSkeleton() {
  return (
    <div className="flex h-full animate-pulse gap-0">
      <div className="flex-1 bg-gray-100 rounded-xl m-4" />
      <div className="w-96 shrink-0 m-4 space-y-4">
        <div className="h-6 bg-gray-200 rounded w-40" />
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 bg-gray-200 rounded-xl" />
          ))}
        </div>
        <div className="h-24 bg-gray-100 rounded-xl" />
        <div className="h-10 bg-gray-100 rounded-xl" />
        <div className="h-20 bg-gray-100 rounded-xl" />
        <div className="h-10 bg-blue-100 rounded-xl" />
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ExecuteTestPage() {
  const { cycleId, assignmentId } = useParams<{
    cycleId: string
    assignmentId: string
  }>()
  const navigate = useNavigate()

  const [outcome, setOutcome] = useState<TestOutcome | null>(null)
  const [actualResult, setActualResult] = useState('')
  const [defectReference, setDefectReference] = useState('')
  const [notes, setNotes] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Fetch all assignments to find ours
  const { data: assignments, isLoading: loadingAssignments } = useQuery<TestAssignment[]>({
    queryKey: ['test-cycle-assignments', cycleId],
    queryFn: () =>
      apiClient.get(`/test-cycles/${cycleId}/assignments`).then((r) => r.data),
    enabled: !!cycleId,
  })

  const assignment = assignments?.find((a) => a.id === assignmentId)

  // Fetch the script once we have the assignment
  const { data: script, isLoading: loadingScript } = useQuery<TestScript>({
    queryKey: ['test-script', assignment?.test_script_id],
    queryFn: () =>
      apiClient
        .get(`/test-scripts/${assignment!.test_script_id}`)
        .then((r) => r.data),
    enabled: !!assignment?.test_script_id,
  })

  const submitMutation = useMutation({
    mutationFn: (body: SubmitResultBody) =>
      apiClient
        .post(`/test-cycles/${cycleId}/assignments/${assignmentId}/result`, body)
        .then((r) => r.data),
    onSuccess: () => navigate(`/test-cycles/${cycleId}`),
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  const isLoading = loadingAssignments || loadingScript

  if (isLoading) return <ExecuteSkeleton />

  if (!assignment) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <p className="text-gray-500">Assignment not found.</p>
        <button
          onClick={() => navigate(`/test-cycles/${cycleId}`)}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Back to cycle
        </button>
      </div>
    )
  }

  const requiresDetails = outcome === 'failed' || outcome === 'blocked'

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    if (!outcome) return
    submitMutation.mutate({
      outcome,
      actual_result: actualResult,
      defect_reference: defectReference,
      notes,
    })
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate(`/test-cycles/${cycleId}`)}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800"
        >
          <ChevronLeft size={16} />
          Back to Cycle
        </button>
        <span className="text-gray-300">|</span>
        <h1 className="text-sm font-semibold text-gray-900 truncate">
          {script?.title ?? 'Test Execution'}
        </h1>
      </div>

      {/* Split layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: script viewer */}
        <div className="flex-1 overflow-auto p-4 min-w-0">
          <div className="h-full">
            {script ? (
              <ScriptEditor
                value={script.rendered_content ?? ''}
                format={script.format}
                readOnly
                height="100%"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                Script content unavailable.
              </div>
            )}
          </div>
        </div>

        {/* Right: result form */}
        <div className="w-96 shrink-0 overflow-y-auto bg-white border-l border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Submit Result</h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Outcome radios */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">
                Outcome <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {OUTCOME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setOutcome(opt.value)}
                    className={`flex items-center gap-2 px-3 py-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                      outcome === opt.value
                        ? `${opt.activeClass} ${opt.textClass}`
                        : `border-gray-200 text-gray-500 ${opt.borderClass}`
                    }`}
                  >
                    <span className={outcome === opt.value ? opt.textClass : 'text-gray-400'}>
                      {opt.icon}
                    </span>
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Actual result */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">
                Actual Result
                {requiresDetails && <span className="text-red-500 ml-1">*</span>}
              </label>
              <textarea
                value={actualResult}
                onChange={(e) => setActualResult(e.target.value)}
                required={requiresDetails}
                rows={4}
                placeholder={
                  requiresDetails
                    ? 'Describe what actually happened…'
                    : 'Optional: what actually happened…'
                }
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>

            {/* Defect reference */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Defect Reference</label>
              <input
                type="text"
                value={defectReference}
                onChange={(e) => setDefectReference(e.target.value)}
                placeholder="e.g. JIRA-1234 or bug tracker URL"
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Notes */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Any additional notes…"
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>

            {submitError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {submitError}
              </p>
            )}

            <button
              type="submit"
              disabled={!outcome || submitMutation.isPending}
              className="w-full py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {submitMutation.isPending ? 'Submitting…' : 'Submit Result'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
