import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Download, Camera } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import ScreenshotLightbox from '@/components/ScreenshotLightbox'
import type { ExecutionRun, StepResult } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  return `${mins}m ${secs % 60}s`
}

function durationFromDates(start: string | null, end: string | null): string {
  if (!start) return '—'
  const from = new Date(start).getTime()
  const to = end ? new Date(end).getTime() : Date.now()
  return formatDuration(to - from)
}

// ── status configs ────────────────────────────────────────────────────────

type RunStatus = ExecutionRun['status']
type StepStatus = StepResult['status']

const runStatusStyles: Record<RunStatus, string> = {
  passed: 'bg-green-100 text-green-700 border-green-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
  error: 'bg-red-100 text-red-700 border-red-200',
  pending: 'bg-gray-100 text-gray-600 border-gray-200',
  running: 'bg-yellow-100 text-yellow-700 border-yellow-200',
}

const stepCircleStyles: Record<StepStatus, string> = {
  passed: 'bg-green-500 text-white',
  failed: 'bg-red-500 text-white',
  error: 'bg-red-500 text-white',
  skipped: 'bg-gray-400 text-white',
}

const stepBadgeStyles: Record<StepStatus, string> = {
  passed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  error: 'bg-red-100 text-red-700',
  skipped: 'bg-gray-100 text-gray-600',
}

// ── skeleton ──────────────────────────────────────────────────────────────

function StepSkeleton() {
  return (
    <div className="flex gap-4 p-4 bg-white border border-gray-100 rounded-xl animate-pulse">
      <div className="w-8 h-8 rounded-full bg-gray-200 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-gray-200 rounded w-1/4" />
        <div className="h-3 bg-gray-100 rounded w-3/4" />
        <div className="h-3 bg-gray-100 rounded w-1/2" />
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function ExecutionRunDetailPage() {
  const { executionId } = useParams<{ executionId: string }>()
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  const {
    data: run,
    isLoading,
    error,
  } = useQuery<ExecutionRun>({
    queryKey: ['execution', executionId],
    queryFn: () =>
      apiClient.get<ExecutionRun>(`/executions/${executionId}`).then((r) => r.data),
    enabled: !!executionId,
  })

  // Placeholder lightbox images — one per step that would have a screenshot
  const lightboxImages = (run?.step_results ?? []).map((_, i) => ({
    src: '',
    alt: `Step ${i + 1} screenshot`,
  }))

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-lg mx-auto space-y-6">
        <div className="h-8 w-64 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-48 bg-gray-100 rounded animate-pulse" />
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <StepSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8 max-w-screen-lg mx-auto">
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      </div>
    )
  }

  if (!run) return null

  return (
    <div className="p-6 lg:p-8 max-w-screen-lg mx-auto space-y-8">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          {/* Large outcome badge */}
          <span
            className={`inline-flex items-center px-4 py-1.5 rounded-full text-sm font-semibold border ${runStatusStyles[run.status]}`}
          >
            {run.status.toUpperCase()}
          </span>

          <div className="space-y-1">
            <p className="text-sm text-gray-600">
              Script:{' '}
              <Link
                to={`/scripts/${run.script_id}`}
                className="font-mono text-blue-600 hover:underline"
              >
                {run.script_id}
              </Link>
            </p>
            <p className="text-sm text-gray-600">
              Started: <span className="text-gray-800">{formatDate(run.started_at)}</span>
            </p>
            <p className="text-sm text-gray-600">
              Duration:{' '}
              <span className="text-gray-800">
                {run.duration_ms !== null
                  ? formatDuration(run.duration_ms)
                  : durationFromDates(run.started_at, run.completed_at)}
              </span>
            </p>
            {run.triggered_by && (
              <p className="text-sm text-gray-600">
                Triggered by:{' '}
                <span className="text-gray-800">{run.triggered_by}</span>
              </p>
            )}
          </div>
        </div>

        {/* Download report */}
        <a
          href={`/api/v1/executions/${executionId}/report`}
          download
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors self-start"
        >
          <Download size={16} />
          Download Evidence Report
        </a>
      </div>

      {/* ── Step summary counts ───────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-green-50 border border-green-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-green-700">{run.passed_count}</p>
          <p className="text-xs text-green-600 mt-0.5 font-medium">Passed</p>
        </div>
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-red-700">{run.failed_count}</p>
          <p className="text-xs text-red-600 mt-0.5 font-medium">Failed</p>
        </div>
        <div className="bg-gray-50 border border-gray-100 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-gray-600">{run.skipped_count}</p>
          <p className="text-xs text-gray-500 mt-0.5 font-medium">Skipped</p>
        </div>
      </div>

      {/* ── Step results ────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-4">
          Step Results
        </h2>

        {run.step_results.length === 0 ? (
          <p className="text-sm text-gray-500">No step results recorded.</p>
        ) : (
          <div className="space-y-3">
            {run.step_results.map((step, index) => (
              <div
                key={step.id}
                className="flex gap-4 p-4 bg-white border border-gray-100 rounded-xl hover:border-gray-200 transition-colors"
              >
                {/* Step number circle */}
                <div
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${stepCircleStyles[step.status]}`}
                >
                  {index + 1}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${stepBadgeStyles[step.status]}`}
                    >
                      {step.status}
                    </span>
                    {step.duration_ms !== null && (
                      <span className="text-xs text-gray-400">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                    {step.executed_at && (
                      <span className="text-xs text-gray-400">
                        {formatDate(step.executed_at)}
                      </span>
                    )}
                  </div>

                  {step.actual_outcome && (
                    <p className="text-sm text-gray-700">{step.actual_outcome}</p>
                  )}

                  {step.failure_reason && (
                    <p className="text-sm text-red-600 italic">
                      {step.failure_reason}
                    </p>
                  )}
                </div>

                {/* Screenshot placeholder */}
                <button
                  className="shrink-0 w-16 h-12 bg-gray-100 border border-gray-200 rounded-lg flex items-center justify-center hover:bg-gray-200 transition-colors"
                  title="View screenshot"
                  onClick={() => setLightboxIndex(index)}
                >
                  <Camera size={16} className="text-gray-400" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Lightbox */}
      <ScreenshotLightbox
        images={lightboxImages}
        index={lightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />
    </div>
  )
}
