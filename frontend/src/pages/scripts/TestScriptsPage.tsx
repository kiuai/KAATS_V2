import { useState, useEffect, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Download, ChevronDown, Zap, X } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { TestScript, TestScriptStatus, Page } from '@/types'
import PaginatedTable from '@/components/PaginatedTable'
import RoleGate from '@/components/RoleGate'

// ── Constants ──────────────────────────────────────────────────────────────

const EXPORT_FORMATS = ['playwright', 'selenium', 'pytest', 'robot', 'gherkin'] as const
type ExportFormat = (typeof EXPORT_FORMATS)[number]

const STATUS_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Statuses', value: '' },
  { label: 'Draft', value: 'draft' },
  { label: 'In Review', value: 'in_review' },
  { label: 'Approved', value: 'approved' },
  { label: 'Deprecated', value: 'deprecated' },
]

const FORMAT_OPTIONS: { label: string; value: string }[] = [
  { label: 'All Formats', value: '' },
  ...EXPORT_FORMATS.map((f) => ({ label: f, value: f })),
]

// ── Badge helpers ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: TestScriptStatus }) {
  const styles: Record<TestScriptStatus, string> = {
    draft: 'bg-gray-100 text-gray-700',
    in_review: 'bg-yellow-100 text-yellow-700',
    approved: 'bg-green-100 text-green-700',
    deprecated: 'bg-red-100 text-red-700',
  }
  const labels: Record<TestScriptStatus, string> = {
    draft: 'Draft',
    in_review: 'In Review',
    approved: 'Approved',
    deprecated: 'Deprecated',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}

function FormatBadge({ format }: { format: string }) {
  const colorMap: Record<string, string> = {
    playwright: 'bg-violet-100 text-violet-700',
    selenium: 'bg-blue-100 text-blue-700',
    pytest: 'bg-sky-100 text-sky-700',
    robot: 'bg-indigo-100 text-indigo-700',
    gherkin: 'bg-emerald-100 text-emerald-700',
  }
  const cls = colorMap[format.toLowerCase()] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {format}
    </span>
  )
}

// ── Export Modal ───────────────────────────────────────────────────────────

interface ExportModalProps {
  open: boolean
  selectedIds: string[]
  onClose: () => void
}

function ExportModal({ open, selectedIds, onClose }: ExportModalProps) {
  const [format, setFormat] = useState<ExportFormat>('playwright')
  const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

  const handleExport = () => {
    for (const id of selectedIds) {
      window.open(`${BASE_URL}/test-scripts/${id}/export?format=${format}`, '_blank')
    }
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900">Export Test Scripts</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Exporting <span className="font-medium">{selectedIds.length}</span> script
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
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function TestScriptsPage() {
  const { systemId = '' } = useParams<{ systemId: string }>()
  const canExport = usePermission('script:export')

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [status, setStatus] = useState('')
  const [format, setFormat] = useState('')
  const [aiOnly, setAiOnly] = useState(false)

  // Pagination
  const [offset, setOffset] = useState(0)
  const LIMIT = 50

  // Selection
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

  const queryClient = useQueryClient()
  const bulkDelete = useMutation({
    mutationFn: (ids: string[]) =>
      apiClient.post(`/systems/${systemId}/test-scripts/bulk-delete`, { ids }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['test-scripts', systemId] })
      setSelectedKeys(new Set())
    },
  })

  // Modal
  const [exportModalOpen, setExportModalOpen] = useState(false)

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search)
      setOffset(0)
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  const resetOffset = useCallback((setter: (v: string) => void) => (v: string) => {
    setter(v)
    setOffset(0)
  }, [])

  const queryKey = [
    'test-scripts',
    systemId,
    debouncedSearch,
    status,
    format,
    aiOnly,
    offset,
  ]

  const { data, isLoading, error } = useQuery<Page<TestScript>>({
    queryKey,
    queryFn: () => {
      const params = new URLSearchParams()
      if (debouncedSearch) params.set('search', debouncedSearch)
      if (status) params.set('status', status)
      if (format) params.set('format', format)
      if (aiOnly) params.set('ai_generated', 'true')
      params.set('limit', String(LIMIT))
      params.set('offset', String(offset))
      return apiClient
        .get<Page<TestScript>>(`/systems/${systemId}/test-scripts?${params}`)
        .then((r) => r.data)
    },
    enabled: !!systemId,
  })

  const columns = [
    {
      key: 'title',
      header: 'Title',
      render: (row: TestScript) => (
        <div className="flex items-center gap-2">
          {row.ai_generated && (
            <Zap size={13} className="text-yellow-500 shrink-0" title="AI-generated" />
          )}
          <Link
            to={`/test-scripts/${row.id}`}
            className="font-medium text-blue-600 hover:text-blue-800 hover:underline truncate max-w-xs"
          >
            {row.title}
          </Link>
        </div>
      ),
    },
    {
      key: 'format',
      header: 'Format',
      render: (row: TestScript) => <FormatBadge format={row.format} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: TestScript) => <StatusBadge status={row.status} />,
    },
    {
      key: 'version',
      header: 'Version',
      render: (row: TestScript) => (
        <span className="text-sm text-gray-500 font-mono">v{row.version_number}</span>
      ),
    },
    {
      key: 'domain',
      header: 'Domain',
      render: (row: TestScript) => (
        <span className="text-sm text-gray-500">{row.business_domain ?? '—'}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: TestScript) => (
        <span className="text-sm text-gray-500">
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
          <h1 className="text-2xl font-bold text-gray-900">Test Scripts</h1>
          {data && (
            <p className="text-sm text-gray-500 mt-0.5">{data.total} total</p>
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
            placeholder="Search scripts…"
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="relative">
          <select
            value={status}
            onChange={(e) => resetOffset(setStatus)(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>

        <div className="relative">
          <select
            value={format}
            onChange={(e) => resetOffset(setFormat)(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            {FORMAT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={aiOnly}
            onChange={(e) => { setAiOnly(e.target.checked); setOffset(0) }}
            className="rounded border-gray-300 text-blue-600"
          />
          <Zap size={13} className="text-yellow-500" />
          AI-generated only
        </label>
      </div>

      {/* Bulk action bar */}
      {selectedKeys.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg">
          <span className="text-sm font-medium text-blue-700">
            {selectedKeys.size} selected
          </span>
          <RoleGate permission="script:export">
            <button
              onClick={() => setExportModalOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              <Download size={13} />
              Export Selected
            </button>
          </RoleGate>
          <RoleGate permission="content:manage">
            <button
              onClick={() => {
                if (confirm(`Delete ${selectedKeys.size} script(s)?`)) {
                  bulkDelete.mutate(Array.from(selectedKeys))
                }
              }}
              disabled={bulkDelete.isPending}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-40"
            >
              {bulkDelete.isPending ? 'Deleting…' : 'Delete Selected'}
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

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Table */}
      <PaginatedTable<TestScript>
        columns={columns}
        rows={data?.items ?? []}
        getKey={(r) => r.id}
        total={data?.total ?? 0}
        offset={offset}
        limit={LIMIT}
        onOffsetChange={setOffset}
        isLoading={isLoading}
        emptyMessage="No test scripts yet. Generate scripts from requirements to get started."
        selectedKeys={selectedKeys}
        onSelectionChange={setSelectedKeys}
      />

      {/* Export modal */}
      <ExportModal
        open={exportModalOpen}
        selectedIds={Array.from(selectedKeys)}
        onClose={() => {
          setExportModalOpen(false)
          setSelectedKeys(new Set())
        }}
      />
    </div>
  )
}
