import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Calendar, Play, Pause, Trash2, Plus } from 'lucide-react'
import apiClient from '@/services/api'
import type { ScheduledJob } from '@/types'

export default function SchedulerPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)

  const { data: jobs = [], isLoading } = useQuery<ScheduledJob[]>({
    queryKey: ['scheduled_jobs'],
    queryFn: () => apiClient.get('/scheduled_jobs').then((r) => r.data),
  })

  const triggerMutation = useMutation({
    mutationFn: (jobId: string) =>
      apiClient.post(`/scheduled_jobs/${jobId}/trigger`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled_jobs'] }),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ jobId, enabled }: { jobId: string; enabled: boolean }) =>
      apiClient.put(`/scheduled_jobs/${jobId}`, { is_enabled: enabled }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled_jobs'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.delete(`/scheduled_jobs/${jobId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduled_jobs'] }),
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Calendar size={24} />
          Scheduled Jobs
        </h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
        >
          <Plus size={16} />
          New Job
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-5 py-3 font-medium text-gray-600">Agent</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Cron</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Timezone</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Next Run</th>
                <th className="text-left px-5 py-3 font-medium text-gray-600">Status</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="px-5 py-3 capitalize font-medium">{job.agent_type}</td>
                  <td className="px-5 py-3 font-mono text-xs">{job.cron_expression}</td>
                  <td className="px-5 py-3 text-gray-500">{job.timezone}</td>
                  <td className="px-5 py-3 text-gray-500">
                    {new Date(job.next_run_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${job.is_enabled ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {job.is_enabled ? 'enabled' : 'disabled'}
                    </span>
                    {job.consecutive_failures > 0 && (
                      <span className="ml-2 text-xs text-red-500">{job.consecutive_failures} failures</span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => triggerMutation.mutate(job.id)}
                        className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                        title="Run now"
                      >
                        <Play size={15} />
                      </button>
                      <button
                        onClick={() => toggleMutation.mutate({ jobId: job.id, enabled: !job.is_enabled })}
                        className="p-1 text-gray-500 hover:bg-gray-50 rounded"
                        title={job.is_enabled ? 'Disable' : 'Enable'}
                      >
                        <Pause size={15} />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        className="p-1 text-red-500 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-sm text-gray-400">
                    No scheduled jobs. Create one to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
