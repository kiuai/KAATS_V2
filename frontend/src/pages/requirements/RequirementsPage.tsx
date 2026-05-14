import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Upload,
  Plus,
  Zap,
  X,
  ChevronDown,
} from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type {
  RequirementWithScripts,
  RequirementPriority,
  RequirementStatus,
  Page,
} from '@/types'
import PaginatedTable from '@/components/PaginatedTable'
import RoleGate from '@/components/RoleGate'
import { usePermission } from '@/hooks/usePermission'

// ── Constants ──────────────────────────────────────────────────────────────

const EXPORT_FORMATS = ['playwright', 'selenium', 'pytest', 'robot', 'gherkin'] as const
type ExportFormat = (typeof EXPORT_FORMATS)[number]

const STATUS_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Statuses', value: '' },
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Deprecated', value: 'deprecated' },
]

const PRIORITY_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Priorities', value: '' },
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
  { label: 'Critical', value: 'critical' },
]

const SOURCE_TYPE_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Sources', value: '' },
  { label: 'Manual', value: 'manual' },
  { label: 'Import', value: 'import' },
  { label: 'Agent', value: 'agent' },
]

// ── Badge helpers ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: RequirementStatus }) {
  const styles: Record<RequirementStatus, string> = {
    draft: 'bg-gray-100 text-gray-700',
    active: 'bg-green-100 text-green-700',
    deprecated: 'bg-orange-100 text-orange-700',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  )
}

function PriorityBadge({ priority }: { priority: RequirementPriority }) {
  const styles: Record<RequirementPriority, string> = {
    low: 'bg-sky-100 text-sky-700',
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[priority]}`}>
      {priority}
    </span>
  )
}

// ── Add Requirement Drawer ─────────────────────────────────────────────────

interface AddRequirementDrawerProps {
  systemId: string
  open: boolean
  onClose: () => void
  onCreated: () => void
}

function AddRequirementDrawer({ systemId, open, onClose, onCreated }: AddRequirementDrawerProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<RequirementPriority>('medium')
  const [businessDomain, setBusinessDomain] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/systems/${systemId}/requirements`, {
        title,
        description,
        priority,
        business_domain: businessDomain || null,
        tags: tagsInput
          ? tagsInput
              .split(',')
              .map((t) => t.trim())
              .filter(Boolean)
          : null,
      }),
    onSuccess: () => {
      onCreated()
      onClose()
      setTitle('')
      setDescription('')
      setPriority('medium')
      setBusinessDomain('')
      setTagsInput('')
      setFormError(null)
    },
    onError: (err) => setFormError(errorMessage(err)),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) { setFormError('Title is required'); return }
    if (!description.trim()) { setFormError('Description is required'); return }
    setFormError(null)
    mutation.mutate()
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />
      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Add Requirement</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {formError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {formError}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Requirement title"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Describe the requirement in detail…"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as RequirementPriority)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Business Domain</label>
            <input
              type="text"
              value={businessDomain}
              onChange={(e) => setBusinessDomain(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g. Finance, HR, Operations"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tags</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Comma-separated: login, auth, sso"
            />
          </div>
        </form>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={mutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Creating…' : 'Create Requirement'}
          </button>
        </div>
      </div>
    </>
  )
}

// ── Generate Scripts Modal ─────────────────────────────────────────────────

interface GenerateScriptsModalProps {
  open: boolean
  selectedIds: string[]
  onClose: () => void
}

function GenerateScriptsModal({ open, selectedIds, onClose }: GenerateScriptsModalProps) {
  const [format, setFormat] = useState<ExportFormat>('playwright')
  const [results, setResults] = useState<{ id: string; agentRunId?: string; error?: string }[]>([])
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)

  const handleGenerate = async () => {
    setRunning(true)
    const generated: { id: string; agentRunId?: string; error?: string }[] = []
    for (const id of selectedIds) {
      try {
        const resp = await apiClient.post(`/requirements/${id}/generate-script`, {
          export_format: format,
        })
        generated.push({ id, agentRunId: (resp.data as { agent_run_id: string }).agent_run_id })
      } catch (err) {
        generated.push({ id, error: errorMessage(err) })
      }
    }
    setResults(generated)
    setRunning(false)
    setDone(true)
  }

  const handleClose = () => {
    setResults([])
    setDone(false)
    setRunning(false)
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900">Generate Test Scripts</h3>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {!done ? (
          <>
            <p className="text-sm text-gray-600 mb-4">
              Generating scripts for <span className="font-medium">{selectedIds.length}</span> requirement
              {selectedIds.length !== 1 ? 's' : ''}.
            </p>
            <div className="mb-5">
              <label className="block text-sm font-medium text-gray-700 mb-1">Export Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {EXPORT_FORMATS.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={running}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Zap size={14} />
                {running ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="space-y-2 mb-5 max-h-64 overflow-y-auto">
              {results.map((r) => (
                <div
                  key={r.id}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm ${
                    r.error ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'
                  }`}
                >
                  <span className="font-mono text-xs truncate">{r.id.slice(0, 12)}…</span>
                  {r.agentRunId ? (
                    <Link
                      to={`/agents/${r.agentRunId}`}
                      className="ml-2 underline shrink-0"
                      onClick={handleClose}
                    >
                      View Run
                    </Link>
                  ) : (
                    <span className="ml-2 shrink-0">{r.error}</span>
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-end">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function RequirementsPage() {
  const { systemId = '' } = useParams<{ systemId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const canCreate = usePermission('req:create')

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [businessDomain, setBusinessDomain] = useState('')
  const [sourceType, setSourceType] = useState('')

  // Pagination
  const [offset, setOffset] = useState(0)
  const LIMIT = 50

  // Selection
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

  // Modals
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [generateModalOpen, setGenerateModalOpen] = useState(false)

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  // Reset offset on filter changes
  const handleFilterChange = useCallback((setter: (v: string) => void) => (v: string) => {
    setter(v)
    setOffset(0)
  }, [])

  const queryKey = ['requirements', systemId, debouncedSearch, status, priority, businessDomain, sourceType, offset]

  const { data, isLoading, error } = useQuery<Page<RequirementWithScripts>>({
    queryKey,
    queryFn: () => {
      const params = new URLSearchParams()
      if (debouncedSearch) params.set('search', debouncedSearch)
      if (status) params.set('status', status)
      if (priority) params.set('priority', priority)
      if (businessDomain) params.set('business_domain', businessDomain)
      if (sourceType) params.set('source_type', sourceType)
      params.set('limit', String(LIMIT))
      params.set('offset', String(offset))
      return apiClient
        .get<Page<RequirementWithScripts>>(`/systems/${systemId}/requirements?${params}`)
        .then((r) => r.data)
    },
    enabled: !!systemId,
  })

  const columns = [
    {
      key: 'title',
      header: 'Title',
      render: (row: RequirementWithScripts) => (
        <Link
          to={`/requirements/${row.id}`}
          className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
        >
          {row.title}
        </Link>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: RequirementWithScripts) => <StatusBadge status={row.status} />,
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (row: RequirementWithScripts) => <PriorityBadge priority={row.priority} />,
    },
    {
      key: 'domain',
      header: 'Domain',
      render: (row: RequirementWithScripts) => (
        <span className="text-gray-500 text-sm">{row.business_domain ?? '—'}</span>
      ),
    },
    {
      key: 'scripts',
      header: 'Scripts',
      render: (row: RequirementWithScripts) => (
        <span className="text-gray-700 text-sm">
          {row.approved_script_count}/{row.script_count}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: RequirementWithScripts) => (
        <span className="text-gray-500 text-sm">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
  ]

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Requirements</h1>
          {data && (
            <p className="text-sm text-gray-500 mt-0.5">{data.total} total</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RoleGate permission="req:import">
            <button
              onClick={() => navigate(`/systems/${systemId}/requirements/import`)}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <Upload size={15} />
              Import
            </button>
          </RoleGate>
          {canCreate && (
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              <Plus size={15} />
              Add Requirement
            </button>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search requirements…"
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="relative">
          <select
            value={status}
            onChange={(e) => handleFilterChange(setStatus)(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select
            value={priority}
            onChange={(e) => handleFilterChange(setPriority)(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {PRIORITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select
            value={sourceType}
            onChange={(e) => handleFilterChange(setSourceType)(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {SOURCE_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>
        <input
          type="text"
          value={businessDomain}
          onChange={(e) => handleFilterChange(setBusinessDomain)(e.target.value)}
          placeholder="Domain filter…"
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Bulk action bar */}
      {selectedKeys.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-700">
            {selectedKeys.size} selected
          </span>
          <RoleGate permission="agent:generate">
            <button
              onClick={() => setGenerateModalOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              <Zap size={13} />
              Generate Scripts
            </button>
          </RoleGate>
          <button
            onClick={() => setSelectedKeys(new Set())}
            className="ml-auto text-sm text-blue-600 hover:underline"
          >
            Clear
          </button>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Table */}
      <PaginatedTable<RequirementWithScripts>
        columns={columns}
        rows={data?.items ?? []}
        getKey={(r) => r.id}
        total={data?.total ?? 0}
        offset={offset}
        limit={LIMIT}
        onOffsetChange={setOffset}
        isLoading={isLoading}
        emptyMessage="No requirements found. Add one or adjust your filters."
        selectedKeys={selectedKeys}
        onSelectionChange={setSelectedKeys}
      />

      {/* Add drawer */}
      <AddRequirementDrawer
        systemId={systemId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['requirements', systemId] })}
      />

      {/* Generate modal */}
      <GenerateScriptsModal
        open={generateModalOpen}
        selectedIds={Array.from(selectedKeys)}
        onClose={() => {
          setGenerateModalOpen(false)
          setSelectedKeys(new Set())
        }}
      />
    </div>
  )
}
