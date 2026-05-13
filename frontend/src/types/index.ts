export interface Enterprise {
  id: string
  name: string
  slug: string
  is_active: boolean
  created_at: string
}

export interface Company {
  id: string
  enterprise_id: string
  name: string
  slug: string
  business_domain: string | null
  is_active: boolean
  created_at: string
}

export interface User {
  id: string
  email: string
  display_name: string | null
  is_active: boolean
  created_at: string
}

export interface System {
  id: string
  company_id: string
  owner_id: string
  name: string
  base_url: string
  system_type: string
  status: string
  created_at: string
  updated_at: string
}

export interface Requirement {
  id: string
  system_id: string
  company_id: string
  title: string
  description: string
  status: 'draft' | 'approved' | 'deprecated'
  priority: 1 | 2 | 3
  source: 'agent' | 'manual'
  created_at: string
  updated_at: string
}

export interface TestStep {
  id: string
  step_number: number
  action: string
  description: string
  expected_outcome: string | null
  parameters: Record<string, unknown> | null
}

export interface TestCase {
  id: string
  name: string
  description: string | null
  stop_on_failure: boolean
  order_index: number
  steps: TestStep[]
}

export interface TestScript {
  id: string
  requirement_id: string | null
  system_id: string
  company_id: string
  title: string
  format: string
  status: string
  created_at: string
  updated_at: string
  cases: TestCase[]
}

export interface StepResult {
  id: string
  step_id: string
  status: 'passed' | 'failed' | 'skipped' | 'error'
  actual_outcome: string | null
  failure_reason: string | null
  executed_at: string | null
  duration_ms: number | null
}

export interface TestExecution {
  id: string
  script_id: string
  system_id: string
  company_id: string
  triggered_by: string | null
  status: 'pending' | 'running' | 'passed' | 'failed' | 'error'
  passed_count: number
  failed_count: number
  skipped_count: number
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  step_results: StepResult[]
}

export interface AgentRun {
  id: string
  company_id: string
  system_id: string | null
  agent_type: 'crawl' | 'generation' | 'execution'
  status: 'running' | 'completed' | 'failed' | 'timed_out'
  prompt_tokens: number
  completion_tokens: number
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  execution_id: string | null
  cosmos_doc_id: string | null
}

export interface ScheduledJob {
  id: string
  company_id: string
  system_id: string
  agent_type: string
  cron_expression: string
  timezone: string
  is_enabled: boolean
  max_failures: number
  consecutive_failures: number
  next_run_at: string
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface ScheduledJobRun {
  id: string
  job_id: string
  agent_run_id: string | null
  status: 'enqueued' | 'running' | 'completed' | 'failed'
  scheduled_for: string
  started_at: string | null
  completed_at: string | null
  failure_reason: string | null
}

export interface EvidenceScreenshot {
  id: string
  execution_id: string
  step_result_id: string | null
  blob_path: string
  sas_url: string | null
  sha256: string
  step_number: number
  captured_at: string
}

export interface EvidenceVerifyResult {
  valid: boolean
  failed_steps: number[]
  checked_at: string
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    page: number
    page_size: number
    total_items: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

export interface ApiError {
  error: {
    code: string
    message: string
    details: Record<string, unknown> | null
    request_id: string | null
  }
}
