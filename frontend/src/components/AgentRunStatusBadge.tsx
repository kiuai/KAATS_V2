import type { AgentRunStatus } from '@/types'

const CONFIG: Record<AgentRunStatus, { label: string; className: string }> = {
  pending:    { label: 'Pending',    className: 'bg-gray-100 text-gray-600' },
  running:    { label: 'Running',    className: 'bg-blue-100 text-blue-700 animate-pulse' },
  completed:  { label: 'Completed', className: 'bg-green-100 text-green-700' },
  failed:     { label: 'Failed',    className: 'bg-red-100 text-red-700' },
  timed_out:  { label: 'Timed Out', className: 'bg-orange-100 text-orange-700' },
  cancelled:  { label: 'Cancelled', className: 'bg-gray-100 text-gray-500' },
}

interface Props {
  status: AgentRunStatus
  size?: 'sm' | 'md'
}

export default function AgentRunStatusBadge({ status, size = 'md' }: Props) {
  const config = CONFIG[status] ?? CONFIG.pending
  const sizeClass = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2.5 py-1'
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${sizeClass} ${config.className}`}>
      {status === 'running' && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-blue-500 animate-ping inline-block" />
      )}
      {config.label}
    </span>
  )
}
