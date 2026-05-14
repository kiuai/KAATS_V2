// ── Tenant ─────────────────────────────────────────────────────────────────

export interface Enterprise {
  id: string
  name: string
  slug: string
  azure_ad_tenant_id: string | null
  is_active: boolean
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface Company {
  id: string
  enterprise_id: string
  name: string
  slug: string
  industry: string | null
  default_export_format: string
  is_active: boolean
  is_deleted: boolean
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

// ── User & Roles ───────────────────────────────────────────────────────────

export type UserRoleEnum =
  | 'global_admin'
  | 'enterprise_admin'
  | 'company_admin'
  | 'system_manager'
  | 'validation_lead'
  | 'qa'
  | 'validation_tester'
  | 'bpo'

export interface UserRole {
  id: string
  user_id: string
  enterprise_id: string | null
  company_id: string | null
  system_id: string | null
  role: UserRoleEnum
  business_domain: string | null
  granted_by: string | null
  expires_at: string | null
  created_at: string
}

export interface User {
  id: string
  email: string
  display_name: string | null
  azure_oid: string | null
  is_active: boolean
  is_global_admin: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

// ── System ─────────────────────────────────────────────────────────────────

export interface SystemStats {
  requirement_count: number
  active_requirement_count: number
  script_count: number
  approved_script_count: number
  coverage_pct: number
  last_crawl_at: string | null
  last_execution_at: string | null
}

export interface System {
  id: string
  company_id: string
  system_manager_id: string | null
  name: string
  description: string | null
  base_url: string | null
  system_type: string
  is_active: boolean
  is_deleted: boolean
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface SystemDetail extends System {
  stats: SystemStats | null
}

// ── Requirement ───────────────────────────────────────────────────────────

export type RequirementStatus = 'draft' | 'active' | 'deprecated'
export type RequirementPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Requirement {
  id: string
  system_id: string
  company_id: string
  title: string
  description: string
  source_type: string
  source_reference: string | null
  business_domain: string | null
  priority: RequirementPriority
  status: RequirementStatus
  tags: string[] | null
  created_by: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface RequirementWithScripts extends Requirement {
  script_count: number
  approved_script_count: number
}

export interface QualityCheckResult {
  score: number
  grade: string
  suggestions: string[]
  cached: boolean
}

export interface RequirementImportPreview {
  title: string
  description: string
  source_type: string
  business_domain: string | null
  priority: string
  tags: string[] | null
}

// ── Test Script ───────────────────────────────────────────────────────────

export type TestScriptStatus = 'draft' | 'in_review' | 'approved' | 'deprecated'

export interface TestScriptVersion {
  id: string
  test_script_id: string
  version_number: number
  title: string
  format: string
  rendered_content: string | null
  script_content: Record<string, unknown> | null
  change_summary: string | null
  created_by: string | null
  created_at: string
}

export interface TestScript {
  id: string
  requirement_id: string | null
  system_id: string
  company_id: string
  title: string
  description: string | null
  format: string
  status: TestScriptStatus
  version_number: number
  ai_generated: boolean
  business_domain: string | null
  approved_by: string | null
  approved_at: string | null
  rejection_comment: string | null
  created_by: string | null
  deleted_at: string | null
  created_at: string
  updated_at: string
  rendered_content: string | null
  script_content: Record<string, unknown> | null
}

// ── Test Cycle ────────────────────────────────────────────────────────────

export type TestCycleStatus = 'planned' | 'in_progress' | 'completed' | 'aborted'
export type TestAssignmentStatus = 'pending' | 'in_progress' | 'passed' | 'failed' | 'blocked' | 'skipped'
export type TestOutcome = 'passed' | 'failed' | 'blocked' | 'skipped'

export interface TestCycle {
  id: string
  system_id: string
  company_id: string
  name: string
  description: string | null
  status: TestCycleStatus
  planned_start: string | null
  planned_end: string | null
  actual_start: string | null
  actual_end: string | null
  lead_user_id: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface TestCycleProgress {
  total: number
  passed: number
  failed: number
  pending: number
  blocked: number
  skipped?: number
}

export interface TestCycleWithProgress extends TestCycle {
  progress: TestCycleProgress
}

export interface TestAssignment {
  id: string
  test_cycle_id: string
  test_script_id: string
  assigned_to: string
  assigned_by: string
  due_date: string | null
  status: TestAssignmentStatus
  assigned_at: string
}

export interface TestResult {
  id: string
  assignment_id: string
  test_script_id: string
  company_id: string
  executed_by: string
  execution_agent_run_id: string | null
  executed_at: string
  outcome: TestOutcome
  actual_result: string | null
  defect_reference: string | null
  notes: string | null
  created_at: string
}

// ── Legacy Execution ──────────────────────────────────────────────────────

export interface StepResult {
  id: string
  step_id: string
  status: 'passed' | 'failed' | 'skipped' | 'error'
  actual_outcome: string | null
  failure_reason: string | null
  executed_at: string | null
  duration_ms: number | null
}

export interface ExecutionRun {
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

// ── Agent Runs ────────────────────────────────────────────────────────────

export type AgentRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'timed_out' | 'cancelled'
export type AgentType = 'crawl' | 'generation' | 'execution'

export interface AgentToolCall {
  tool_name: string
  input: Record<string, unknown>
  output: unknown
  duration_ms: number | null
  success: boolean
  called_at: string
}

export interface AgentRun {
  id: string
  company_id: string
  system_id: string | null
  agent_type: AgentType
  status: AgentRunStatus
  trigger_type: string
  triggered_by_user_id: string | null
  input_config: Record<string, unknown> | null
  output_summary: Record<string, unknown> | null
  prompt_tokens: number
  completion_tokens: number
  total_cost_usd: number | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

// ── Scheduled Jobs ────────────────────────────────────────────────────────

export type ScheduleType = 'one_shot' | 'recurring'

export interface ScheduledJob {
  id: string
  company_id: string
  system_id: string
  agent_type: AgentType
  name: string
  description: string | null
  schedule_type: ScheduleType
  cron_expression: string
  timezone: string
  is_enabled: boolean
  input_config: Record<string, unknown> | null
  max_failures: number
  consecutive_failures: number
  next_run_at: string | null
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

// ── Evidence ──────────────────────────────────────────────────────────────

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

// ── Reports ───────────────────────────────────────────────────────────────

export interface CycleReportSummary {
  cycle_id: string
  cycle_name: string
  cycle_status: string
  total: number
  passed: number
  failed: number
  blocked: number
  skipped: number
  pending: number
  in_progress: number
  pass_rate: number
}

export interface DomainCoverage {
  domain: string | null
  requirement_count: number
  script_count: number
  approved_script_count: number
  coverage_pct: number
}

export interface CompanyOverview {
  company_id: string
  system_count: number
  requirement_count: number
  script_count: number
  approved_script_count: number
  active_cycle_count: number
}

// ── Pagination ────────────────────────────────────────────────────────────

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
  next_cursor: string | null
}

export interface ApiError {
  error: {
    code: string
    message: string
    details: Record<string, unknown> | null
    request_id: string | null
  }
}
