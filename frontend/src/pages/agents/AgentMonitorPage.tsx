import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { Bot, CheckCircle, XCircle, Clock } from 'lucide-react'
import apiClient from '@/services/api'
import type { AgentRun } from '@/types'

const STATUS_ICON = {
  running: <Clock size={16} className="text-yellow-500 animate-spin" />,
  completed: <CheckCircle size={16} className="text-green-500" />,
  failed: <XCircle size={16} className="text-red-500" />,
  timed_out: <XCircle size={16} className="text-orange-500" />,
}

export default function AgentMonitorPage() {
  const { runId } = useParams<{ runId?: string }>()
  const [steps, setSteps] = useState<object[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  const { data: runs = [] } = useQuery<AgentRun[]>({
    queryKey: ['agent_runs'],
    queryFn: () => apiClient.get('/agent_runs').then((r) => r.data),
    refetchInterval: 10_000,
  })

  const { data: selectedRun } = useQuery<AgentRun>({
    queryKey: ['agent_run', runId],
    queryFn: () => apiClient.get(`/agent_runs/${runId}`).then((r) => r.data),
    enabled: !!runId,
    refetchInterval: 5_000,
  })

  useEffect(() => {
    if (!runId || selectedRun?.status !== 'running') return
    const token = localStorage.getItem('kaats_access_token')
    const es = new EventSource(`/api/v1/agent_runs/${runId}/stream?token=${token}`)
    es.addEventListener('step', (e) => {
      setSteps((prev) => [...prev, JSON.parse(e.data)])
    })
    es.addEventListener('complete', () => es.close())
    eventSourceRef.current = es
    return () => es.close()
  }, [runId, selectedRun?.status])

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <Bot size={24} />
        Agent Runs
      </h1>
      <div className="flex gap-6">
        <div className="w-80 space-y-2">
          {runs.map((run) => (
            <div
              key={run.id}
              className={`p-4 bg-white border rounded-xl cursor-pointer ${runId === run.id ? 'border-blue-500' : 'border-gray-200'}`}
            >
              <div className="flex items-center gap-2">
                {STATUS_ICON[run.status] ?? null}
                <span className="text-sm font-medium capitalize">{run.agent_type}</span>
              </div>
              <p className="text-xs text-gray-400 mt-1 truncate">{run.id}</p>
            </div>
          ))}
        </div>
        {selectedRun && (
          <div className="flex-1 bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              {STATUS_ICON[selectedRun.status]}
              <h2 className="font-semibold capitalize">{selectedRun.agent_type} Agent</h2>
            </div>
            <div className="space-y-2 max-h-[60vh] overflow-y-auto font-mono text-xs">
              {steps.map((step: any, i) => (
                <div key={i} className="p-2 bg-gray-50 rounded border border-gray-100">
                  <span className="text-blue-600">Step {step.step_index}</span>
                  {step.thought && <p className="text-gray-700 mt-1">{step.thought}</p>}
                  {step.tool && <p className="text-green-700">→ {step.tool}</p>}
                  {step.observation && <p className="text-gray-500">{step.observation}</p>}
                </div>
              ))}
              {steps.length === 0 && (
                <p className="text-gray-400">Waiting for agent steps...</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
