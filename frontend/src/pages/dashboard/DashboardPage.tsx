import { useQuery } from '@tanstack/react-query'
import apiClient from '@/services/api'

export default function DashboardPage() {
  const { data: systems } = useQuery({
    queryKey: ['systems'],
    queryFn: () => apiClient.get('/systems').then((r) => r.data),
  })

  const { data: agentRuns } = useQuery({
    queryKey: ['agent_runs', 'recent'],
    queryFn: () => apiClient.get('/agent_runs?page=1&page_size=5').then((r) => r.data),
  })

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>
      <div className="grid grid-cols-3 gap-6 mb-8">
        <StatCard label="Systems" value={systems?.length ?? '—'} />
        <StatCard label="Active Runs" value="—" />
        <StatCard label="Scheduled Jobs" value="—" />
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Recent Agent Runs</h2>
        <p className="text-sm text-gray-500">No recent runs.</p>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  )
}
