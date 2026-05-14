import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronDown, ChevronUp, Clock, DollarSign, Cpu, AlertCircle, Info } from 'lucide-react'
import { useAgentRunPoller } from '@/hooks/useAgentRunPoller'
import AgentRunStatusBadge from '@/components/AgentRunStatusBadge'

// ── Helpers ───────────────────────────────────────────────────────────────────

const AGENT_TYPE_LABELS: Record<string, string> = {
  crawl:      'Crawl Agent',
  generation: 'Generation Agent',
  execution:  'Execution Agent',
}

function formatDuration(started: string | null, completed: string | null): string {
  if (!started) return '—'
  const end = completed ? new Date(completed) : new Date()
  const ms = end.getTime() - new Date(started).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${rem}s`
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1 py-3 border-b border-gray-100 last:border-0">
      <dt className="w-44 shrink-0 text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </dt>
      <dd className="text-sm text-gray-800">{children}</dd>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function RunDetailSkeleton() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6 animate-pulse">
      <div className="h-6 bg-gray-200 rounded w-48" />
      <div className="h-48 bg-gray-100 rounded-xl" />
      <div className="h-32 bg-gray-100 rounded-xl" />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AgentRunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [inputExpanded, setInputExpanded] = useState(false)

  const run = useAgentRunPoller(runId)

  if (!run) return <RunDetailSkeleton />

  const isTerminal = ['completed', 'failed', 'timed_out', 'cancelled'].includes(run.status)
  const isActive = run.status === 'running' || run.status === 'pending'

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Back nav */}
      <button
        onClick={() => navigate('/agents')}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-2"
      >
        <ChevronLeft size={16} />
        All Agent Runs
      </button>

      {/* Header */}
      <div className="flex flex-wrap items-start gap-4 justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-gray-900">
              {AGENT_TYPE_LABELS[run.agent_type] ?? run.agent_type}
            </h1>
            <AgentRunStatusBadge status={run.status} />
            {isActive && (
              <span className="flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500" />
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 font-mono">{run.id}</p>
        </div>
      </div>

      {/* Metadata card */}
      <div className="bg-white border border-gray-200 rounded-xl px-6 py-2">
        <dl>
          <MetaRow label="Type">
            <span className="inline-flex items-center gap-1.5">
              <Cpu size={14} className="text-gray-400" />
              {AGENT_TYPE_LABELS[run.agent_type] ?? run.agent_type}
            </span>
          </MetaRow>
          <MetaRow label="Status">
            <AgentRunStatusBadge status={run.status} />
          </MetaRow>
          <MetaRow label="System ID">
            {run.system_id ? (
              <span className="font-mono text-xs">{run.system_id}</span>
            ) : (
              '—'
            )}
          </MetaRow>
          <MetaRow label="Trigger">
            <span className="capitalize">{run.trigger_type}</span>
          </MetaRow>
          <MetaRow label="Triggered by">
            {run.triggered_by_user_id ? (
              <span className="font-mono text-xs">{run.triggered_by_user_id}</span>
            ) : (
              'System'
            )}
          </MetaRow>
          <MetaRow label="Started">
            {run.started_at
              ? new Date(run.started_at).toLocaleString()
              : '—'}
          </MetaRow>
          <MetaRow label="Completed">
            {run.completed_at
              ? new Date(run.completed_at).toLocaleString()
              : isActive
              ? 'In progress…'
              : '—'}
          </MetaRow>
          <MetaRow label="Duration">
            <span className="inline-flex items-center gap-1">
              <Clock size={13} className="text-gray-400" />
              {formatDuration(run.started_at, run.completed_at)}
            </span>
          </MetaRow>
          <MetaRow label="Tokens">
            {run.prompt_tokens || run.completion_tokens ? (
              <span>
                {run.prompt_tokens.toLocaleString()} prompt
                {' + '}
                {run.completion_tokens.toLocaleString()} completion
              </span>
            ) : (
              '—'
            )}
          </MetaRow>
          <MetaRow label="Cost">
            <span className="inline-flex items-center gap-1">
              <DollarSign size={13} className="text-gray-400" />
              {run.total_cost_usd !== null
                ? `$${run.total_cost_usd.toFixed(4)}`
                : '—'}
            </span>
          </MetaRow>
        </dl>
      </div>

      {/* Error message */}
      {run.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 flex items-start gap-3">
          <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-700 mb-1">Error</p>
            <p className="text-sm text-red-600 whitespace-pre-wrap">{run.error_message}</p>
          </div>
        </div>
      )}

      {/* Output summary */}
      {isTerminal && run.output_summary && (
        <div className="space-y-2">
          <h2 className="text-base font-semibold text-gray-800">Output Summary</h2>
          <pre className="bg-gray-900 text-green-300 rounded-xl p-5 text-xs overflow-x-auto leading-relaxed font-mono whitespace-pre-wrap">
            {JSON.stringify(run.output_summary, null, 2)}
          </pre>
        </div>
      )}

      {/* Input config */}
      {run.input_config && (
        <div className="space-y-2">
          <button
            onClick={() => setInputExpanded((p) => !p)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900"
          >
            {inputExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            Input Configuration
          </button>
          {inputExpanded && (
            <pre className="bg-gray-50 border border-gray-200 text-gray-700 rounded-xl p-5 text-xs overflow-x-auto leading-relaxed font-mono whitespace-pre-wrap">
              {JSON.stringify(run.input_config, null, 2)}
            </pre>
          )}
        </div>
      )}

      {/* Tool call timeline placeholder */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4 flex items-start gap-3">
        <Info size={16} className="text-blue-500 shrink-0 mt-0.5" />
        <p className="text-sm text-blue-700">
          Tool call timeline is available in the Cosmos audit log — not exposed via REST API.
        </p>
      </div>
    </div>
  )
}
