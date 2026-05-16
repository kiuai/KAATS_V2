import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, ExternalLink } from 'lucide-react'
import apiClient from '@/services/api'
import type { System } from '@/types'

export default function SystemsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  const { data: systems = [], isLoading } = useQuery<System[]>({
    queryKey: ['systems'],
    queryFn: () => apiClient.get('/systems').then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (body: { name: string; base_url: string }) =>
      apiClient.post('/systems', body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['systems'] })
      setShowForm(false)
      setName('')
      setBaseUrl('')
    },
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Systems</h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
        >
          <Plus size={16} />
          Add System
        </button>
      </div>

      {showForm && (
        <div className="mb-6 p-4 bg-white border border-gray-200 rounded-xl">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">New System</h2>
          <div className="flex gap-3">
            <input
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
              placeholder="System name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
              placeholder="Base URL (https://...)"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
            <button
              onClick={() => createMutation.mutate({ name, base_url: baseUrl })}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {systems.map((s) => (
            <div key={s.id} className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{s.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{s.system_type}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${s.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {s.is_active ? 'active' : 'inactive'}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-2 truncate">{s.base_url}</p>
              <div className="flex gap-3 mt-4">
                <Link to={`/systems/${s.id}`} className="text-xs text-blue-600 hover:underline">
                  Details
                </Link>
                <Link to={`/systems/${s.id}/requirements`} className="text-xs text-gray-600 hover:underline">
                  Requirements
                </Link>
                <Link to={`/systems/${s.id}/scripts`} className="text-xs text-gray-600 hover:underline">
                  Scripts
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
