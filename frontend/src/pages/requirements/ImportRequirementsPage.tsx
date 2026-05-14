import { useState, useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Trash2,
  X,
} from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { RequirementImportPreview } from '@/types'
import FileUploadZone from '@/components/FileUploadZone'

// ── Types ──────────────────────────────────────────────────────────────────

interface EditablePreview extends RequirementImportPreview {
  _key: string
  _expanded: boolean
}

type Step = 1 | 2 | 3

// ── Step indicator ─────────────────────────────────────────────────────────

function StepIndicator({ current }: { current: Step }) {
  const steps: { num: Step; label: string }[] = [
    { num: 1, label: 'Upload' },
    { num: 2, label: 'Preview & Edit' },
    { num: 3, label: 'Confirm' },
  ]
  return (
    <div className="flex items-center gap-0">
      {steps.map((s, i) => (
        <div key={s.num} className="flex items-center">
          <div className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                current === s.num
                  ? 'bg-blue-600 text-white'
                  : current > s.num
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {current > s.num ? <CheckCircle size={14} /> : s.num}
            </div>
            <span
              className={`text-sm ${
                current === s.num ? 'font-semibold text-gray-900' : 'text-gray-500'
              }`}
            >
              {s.label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className="mx-4 h-px w-12 bg-gray-300" />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Editable row ───────────────────────────────────────────────────────────

interface EditableRowProps {
  item: EditablePreview
  index: number
  onChange: (index: number, field: keyof RequirementImportPreview, value: string) => void
  onRemove: (index: number) => void
  onToggleExpand: (index: number) => void
}

function EditableRow({ item, index, onChange, onRemove, onToggleExpand }: EditableRowProps) {
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-gray-50">
        <button
          type="button"
          onClick={() => onToggleExpand(index)}
          className="text-gray-400 hover:text-gray-600 shrink-0"
        >
          {item._expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        <input
          type="text"
          value={item.title}
          onChange={(e) => onChange(index, 'title', e.target.value)}
          className="flex-1 bg-transparent text-sm font-medium text-gray-900 focus:outline-none"
          placeholder="Requirement title"
        />
        <div className="flex items-center gap-2 shrink-0">
          <select
            value={item.priority}
            onChange={(e) => onChange(index, 'priority', e.target.value)}
            className="text-xs rounded border border-gray-200 px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
          <input
            type="text"
            value={item.business_domain ?? ''}
            onChange={(e) => onChange(index, 'business_domain', e.target.value)}
            placeholder="Domain"
            className="w-28 text-xs rounded border border-gray-200 px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => onRemove(index)}
            className="text-gray-400 hover:text-red-500"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {item._expanded && (
        <div className="px-4 pb-3 pt-2 bg-white">
          <textarea
            value={item.description}
            onChange={(e) => onChange(index, 'description', e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Description…"
          />
        </div>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function ImportRequirementsPage() {
  const { systemId = '' } = useParams<{ systemId: string }>()
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>(1)
  const [items, setItems] = useState<EditablePreview[]>([])
  const [sourceReference, setSourceReference] = useState('')
  const [defaultDomain, setDefaultDomain] = useState('')
  const [importedCount, setImportedCount] = useState<number | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)

  // Step 1 — preview
  const previewMutation = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return apiClient
        .post<RequirementImportPreview[]>(
          `/systems/${systemId}/requirements/import/preview`,
          fd,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        )
        .then((r) => r.data)
    },
    onSuccess: (data) => {
      setItems(
        data.map((p, i) => ({
          ...p,
          business_domain: p.business_domain ?? defaultDomain || null,
          _key: `preview-${i}-${Date.now()}`,
          _expanded: false,
        })),
      )
      setStep(2)
      setPageError(null)
    },
    onError: (err) => setPageError(errorMessage(err)),
  })

  // Step 3 — confirm import
  const confirmMutation = useMutation({
    mutationFn: () => {
      const requirements = items.map(({ _key: _k, _expanded: _e, ...rest }) => rest)
      return apiClient
        .post<RequirementImportPreview[]>(
          `/systems/${systemId}/requirements/import/confirm`,
          {
            requirements,
            source_reference: sourceReference || null,
            business_domain: defaultDomain || null,
          },
        )
        .then((r) => r.data)
    },
    onSuccess: (data) => {
      setImportedCount(data.length)
      setStep(3)
      setPageError(null)
    },
    onError: (err) => setPageError(errorMessage(err)),
  })

  const handleFile = useCallback(
    (file: File) => {
      setPageError(null)
      previewMutation.mutate(file)
    },
    [previewMutation],
  )

  const handleItemChange = (
    index: number,
    field: keyof RequirementImportPreview,
    value: string,
  ) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, [field]: value || (field === 'business_domain' ? null : value) } : item,
      ),
    )
  }

  const handleRemove = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  const handleToggleExpand = (index: number) => {
    setItems((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, _expanded: !item._expanded } : item,
      ),
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/systems/${systemId}/requirements`)}
            className="text-gray-400 hover:text-gray-600"
          >
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-xl font-bold text-gray-900">Import Requirements</h1>
        </div>
        <StepIndicator current={step} />
      </div>

      {/* Error */}
      {pageError && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          <span>{pageError}</span>
          <button onClick={() => setPageError(null)}><X size={14} /></button>
        </div>
      )}

      {/* Step 1 — Upload */}
      {step === 1 && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 space-y-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-1">Upload Requirements File</h2>
            <p className="text-sm text-gray-500">
              Upload a document containing requirements. Supported formats: .txt, .csv, .json, .docx, .pdf
            </p>
          </div>

          {/* Optional metadata */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Source Reference <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="text"
                value={sourceReference}
                onChange={(e) => setSourceReference(e.target.value)}
                placeholder="e.g. JIRA sprint, document name"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default Domain <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="text"
                value={defaultDomain}
                onChange={(e) => setDefaultDomain(e.target.value)}
                placeholder="e.g. Finance, HR"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <FileUploadZone
            accept=".txt,.csv,.json,.docx,.pdf"
            maxSizeMb={20}
            onFile={handleFile}
            label={
              previewMutation.isPending
                ? 'Parsing file…'
                : 'Drop file here or click to browse'
            }
          />

          {previewMutation.isPending && (
            <div className="flex items-center gap-2 text-sm text-blue-600">
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              Parsing requirements from file…
            </div>
          )}

          <div className="flex justify-between pt-2">
            <button
              onClick={() => navigate(`/systems/${systemId}/requirements`)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — Preview & Edit */}
      {step === 2 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Review Extracted Requirements
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                <span className="font-medium text-gray-900">{items.length}</span> requirement
                {items.length !== 1 ? 's' : ''} ready to import.
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>Source:</span>
              <input
                type="text"
                value={sourceReference}
                onChange={(e) => setSourceReference(e.target.value)}
                placeholder="Source reference"
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Domain override */}
          <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-lg">
            <label className="text-sm font-medium text-gray-600 whitespace-nowrap">
              Default domain:
            </label>
            <input
              type="text"
              value={defaultDomain}
              onChange={(e) => setDefaultDomain(e.target.value)}
              placeholder="Apply domain to all rows without one"
              className="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() =>
                setItems((prev) =>
                  prev.map((it) => ({
                    ...it,
                    business_domain: defaultDomain || it.business_domain,
                  })),
                )
              }
              className="px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100"
            >
              Apply to all
            </button>
          </div>

          {items.length === 0 ? (
            <div className="text-center py-8 text-sm text-gray-400">
              All rows removed. Go back to re-upload.
            </div>
          ) : (
            <div className="space-y-2 max-h-[480px] overflow-y-auto">
              {items.map((item, i) => (
                <EditableRow
                  key={item._key}
                  item={item}
                  index={i}
                  onChange={handleItemChange}
                  onRemove={handleRemove}
                  onToggleExpand={handleToggleExpand}
                />
              ))}
            </div>
          )}

          <div className="flex justify-between pt-2">
            <button
              onClick={() => setStep(1)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <ArrowLeft size={14} />
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={items.length === 0}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              Continue
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Confirm / Success */}
      {step === 3 && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 space-y-6">
          {importedCount !== null ? (
            // Success state
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100">
                <CheckCircle size={32} className="text-green-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {importedCount} Requirement{importedCount !== 1 ? 's' : ''} Imported
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  All requirements have been successfully added to the system.
                </p>
              </div>
              <div className="flex justify-center gap-3">
                <button
                  onClick={() => {
                    setStep(1)
                    setItems([])
                    setImportedCount(null)
                    setSourceReference('')
                    setDefaultDomain('')
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Import More
                </button>
                <Link
                  to={`/systems/${systemId}/requirements`}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                >
                  View Requirements
                </Link>
              </div>
            </div>
          ) : (
            // Pre-import summary
            <>
              <div>
                <h2 className="text-base font-semibold text-gray-900 mb-1">Confirm Import</h2>
                <p className="text-sm text-gray-500">
                  You are about to import{' '}
                  <span className="font-semibold text-gray-900">{items.length}</span> requirement
                  {items.length !== 1 ? 's' : ''}.
                </p>
              </div>

              {/* Summary table */}
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <table className="min-w-full divide-y divide-gray-100 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Title</th>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Priority</th>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Domain</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
                    {items.map((it) => (
                      <tr key={it._key} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-800 truncate max-w-xs">{it.title}</td>
                        <td className="px-4 py-2 text-gray-600 capitalize">{it.priority}</td>
                        <td className="px-4 py-2 text-gray-500">{it.business_domain ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {sourceReference && (
                <p className="text-sm text-gray-500">
                  Source reference: <span className="font-medium text-gray-700">{sourceReference}</span>
                </p>
              )}

              {confirmMutation.isError && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {errorMessage(confirmMutation.error)}
                </div>
              )}

              <div className="flex justify-between pt-2">
                <button
                  onClick={() => setStep(2)}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  <ArrowLeft size={14} />
                  Back
                </button>
                <button
                  onClick={() => confirmMutation.mutate()}
                  disabled={confirmMutation.isPending || items.length === 0}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle size={14} />
                  {confirmMutation.isPending
                    ? 'Importing…'
                    : `Import ${items.length} Requirement${items.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
