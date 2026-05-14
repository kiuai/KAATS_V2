import { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Cpu,
  Zap,
  Play,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import apiClient, { errorMessage } from '@/services/api'
import type { AgentType, System, Requirement, TestScript, ScheduleType } from '@/types'
import CronBuilder from '@/components/CronBuilder'
import { useSchedulePreview } from '@/hooks/useSchedulePreview'

// ── Step definitions ──────────────────────────────────────────────────────────

const STEPS = ['Agent Type', 'Configure', 'Schedule', 'Review'] as const
type StepIndex = 0 | 1 | 2 | 3

// ── Agent type cards ──────────────────────────────────────────────────────────

interface AgentTypeCard {
  type: AgentType
  label: string
  description: string
  icon: React.ReactNode
}

const AGENT_TYPE_CARDS: AgentTypeCard[] = [
  {
    type: 'crawl',
    label: 'Crawl Agent',
    description: 'Discover pages and interactions from a live system URL.',
    icon: <Cpu size={24} />,
  },
  {
    type: 'generation',
    label: 'Generation Agent',
    description: 'Generate test scripts from requirements using AI.',
    icon: <Zap size={24} />,
  },
  {
    type: 'execution',
    label: 'Execution Agent',
    description: 'Run approved test scripts against a target system.',
    icon: <Play size={24} />,
  },
]

// ── Agent type -> color ───────────────────────────────────────────────────────

const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  crawl:      'border-purple-400 bg-purple-50 text-purple-700',
  generation: 'border-blue-400 bg-blue-50 text-blue-700',
  execution:  'border-green-400 bg-green-50 text-green-700',
}

// ── Target formats ────────────────────────────────────────────────────────────

const TARGET_FORMATS = [
  { value: 'playwright', label: 'Playwright' },
  { value: 'selenium',   label: 'Selenium' },
  { value: 'pytest',     label: 'PyTest' },
  { value: 'robot',      label: 'Robot Framework' },
  { value: 'gherkin',    label: 'Gherkin' },
]

// ── Reusable field wrapper ────────────────────────────────────────────────────

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
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

// ── Input config interfaces ───────────────────────────────────────────────────

interface CrawlConfig {
  base_url: string
  crawler_type: string
  max_depth: number
  include_patterns: string
  exclude_patterns: string
}

interface GenerateConfig {
  requirement_ids: string[]
  target_formats: string[]
}

interface ExecutionConfig {
  script_ids: string[]
  base_url_override: string
}

// ── Configure step forms ──────────────────────────────────────────────────────

function CrawlConfigForm({
  value,
  onChange,
}: {
  value: CrawlConfig
  onChange: (c: CrawlConfig) => void
}) {
  function set<K extends keyof CrawlConfig>(field: K) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      const v = field === 'max_depth' ? Number(e.target.value) : e.target.value
      onChange({ ...value, [field]: v })
    }
  }

  return (
    <div className="space-y-4">
      <Field label="Base URL" required>
        <input
          type="url"
          value={value.base_url}
          onChange={set('base_url')}
          required
          placeholder="https://app.example.com"
          className={inputCls}
        />
      </Field>
      <Field label="Crawler Type">
        <select value={value.crawler_type} onChange={set('crawler_type')} className={inputCls}>
          <option value="web">Web</option>
          <option value="sap_fiori">SAP Fiori</option>
        </select>
      </Field>
      <Field label="Max Depth">
        <input
          type="number"
          value={value.max_depth}
          onChange={set('max_depth')}
          min={1}
          max={20}
          className={inputCls}
        />
      </Field>
      <Field label="Include Patterns (one per line)">
        <textarea
          value={value.include_patterns}
          onChange={set('include_patterns')}
          rows={3}
          placeholder="/app/*"
          className={textareaCls}
        />
      </Field>
      <Field label="Exclude Patterns (one per line)">
        <textarea
          value={value.exclude_patterns}
          onChange={set('exclude_patterns')}
          rows={3}
          placeholder="/static/*"
          className={textareaCls}
        />
      </Field>
    </div>
  )
}

function GenerateConfigForm({
  systemId,
  value,
  onChange,
}: {
  systemId: string
  value: GenerateConfig
  onChange: (c: GenerateConfig) => void
}) {
  const [expanded, setExpanded] = useState(true)

  const { data: requirements } = useQuery<Requirement[]>({
    queryKey: ['requirements', systemId],
    queryFn: () =>
      apiClient.get(`/systems/${systemId}/requirements`).then((r) => r.data),
    enabled: !!systemId,
  })

  function toggleReq(id: string) {
    const ids = value.requirement_ids.includes(id)
      ? value.requirement_ids.filter((x) => x !== id)
      : [...value.requirement_ids, id]
    onChange({ ...value, requirement_ids: ids })
  }

  function toggleFormat(fmt: string) {
    const fmts = value.target_formats.includes(fmt)
      ? value.target_formats.filter((x) => x !== fmt)
      : [...value.target_formats, fmt]
    onChange({ ...value, target_formats: fmts })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setExpanded((p) => !p)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          Requirements ({value.requirement_ids.length} selected)
        </button>
        {expanded && (
          <div className="border border-gray-200 rounded-xl max-h-52 overflow-y-auto divide-y divide-gray-100">
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
                    checked={value.requirement_ids.includes(req.id)}
                    onChange={() => toggleReq(req.id)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600"
                  />
                  <span className="text-sm text-gray-700 truncate">{req.title}</span>
                </label>
              ))
            )}
          </div>
        )}
      </div>

      <Field label="Target Formats">
        <div className="flex flex-wrap gap-2">
          {TARGET_FORMATS.map((f) => (
            <label
              key={f.value}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm transition-colors ${
                value.target_formats.includes(f.value)
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <input
                type="checkbox"
                checked={value.target_formats.includes(f.value)}
                onChange={() => toggleFormat(f.value)}
                className="sr-only"
              />
              {f.label}
            </label>
          ))}
        </div>
      </Field>
    </div>
  )
}

function ExecutionConfigForm({
  systemId,
  value,
  onChange,
}: {
  systemId: string
  value: ExecutionConfig
  onChange: (c: ExecutionConfig) => void
}) {
  const [expanded, setExpanded] = useState(true)

  const { data: scripts } = useQuery<TestScript[]>({
    queryKey: ['test-scripts', systemId, 'approved'],
    queryFn: () =>
      apiClient
        .get(`/systems/${systemId}/test-scripts`, { params: { status: 'approved' } })
        .then((r) => r.data),
    enabled: !!systemId,
  })

  function toggleScript(id: string) {
    const ids = value.script_ids.includes(id)
      ? value.script_ids.filter((x) => x !== id)
      : [...value.script_ids, id]
    onChange({ ...value, script_ids: ids })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setExpanded((p) => !p)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          Test Scripts ({value.script_ids.length} selected)
        </button>
        {expanded && (
          <div className="border border-gray-200 rounded-xl max-h-52 overflow-y-auto divide-y divide-gray-100">
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
                    checked={value.script_ids.includes(s.id)}
                    onChange={() => toggleScript(s.id)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600"
                  />
                  <span className="text-sm text-gray-700 truncate">{s.title}</span>
                </label>
              ))
            )}
          </div>
        )}
      </div>

      <Field label="Base URL Override (optional)">
        <input
          type="url"
          value={value.base_url_override}
          onChange={(e) => onChange({ ...value, base_url_override: e.target.value })}
          placeholder="https://staging.example.com"
          className={inputCls}
        />
      </Field>
    </div>
  )
}

// ── Main form state ───────────────────────────────────────────────────────────

interface WizardState {
  // Step 1
  agentType: AgentType | null
  // Step 2
  crawlConfig: CrawlConfig
  generateConfig: GenerateConfig
  executionConfig: ExecutionConfig
  // Step 3
  scheduleType: ScheduleType
  cronExpression: string
  oneShot: string
  timezone: string
  name: string
  description: string
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function NewSchedulePage() {
  const { systemId } = useParams<{ systemId: string }>()
  const navigate = useNavigate()

  const [step, setStep] = useState<StepIndex>(0)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const [state, setState] = useState<WizardState>({
    agentType: null,
    crawlConfig: {
      base_url: '',
      crawler_type: 'web',
      max_depth: 3,
      include_patterns: '',
      exclude_patterns: '',
    },
    generateConfig: {
      requirement_ids: [],
      target_formats: ['playwright'],
    },
    executionConfig: {
      script_ids: [],
      base_url_override: '',
    },
    scheduleType: 'recurring',
    cronExpression: '0 9 * * 1',
    oneShot: '',
    timezone: 'UTC',
    name: '',
    description: '',
  })

  const cronPreview = useSchedulePreview(state.cronExpression)

  // Stable onChange for CronBuilder
  const handleCronChange = useCallback(
    (cron: string) => setState((prev) => ({ ...prev, cronExpression: cron })),
    [],
  )

  const { data: system } = useQuery<System>({
    queryKey: ['system', systemId],
    queryFn: () => apiClient.get(`/systems/${systemId}`).then((r) => r.data),
    enabled: !!systemId,
  })

  const createMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiClient
        .post(`/systems/${systemId}/scheduled-jobs`, body)
        .then((r) => r.data),
    onSuccess: () => navigate(`/systems/${systemId}/schedules`),
    onError: (err) => setSubmitError(errorMessage(err)),
  })

  function buildInputConfig(): Record<string, unknown> {
    if (!state.agentType) return {}
    if (state.agentType === 'crawl') {
      return {
        base_url: state.crawlConfig.base_url,
        crawler_type: state.crawlConfig.crawler_type,
        max_depth: state.crawlConfig.max_depth,
        include_patterns: state.crawlConfig.include_patterns
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean),
        exclude_patterns: state.crawlConfig.exclude_patterns
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean),
      }
    }
    if (state.agentType === 'generation') {
      return {
        requirement_ids: state.generateConfig.requirement_ids,
        target_formats: state.generateConfig.target_formats,
      }
    }
    return {
      script_ids: state.executionConfig.script_ids,
      base_url_override: state.executionConfig.base_url_override || undefined,
    }
  }

  function handleCreate() {
    setSubmitError(null)
    const cronExpr =
      state.scheduleType === 'one_shot'
        ? state.cronExpression // For one-shot, cron_expression still required by API
        : state.cronExpression

    createMutation.mutate({
      name: state.name,
      agent_type: state.agentType,
      schedule_type: state.scheduleType,
      cron_expression: cronExpr,
      timezone: state.timezone || 'UTC',
      input_config: buildInputConfig(),
      is_enabled: true,
      system_id: systemId,
    })
  }

  const canAdvanceStep1 = !!state.agentType
  const canAdvanceStep3 =
    !!state.name.trim() &&
    (state.scheduleType === 'recurring' ? !!state.cronExpression : !!state.oneShot)

  const agentTypeCard = AGENT_TYPE_CARDS.find((c) => c.type === state.agentType)

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {/* Back */}
      <Link
        to={`/systems/${systemId}/schedules`}
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800"
      >
        <ChevronLeft size={16} />
        Back to Schedules
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-gray-900">New Schedule</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {system ? `${system.name} — ` : ''}Configure a scheduled agent run.
        </p>
      </div>

      {/* Progress dots */}
      <div className="flex items-center gap-2 justify-center">
        {STEPS.map((label, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div
              className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold transition-colors ${
                idx < step
                  ? 'bg-green-500 text-white'
                  : idx === step
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-400'
              }`}
            >
              {idx < step ? <CheckCircle2 size={14} /> : idx + 1}
            </div>
            <span
              className={`text-xs hidden sm:block ${
                idx === step ? 'text-blue-600 font-medium' : 'text-gray-400'
              }`}
            >
              {label}
            </span>
            {idx < STEPS.length - 1 && (
              <div className={`w-8 h-px ${idx < step ? 'bg-green-300' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Card */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-6">
        {/* Step 1: Agent Type */}
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Choose Agent Type</h2>
            <div className="grid grid-cols-1 gap-3">
              {AGENT_TYPE_CARDS.map((card) => (
                <button
                  key={card.type}
                  type="button"
                  onClick={() => {
                    setState((prev) => ({ ...prev, agentType: card.type }))
                    setStep(1)
                  }}
                  className={`flex items-center gap-4 p-4 rounded-xl border-2 text-left transition-colors ${
                    state.agentType === card.type
                      ? AGENT_TYPE_COLORS[card.type]
                      : 'border-gray-200 hover:border-gray-300 text-gray-700'
                  }`}
                >
                  <span
                    className={
                      state.agentType === card.type ? 'opacity-100' : 'text-gray-400'
                    }
                  >
                    {card.icon}
                  </span>
                  <div>
                    <p className="font-semibold text-sm">{card.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{card.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Configure */}
        {step === 1 && state.agentType && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">
              Configure {agentTypeCard?.label}
            </h2>

            {state.agentType === 'crawl' && (
              <CrawlConfigForm
                value={state.crawlConfig}
                onChange={(c) => setState((prev) => ({ ...prev, crawlConfig: c }))}
              />
            )}
            {state.agentType === 'generation' && systemId && (
              <GenerateConfigForm
                systemId={systemId}
                value={state.generateConfig}
                onChange={(c) => setState((prev) => ({ ...prev, generateConfig: c }))}
              />
            )}
            {state.agentType === 'execution' && systemId && (
              <ExecutionConfigForm
                systemId={systemId}
                value={state.executionConfig}
                onChange={(c) => setState((prev) => ({ ...prev, executionConfig: c }))}
              />
            )}
          </div>
        )}

        {/* Step 3: Schedule */}
        {step === 2 && (
          <div className="space-y-5">
            <h2 className="text-base font-semibold text-gray-900">Schedule</h2>

            {/* Schedule type toggle */}
            <div className="flex gap-4">
              {(['one_shot', 'recurring'] as ScheduleType[]).map((type) => (
                <label key={type} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="schedule_type"
                    value={type}
                    checked={state.scheduleType === type}
                    onChange={() => setState((prev) => ({ ...prev, scheduleType: type }))}
                    className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    {type === 'one_shot' ? 'One-Shot' : 'Recurring'}
                  </span>
                </label>
              ))}
            </div>

            {state.scheduleType === 'one_shot' ? (
              <Field label="Run At" required>
                <input
                  type="datetime-local"
                  value={state.oneShot}
                  onChange={(e) =>
                    setState((prev) => ({ ...prev, oneShot: e.target.value }))
                  }
                  required
                  className={inputCls}
                />
              </Field>
            ) : (
              <div className="space-y-3">
                <label className="text-sm font-medium text-gray-700">Cron Schedule</label>
                <CronBuilder value={state.cronExpression} onChange={handleCronChange} />
                {/* Preview */}
                <div className="flex items-center gap-2 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl">
                  <span className="text-sm text-blue-700">
                    Will run: <strong>{cronPreview || state.cronExpression}</strong>
                  </span>
                </div>
              </div>
            )}

            <Field label="Timezone">
              <input
                type="text"
                value={state.timezone}
                onChange={(e) =>
                  setState((prev) => ({ ...prev, timezone: e.target.value }))
                }
                placeholder="UTC"
                className={inputCls}
              />
            </Field>

            <Field label="Schedule Name" required>
              <input
                type="text"
                value={state.name}
                onChange={(e) => setState((prev) => ({ ...prev, name: e.target.value }))}
                required
                placeholder="Daily Regression Crawl"
                className={inputCls}
              />
            </Field>

            <Field label="Description">
              <textarea
                value={state.description}
                onChange={(e) =>
                  setState((prev) => ({ ...prev, description: e.target.value }))
                }
                rows={2}
                placeholder="Optional description…"
                className={textareaCls}
              />
            </Field>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Review & Create</h2>

            <div className="bg-gray-50 rounded-xl p-4 space-y-3 text-sm">
              <ReviewRow label="Name" value={state.name} />
              <ReviewRow
                label="Agent Type"
                value={agentTypeCard?.label ?? state.agentType ?? ''}
              />
              <ReviewRow
                label="Schedule Type"
                value={state.scheduleType === 'one_shot' ? 'One-Shot' : 'Recurring'}
              />
              {state.scheduleType === 'recurring' ? (
                <>
                  <ReviewRow label="Cron" value={state.cronExpression} mono />
                  <ReviewRow
                    label="Human Readable"
                    value={cronPreview || state.cronExpression}
                  />
                </>
              ) : (
                <ReviewRow
                  label="Run At"
                  value={
                    state.oneShot
                      ? new Date(state.oneShot).toLocaleString()
                      : '—'
                  }
                />
              )}
              <ReviewRow label="Timezone" value={state.timezone || 'UTC'} />
              {state.description && (
                <ReviewRow label="Description" value={state.description} />
              )}
              <div className="pt-2 border-t border-gray-200">
                <p className="text-xs font-medium text-gray-500 mb-2">Input Config</p>
                <pre className="text-xs font-mono text-gray-600 bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(buildInputConfig(), null, 2)}
                </pre>
              </div>
            </div>

            {submitError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {submitError}
              </p>
            )}

            <button
              type="button"
              onClick={handleCreate}
              disabled={createMutation.isPending}
              className="w-full py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {createMutation.isPending ? 'Creating…' : 'Create Schedule'}
            </button>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1) as StepIndex)}
            disabled={step === 0}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40"
          >
            <ChevronLeft size={15} />
            Back
          </button>

          {step < 3 && (
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(3, s + 1) as StepIndex)}
              disabled={
                (step === 0 && !canAdvanceStep1) ||
                (step === 2 && !canAdvanceStep3)
              }
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-40"
            >
              Next
              <ChevronRight size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Review row helper ─────────────────────────────────────────────────────────

function ReviewRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-gray-500 shrink-0">{label}</span>
      <span className={`text-right text-gray-800 ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </span>
    </div>
  )
}
