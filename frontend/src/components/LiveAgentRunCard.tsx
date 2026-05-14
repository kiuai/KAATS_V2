import { Link } from 'react-router-dom'
import { Clock, Cpu } from 'lucide-react'
import { useAgentRunPoller } from '@/hooks/useAgentRunPoller'
import AgentRunStatusBadge from './AgentRunStatusBadge'
import type { AgentRun } from '@/types'

interface Props {
  runId: string
  onComplete?: (run: AgentRun) => void
}

const AGENT_LABELS: Record<string, string> = {
  crawl: 'Crawl Agent',
  generation: 'Generation Agent',
  execution: 'Execution Agent',
}

export default function LiveAgentRunCard({ runId, onComplete }: Props) {
  const run = useAgentRunPoller(runId, onComplete)

  if (!run) {
    return (
      <div className="animate-pulse bg-white border border-gray-200 rounded-xl p-4 h-20" />
    )
  }

  const started = run.started_at ? new Date(run.started_at) : null
  const elapsed = started
    ? Math.round((Date.now() - started.getTime()) / 1000)
    : null

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <Cpu size={18} className="text-blue-500 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">
            {AGENT_LABELS[run.agent_type] ?? run.agent_type}
          </p>
          <p className="text-xs text-gray-500 truncate">Run {run.id.slice(0, 8)}…</p>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {elapsed !== null && run.status === 'running' && (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <Clock size={12} />
            {elapsed}s
          </span>
        )}
        <AgentRunStatusBadge status={run.status} />
        <Link
          to={`/agents/${run.id}`}
          className="text-xs text-blue-600 hover:underline"
        >
          View
        </Link>
      </div>
    </div>
  )
}
