import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { CheckCircle, AlertCircle } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import type { Company } from '@/types'

// ── export format options ─────────────────────────────────────────────────

const EXPORT_FORMATS = [
  { value: 'playwright', label: 'Playwright' },
  { value: 'selenium', label: 'Selenium' },
  { value: 'pytest', label: 'pytest' },
  { value: 'robot', label: 'Robot Framework' },
  { value: 'gherkin', label: 'Gherkin / Cucumber' },
] as const

type ExportFormat = (typeof EXPORT_FORMATS)[number]['value']

// ── form state ────────────────────────────────────────────────────────────

interface FormState {
  name: string
  industry: string
  is_active: boolean
  default_export_format: ExportFormat
  settings_raw: string
}

function companyToForm(c: Company): FormState {
  return {
    name: c.name,
    industry: c.industry ?? '',
    is_active: c.is_active,
    default_export_format: (EXPORT_FORMATS.some((f) => f.value === c.default_export_format)
      ? c.default_export_format
      : 'playwright') as ExportFormat,
    settings_raw: c.settings ? JSON.stringify(c.settings, null, 2) : '',
  }
}

// ── skeleton ──────────────────────────────────────────────────────────────

function FieldSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-3 w-24 bg-gray-200 rounded" />
      <div className="h-10 bg-gray-100 rounded-lg" />
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function CompanySettingsPage() {
  const companyId = useAuthStore((s) => s.currentCompany?.id)
  const setCurrentCompany = useAuthStore((s) => s.setCurrentCompany)

  const [form, setForm] = useState<FormState | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [successBanner, setSuccessBanner] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const {
    data: company,
    isLoading,
    error: fetchError,
  } = useQuery<Company>({
    queryKey: ['company', companyId],
    queryFn: () =>
      apiClient.get<Company>(`/companies/${companyId}`).then((r) => r.data),
    enabled: !!companyId,
  })

  useEffect(() => {
    if (company && form === null) {
      setForm(companyToForm(company))
    }
  }, [company, form])

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!form) throw new Error('No form state')

      let settings: Record<string, unknown> | null = null
      if (form.settings_raw.trim()) {
        settings = JSON.parse(form.settings_raw) as Record<string, unknown>
      }

      return apiClient
        .patch<Company>(`/companies/${companyId}`, {
          name: form.name,
          industry: form.industry || null,
          is_active: form.is_active,
          default_export_format: form.default_export_format,
          settings,
        })
        .then((r) => r.data)
    },
    onSuccess: (updated) => {
      setCurrentCompany(updated)
      setSuccessBanner(true)
      setSaveError(null)
      setTimeout(() => setSuccessBanner(false), 4000)
    },
    onError: (err) => setSaveError(errorMessage(err)),
  })

  const handleSettingsChange = (raw: string) => {
    if (form === null) return
    setForm({ ...form, settings_raw: raw })
    try {
      if (raw.trim()) JSON.parse(raw)
      setSettingsError(null)
    } catch {
      setSettingsError('Invalid JSON')
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (settingsError) return
    setSaveError(null)
    saveMutation.mutate()
  }

  if (!companyId) {
    return (
      <div className="p-6 lg:p-8 max-w-2xl mx-auto">
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          No company context available.
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-6 lg:p-8 max-w-2xl mx-auto">
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(fetchError)}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Company Settings</h1>
        {company && (
          <p className="mt-1 text-sm text-gray-500">
            Slug:{' '}
            <span className="font-mono text-gray-700">{company.slug}</span>
          </p>
        )}
      </div>

      {/* Success banner */}
      {successBanner && (
        <div className="flex items-center gap-2 rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
          <CheckCircle size={16} />
          Changes saved successfully.
        </div>
      )}

      {/* Save error */}
      {saveError && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          <AlertCircle size={16} />
          {saveError}
        </div>
      )}

      {isLoading || form === null ? (
        <div className="space-y-6">
          {Array.from({ length: 6 }).map((_, i) => <FieldSkeleton key={i} />)}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Section 1: Company Info */}
          <section className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">
              Company Info
            </h2>

            <div>
              <label
                htmlFor="company-name"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Name
              </label>
              <input
                id="company-name"
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="company-industry"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Industry
              </label>
              <input
                id="company-industry"
                type="text"
                value={form.industry}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                placeholder="e.g. Healthcare, Finance"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="company-slug"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Slug{' '}
                <span className="text-xs text-gray-400 font-normal">(read-only)</span>
              </label>
              <input
                id="company-slug"
                type="text"
                value={company?.slug ?? ''}
                disabled
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500 cursor-not-allowed font-mono"
              />
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                role="switch"
                aria-checked={form.is_active}
                onClick={() => setForm({ ...form, is_active: !form.is_active })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                  form.is_active ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    form.is_active ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span className="text-sm font-medium text-gray-700">
                {form.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </section>

          {/* Section 2: Defaults */}
          <section className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">
              Defaults
            </h2>

            <div>
              <label
                htmlFor="export-format"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Default Export Format
              </label>
              <select
                id="export-format"
                value={form.default_export_format}
                onChange={(e) =>
                  setForm({ ...form, default_export_format: e.target.value as ExportFormat })
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {EXPORT_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
          </section>

          {/* Section 3: Settings JSON */}
          <section className="bg-white border border-gray-200 rounded-2xl p-6 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wide">
                Advanced Settings (JSON)
              </h2>
              <span className="text-xs text-gray-400">Optional</span>
            </div>

            <textarea
              value={form.settings_raw}
              onChange={(e) => handleSettingsChange(e.target.value)}
              rows={8}
              className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 ${
                settingsError
                  ? 'border-red-400 focus:ring-red-400'
                  : 'border-gray-300 focus:ring-blue-500'
              }`}
              placeholder='{ "key": "value" }'
            />
            {settingsError && (
              <p className="text-xs text-red-600">{settingsError}</p>
            )}
          </section>

          {/* Save button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saveMutation.isPending || !!settingsError}
              className="px-6 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saveMutation.isPending ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
