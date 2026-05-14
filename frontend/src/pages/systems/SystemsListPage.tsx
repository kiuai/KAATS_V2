import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { usePermission } from '@/hooks/usePermission'
import RoleGate from '@/components/RoleGate'
import type { System } from '@/types'

// ── types ─────────────────────────────────────────────────────────────────

type SystemType = 'web' | 'sap_fiori' | 'api' | 'other'

interface NewSystemForm {
  name: string
  description: string
  base_url: string
  system_type: SystemType
}

interface SystemFilters {
  search: string
  system_type: SystemType | ''
  is_active: '' | 'true' | 'false'
}

// ── helpers ───────────────────────────────────────────────────────────────

function typeBadgeClass(type: string): string {
  switch (type) {
    case 'web':       return 'bg-blue-100 text-blue-700'
    case 'sap_fiori': return 'bg-orange-100 text-orange-700'
    case 'api':       return 'bg-purple-100 text-purple-700'
    default:          return 'bg-gray-100 text-gray-600'
  }
}

// ── skeleton ──────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 animate-pulse">
      <div className="h-4 w-2/3 bg-gray-200 rounded mb-2" />
      <div className="h-3 w-1/3 bg-gray-100 rounded mb-4" />
      <div className="h-3 w-1/2 bg-gray-100 rounded mb-3" />
      <div className="flex gap-2 mt-4">
        <div className="h-7 w-16 bg-gray-100 rounded-lg" />
        <div className="h-7 w-20 bg-gray-100 rounded-lg" />
      </div>
    </div>
  )
}

// ── modal form ────────────────────────────────────────────────────────────

interface NewSystemModalProps {
  onClose: () => void
  onSuccess: () => void
}

function NewSystemModal({ onClose, onSuccess }: NewSystemModalProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState<NewSystemForm>({
    name: '',
    description: '',
    base_url: '',
    system_type: 'web',
  })
  const [serverError, setServerError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (body: NewSystemForm) =>
      apiClient.post<System>('/systems', body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['systems'] })
      onSuccess()
    },
    onError: (err) => {
      setServerError(errorMessage(err))
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setServerError(null)
    if (!form.name.trim()) return
    mutation.mutate(form)
  }

  function set<K extends keyof NewSystemForm>(key: K, value: NewSystemForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-system-title"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 id="new-system-title" className="text-lg font-semibold text-gray-900 mb-5">
          New System
        </h2>

        {serverError && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="My System"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Optional description"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Base URL
            </label>
            <input
              type="url"
              value={form.base_url}
              onChange={(e) => set('base_url', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              System Type
            </label>
            <select
              value={form.system_type}
              onChange={(e) => set('system_type', e.target.value as SystemType)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="web">Web</option>
              <option value="sap_fiori">SAP Fiori</option>
              <option value="api">API</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={mutation.isPending}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !form.name.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {mutation.isPending ? 'Creating…' : 'Create System'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function SystemsListPage() {
  const canUpdate = usePermission('system:update')
  const [showModal, setShowModal] = useState(false)
  const [filters, setFilters] = useState<SystemFilters>({
    search: '',
    system_type: '',
    is_active: '',
  })

  function setFilter<K extends keyof SystemFilters>(key: K, value: SystemFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const { data: systems = [], isLoading, error } = useQuery<System[]>({
    queryKey: ['systems'],
    queryFn: () => apiClient.get<System[]>('/systems').then((r) => r.data),
  })

  // Client-side filtering
  const filtered = systems.filter((s) => {
    if (
      filters.search &&
      !s.name.toLowerCase().includes(filters.search.toLowerCase()) &&
      !(s.base_url ?? '').toLowerCase().includes(filters.search.toLowerCase())
    ) {
      return false
    }
    if (filters.system_type && s.system_type !== filters.system_type) return false
    if (filters.is_active === 'true' && !s.is_active) return false
    if (filters.is_active === 'false' && s.is_active) return false
    return true
  })

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Systems</h1>
        <RoleGate permission="system:create">
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl transition-colors"
          >
            <Plus size={16} />
            New System
          </button>
        </RoleGate>
      </div>

      {/* ── Filters ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="search"
          placeholder="Search systems…"
          value={filters.search}
          onChange={(e) => setFilter('search', e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
        />

        <select
          value={filters.system_type}
          onChange={(e) => setFilter('system_type', e.target.value as SystemType | '')}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">All types</option>
          <option value="web">Web</option>
          <option value="sap_fiori">SAP Fiori</option>
          <option value="api">API</option>
          <option value="other">Other</option>
        </select>

        <select
          value={filters.is_active}
          onChange={(e) => setFilter('is_active', e.target.value as '' | 'true' | 'false')}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">All statuses</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
      </div>

      {/* ── Error ───────────────────────────────────────────────── */}
      {error && (
        <p className="text-sm text-red-600 mb-4">{errorMessage(error)}</p>
      )}

      {/* ── Grid ────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 p-12 text-center">
          <p className="text-sm text-gray-500 mb-3">
            {systems.length === 0
              ? 'No systems configured yet.'
              : 'No systems match your filters.'}
          </p>
          <RoleGate permission="system:create">
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors"
            >
              <Plus size={14} />
              Add System
            </button>
          </RoleGate>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((system) => (
            <div
              key={system.id}
              className="bg-white border border-gray-200 rounded-2xl p-5 hover:shadow-md transition-shadow flex flex-col"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-gray-900 truncate pr-2">
                  {system.name}
                </h3>
                <span
                  className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${typeBadgeClass(system.system_type)}`}
                >
                  {system.system_type}
                </span>
              </div>

              <div className="flex items-center gap-1.5 mb-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    system.is_active ? 'bg-green-500' : 'bg-gray-300'
                  }`}
                />
                <span className="text-xs text-gray-500">
                  {system.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              {system.base_url && (
                <p className="text-xs text-gray-400 truncate mb-3">
                  {system.base_url}
                </p>
              )}

              <div className="flex gap-2 mt-auto pt-3">
                <Link
                  to={`/systems/${system.id}`}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  View
                </Link>
                {canUpdate && (
                  <Link
                    to={`/systems/${system.id}/settings`}
                    className="px-3 py-1.5 bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium rounded-lg transition-colors"
                  >
                    Settings
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Modal ───────────────────────────────────────────────── */}
      {showModal && (
        <NewSystemModal
          onClose={() => setShowModal(false)}
          onSuccess={() => setShowModal(false)}
        />
      )}
    </div>
  )
}
