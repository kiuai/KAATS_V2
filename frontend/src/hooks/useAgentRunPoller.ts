import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/services/api'
import type { AgentRun } from '@/types'

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'timed_out', 'cancelled'])

export function useAgentRunPoller(
  runId: string | null | undefined,
  onComplete?: (run: AgentRun) => void,
): AgentRun | undefined {
  const qc = useQueryClient()
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  const { data: run } = useQuery<AgentRun>({
    queryKey: ['agent-runs', runId],
    queryFn: () => apiClient.get(`/agent_runs/${runId}`).then((r) => r.data),
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data as AgentRun | undefined
      if (!data) return 5_000
      return TERMINAL_STATUSES.has(data.status) ? false : 5_000
    },
  })

  useEffect(() => {
    if (run && TERMINAL_STATUSES.has(run.status)) {
      onCompleteRef.current?.(run)
      // Stop polling by invalidating so next render won't refetch
      qc.cancelQueries({ queryKey: ['agent-runs', runId] })
    }
  }, [run, runId, qc])

  return run
}
