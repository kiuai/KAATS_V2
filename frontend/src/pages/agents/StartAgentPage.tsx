import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { ChevronLeft, ChevronDown, ChevronUp } from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { System, Requirement, TestScript, AgentRun } from '@/types'

// ── Tab definitions ───────────────────────────────────────────────────────────

type TabId = 'crawl' | 'generation' | 'execution'

const TABS: { id: TabId; label: string }[] = [
  { id: 'crawl',      label: 'Crawl' },
  { id: 'generation', label: 'Generate' },
  { id: 'execution',  label: 'Execute' },
]

const CRAWLER_TYPES = [
  { value: 'web',       label: 'Web' },
  { value: 'sap_fiori', label: 'SAP Fiori' },
]

const TARGET_FORMATS = [
  { value: 'playwright', label: 'Playwright' },
  { value: 'selenium',   label: 'Selenium' },
  { value: 'pytest',     label: 'PyTest' },
  { value: 'robot',      label: 'Robot Framework' },
  { value: 'gherkin',    label: 'Gherkin' },
]

// ── Form field helpers ────────────────────────────────────────────────────────

interface FieldProps {
  label: string
  required?: boolean
  children: React.ReactNode
}

function Field({ label, required, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls =
  'border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'
const textareaCls = `${inputCls} resize-none`

// ── System selector ───────────────────────────────────────────────────────────

interface SystemSelectProps {
  value: string
  onChange: (id: string) => void
  systems: System[]
}

function SystemSelect({ value, onChange, systems }: SystemSelectProps) {
  return (
    <Field label="System" required>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        className={inputCls}
      >
        <option value="">— Select system —</option>
        {systems.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </Field>
  )
}

// ── Crawl form ────────────────────────────────────────────────────────────────

interface CrawlFormState {
  system_id: string
  base_url: string
  crawler_type: string
  max_depth: number
  include_patterns: string
  exclude_patterns: string
}

interface CrawlFormProps {
  systems: System[]
  urlSystemId: string | undefined
  onSubmit: (data: CrawlFormState) => void
  isPending: boolean
  submitError: string | null
}

function CrawlForm({ systems, urlSystemId, onSubmit, isPending, submitError }: CrawlFormProps) {
  const [form, setForm] = useState<CrawlFormState>({
    system_id: urlSystemId ?? '',
    base_url: '',
    crawler_type: 'web',
    max_depth: 3,
    include_patterns: '',
    exclude_patterns: '',
  })

  // Prefill base_url when system changes
  const selectedSystem = systems.find((s) => s.id === form.system_id)
  useEffect(() => {
    if (selectedSystem?.base_url) {
      setForm((prev) => ({ ...prev, base_url: selectedSystem.base_url ?? '' }))
    }
  }, [selectedSystem?.base_url, selectedSystem?.id])

  function set<K extends keyof CrawlFormState>(field: K) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      const val = field === 'max_depth' ? Number(e.target.value) : e.target.value
      setForm((prev) => ({ ...prev, [field]: val }))
    }
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(form) }}
      className="space-y-4"
    >
      {!urlSystemId && (
        <SystemSelect
          value={form.system_id}
          onChange={(id) => setForm((prev) => ({ ...prev, system_id: id }))}
          systems={systems}
        />
      )}

      <Field label="Base URL" required>
        <input
          type="url"
          value={form.base_url}
          onChange={set('base_url')}
          required
          placeholder="https://app.example.com"
          className={inputCls}
        />
      </Field>

      <Field label="Crawler Type" required>
        <select value={form.crawler_type} onChange={set('crawler_type')} className={inputCls}>
          {CRAWLER_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </Field>

      <Field label="Max Depth">
        <input
          type="number"
          value={form.max_depth}
          onChange={set('max_depth')}
          min={1}
          max={20}
          className={inputCls}
        />
      </Field>

      <Field label="Include Patterns (one per line)">
        <textarea
          value={form.include_patterns}
          onChange={set('include_patterns')}
          rows={3}
          placeholder="/app/*&#10;/portal/*"
          className={textareaCls}
        />
      </Field>

      <Field label="Exclude Patterns (one per line)">
        <textarea
          value={form.exclude_patterns}
          onChange={set('exclude_patterns')}
          rows={3}
          placeholder="/logout*&#10;/static/*"
          className={textareaCls}
        />
      </Field>

      <SubmitFooter isPending={isPending} submitError={submitError} label="Start Crawl" />
    </form>
  )
}

// ── Generate form ─────────────────────────────────────────────────────────────

interface GenerateFormState {
  system_id: string
  requirement_ids: string[]
  target_formats: string[]
}

interface GenerateFormProps {
  systems: System[]
  urlSystemId: string | undefined
  onSubmit: (data: GenerateFormState) => void
  isPending: boolean
  submitError: string | null
}

function GenerateForm({ systems, urlSystemId, onSubmit, isPending, submitError }: GenerateFormProps) {
  const [systemId, setSystemId] = useState(urlSystemId ?? '')
  const [requirementIds, setRequirementIds] = useState<string[]>([])
  const [targetFormats, setTargetFormats] = useState<string[]>(['playwright'])
  const [reqExpanded, setReqExpanded] = useState(true)

  const { data: requirements } = useQuery<Requirement[]>({
    queryKey: ['requirements', systemId],
    queryFn: () =>
      apiClient.get(`/systems/${systemId}/requirements`).then((r) => r.data),
    enabled: !!systemId,
  })

  function toggleReq(id: string) {
    setRequirementIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  function toggleFormat(val: string) {
    setTargetFormats((prev) =>
      prev.includes(val) ? prev.filter((x) => x !== val) : [...prev, val],
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ system_id: systemId, requirement_ids: requirementIds, target_formats: targetFormats })
      }}
      className="space-y-4"
    >
      {!urlSystemId && (
        <SystemSelect value={systemId} onChange={setSystemId} systems={systems} />
      )}

      {/* Requirements */}
      {systemId && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setReqExpanded((p) => !p)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            {reqExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            Requirements ({requirementIds.length} selected)
          </button>
          {reqExpanded && (
            <div className="border border-gray-200 rounded-xl max-h-60 overflow-y-auto divide-y divide-gray-100">
              {(requirements ?? []).length === 0 ? (
                <p className="px-4 py-3 text-sm text-gray-400">No requirements found.</p>
              ) : (
                (requirements ?? []).map((req) => (
                  <label
                    key={req.id}
                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={requirementIds.includes(req.id)}
                      onChange={() => toggleReq(req.id)}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700 truncate">{req.title}</span>
                  </label>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Target formats */}
      <Field label="Target Formats">
        <div className="flex flex-wrap gap-2">
          {TARGET_FORMATS.map((f) => (
            <label
              key={f.value}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm transition-colors ${
                targetFormats.includes(f.value)
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <input
                type="checkbox"
                checked={targetFormats.includes(f.value)}
                onChange={() => toggleFormat(f.value)}
                className="sr-only"
              />
              {f.label}
            </label>
          ))}
        </div>
      </Field>

      <SubmitFooter isPending={isPending} submitError={submitError} label="Start Generation" />
    </form>
  )
}

// ── Execute form ──────────────────────────────────────────────────────────────

interface ExecuteFormState {
  system_id: string
  script_ids: string[]
  base_url_override: string
}

interface ExecuteFormProps {
  systems: System[]
  urlSystemId: string | undefined
  onSubmit: (data: ExecuteFormState) => void
  isPending: boolean
  submitError: string | null
}

function ExecuteForm({ systems, urlSystemId, onSubmit, isPending, submitError }: ExecuteFormProps) {
  const [systemId, setSystemId] = useState(urlSystemId ?? '')
  const [scriptIds, setScriptIds] = useState<string[]>([])
  const [baseUrlOverride, setBaseUrlOverride] = useState('')
  const [scriptsExpanded, setScriptsExpanded] = useState(true)

  const { data: scripts } = useQuery<TestScript[]>({
    queryKey: ['test-scripts', systemId, 'approved'],
    queryFn: () =>
      apiClient
        .get(`/systems/${systemId}/test-scripts`, { params: { status: 'approved' } })
        .then((r) => r.data),
    enabled: !!systemId,
  })

  function toggleScript(id: string) {
    setScriptIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({ system_id: systemId, script_ids: scriptIds, base_url_override: baseUrlOverride })
      }}
      className="space-y-4"
    >
      {!urlSystemId && (
        <SystemSelect value={systemId} onChange={setSystemId} systems={systems} />
      )}

      {/* Script selection */}
      {systemId && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setScriptsExpanded((p) => !p)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            {scriptsExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            Test Scripts ({scriptIds.length} selected)
          </button>
          {scriptsExpanded && (
            <div className="border border-gray-200 rounded-xl max-h-60 overflow-y-auto divide-y divide-gray-100">
              {(scripts ?? []).length === 0 ? (
                <p className="px-4 py-3 text-sm text-gray-400">No approved scripts found.</p>
              ) : (
                (scripts ?? []).map((s) => (
                  <label
                    key={s.id}
                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={scriptIds.includes(s.id)}
                      onChange={() => toggleScript(s.id)}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700 truncate">{s.title}</span>
                  </label>
                ))
              )}
            </div>
          )}
        </div>
      )}

      <Field label="Base URL Override (optional)">
        <input
          type="url"
          value={baseUrlOverride}
          onChange={(e) => setBaseUrlOverride(e.target.value)}
          placeholder="https://staging.example.com"
          className={inputCls}
        />
      </Field>

      <SubmitFooter isPending={isPending} submitError={submitError} label="Start Execution" />
    </form>
  )
}

// ── Shared submit footer ──────────────────────────────────────────────────────

interface SubmitFooterProps {
  isPending: boolean
  submitError: string | null
  label: string
}

function SubmitFooter({ isPending, submitError, label }: SubmitFooterProps) {
  return (
    <>
      {submitError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {submitError}
        </p>
      )}
      <button
        type="submit"
        disabled={isPending}
        className="w-full py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
      >
        {isPending ? 'Starting…' : label}
      </button>
    </>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function StartAgentPage() {
  const { systemId: urlSystemId } = useParams<{ systemId?: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const defaultTab = (searchParams.get('type') as TabId | null) ?? 'crawl'
  const [activeTab, setActiveTab] = useState<TabId>(
    TABS.some((t) => t.id === defaultTab) ? defaultTab : 'crawl',
  )
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { data: systems } = useQuery<System[]>({
    queryKey: ['systems'],
    queryFn: () => apiClient.get('/systems').then((r) => r.data),
    enabled: !urlSystemId,
  })

  const crawlMutation = useMutation({
    mutationFn: (data: {
      system_id: string
      base_url: string
      crawler_type: string
      max_depth: number
      include_patterns: string[]
      exclude_patterns: string[]
    }) => apiClient.post('/agent_runs/crawl', data).then((r) => r.data as AgentRun),
    onSuccess: (run) => navigate(`/agents/${run.id}`),
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  const generateMutation = useMutation({
    mutationFn: (data: {
      system_id: string
      requirement_ids: string[]
      target_formats: string[]
    }) => apiClient.post('/agent_runs/generation', data).then((r) => r.data as AgentRun),
    onSuccess: (run) => navigate(`/agents/${run.id}`),
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  const executeMutation = useMutation({
    mutationFn: (data: {
      system_id: string
      script_ids: string[]
      base_url_override?: string
    }) => apiClient.post('/agent_runs/execution', data).then((r) => r.data as AgentRun),
    onSuccess: (run) => navigate(`/agents/${run.id}`),
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  function handleTabChange(tab: TabId) {
    setActiveTab(tab)
    setSubmitError(null)
  }

  const allSystems = systems ?? []

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {/* Back */}
      <Link
        to="/agents"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800"
      >
        <ChevronLeft size={16} />
        Back to Agents
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Start New Agent</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure and launch an agent run.</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="border-b border-gray-200 flex">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'crawl' && (
            <CrawlForm
              systems={allSystems}
              urlSystemId={urlSystemId}
              isPending={crawlMutation.isPending}
              submitError={submitError}
              onSubmit={(data) => {
                setSubmitError(null)
                crawlMutation.mutate({
                  system_id: urlSystemId ?? data.system_id,
                  base_url: data.base_url,
                  crawler_type: data.crawler_type,
                  max_depth: data.max_depth,
                  include_patterns: data.include_patterns
                    .split('\n')
                    .map((l) => l.trim())
                    .filter(Boolean),
                  exclude_patterns: data.exclude_patterns
                    .split('\n')
                    .map((l) => l.trim())
                    .filter(Boolean),
                })
              }}
            />
          )}

          {activeTab === 'generation' && (
            <GenerateForm
              systems={allSystems}
              urlSystemId={urlSystemId}
              isPending={generateMutation.isPending}
              submitError={submitError}
              onSubmit={(data) => {
                setSubmitError(null)
                generateMutation.mutate({
                  system_id: urlSystemId ?? data.system_id,
                  requirement_ids: data.requirement_ids,
                  target_formats: data.target_formats,
                })
              }}
            />
          )}

          {activeTab === 'execution' && (
            <ExecuteForm
              systems={allSystems}
              urlSystemId={urlSystemId}
              isPending={executeMutation.isPending}
              submitError={submitError}
              onSubmit={(data) => {
                setSubmitError(null)
                executeMutation.mutate({
                  system_id: urlSystemId ?? data.system_id,
                  script_ids: data.script_ids,
                  base_url_override: data.base_url_override || undefined,
                })
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
