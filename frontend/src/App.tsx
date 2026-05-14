import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { SystemProvider } from '@/contexts/SystemContext'
import AppShell from '@/components/layout/AppShell'

// Auth
import LoginPage from '@/pages/auth/LoginPage'
import CallbackPage from '@/pages/auth/CallbackPage'
import UnauthorizedPage from '@/pages/auth/UnauthorizedPage'

// Dashboard
import DashboardPage from '@/pages/dashboard/DashboardPage'

// Systems
import SystemsListPage from '@/pages/systems/SystemsListPage'
import SystemDetailPage from '@/pages/systems/SystemDetailPage'
import SystemSettingsPage from '@/pages/systems/SystemSettingsPage'

// Requirements
import RequirementsPage from '@/pages/requirements/RequirementsPage'
import RequirementDetailPage from '@/pages/requirements/RequirementDetailPage'
import ImportRequirementsPage from '@/pages/requirements/ImportRequirementsPage'

// Test Scripts
import TestScriptsPage from '@/pages/scripts/TestScriptsPage'
import TestScriptDetailPage from '@/pages/scripts/TestScriptDetailPage'

// Test Cycles
import TestCyclesPage from '@/pages/cycles/TestCyclesPage'
import TestCycleDetailPage from '@/pages/cycles/TestCycleDetailPage'
import ExecuteTestPage from '@/pages/cycles/ExecuteTestPage'

// Agents
import AgentsPage from '@/pages/agents/AgentsPage'
import AgentRunDetailPage from '@/pages/agents/AgentRunDetailPage'
import StartAgentPage from '@/pages/agents/StartAgentPage'

// Schedules
import SchedulesPage from '@/pages/schedules/SchedulesPage'
import NewSchedulePage from '@/pages/schedules/NewSchedulePage'

// Evidence
import ExecutionRunsPage from '@/pages/evidence/ExecutionRunsPage'
import ExecutionRunDetailPage from '@/pages/evidence/ExecutionRunDetailPage'

// Reports
import CoverageReportPage from '@/pages/reports/CoverageReportPage'
import ExecutionHistoryPage from '@/pages/reports/ExecutionHistoryPage'
import CompanyOverviewPage from '@/pages/reports/CompanyOverviewPage'
import AIUsagePage from '@/pages/reports/AIUsagePage'

// Admin
import UsersPage from '@/pages/admin/UsersPage'
import CompanySettingsPage from '@/pages/admin/CompanySettingsPage'
import GlobalAdminPage from '@/pages/admin/GlobalAdminPage'
import AdminDashboardPage from '@/pages/admin/AdminDashboardPage'
import AdminCompanyDetailPage from '@/pages/admin/AdminCompanyDetailPage'
import AuditLogPage from '@/pages/admin/AuditLogPage'
import WebhooksPage from '@/pages/admin/WebhooksPage'
import BillingPage from '@/pages/billing/BillingPage'

// Onboarding
import AcceptInvitePage from '@/pages/auth/AcceptInvitePage'
import OnboardingWizardPage from '@/pages/onboarding/OnboardingWizardPage'

// Legacy stubs (kept for backwards-compat until fully migrated)
import AgentMonitorPage from '@/pages/agents/AgentMonitorPage'
import SchedulerPage from '@/pages/scheduler/SchedulerPage'
import EvidenceViewerPage from '@/pages/evidence/EvidenceViewerPage'
import ReportsPage from '@/pages/reports/ReportsPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      {/* ── Public ─────────────────────────────────────────────────── */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<CallbackPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />

      {/* ── Protected (AppShell + SystemProvider) ──────────────────── */}
      <Route
        path="/"
        element={
          <RequireAuth>
            <SystemProvider>
              <AppShell />
            </SystemProvider>
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />

        {/* Dashboard */}
        <Route path="dashboard" element={<DashboardPage />} />

        {/* Systems */}
        <Route path="systems" element={<SystemsListPage />} />
        <Route path="systems/:systemId" element={<SystemDetailPage />} />
        <Route path="systems/:systemId/settings" element={<SystemSettingsPage />} />

        {/* Requirements (system-scoped) */}
        <Route path="systems/:systemId/requirements" element={<RequirementsPage />} />
        <Route path="systems/:systemId/requirements/import" element={<ImportRequirementsPage />} />
        <Route path="requirements/:requirementId" element={<RequirementDetailPage />} />

        {/* Test Scripts (system-scoped) */}
        <Route path="systems/:systemId/scripts" element={<TestScriptsPage />} />
        <Route path="test-scripts/:scriptId" element={<TestScriptDetailPage />} />
        <Route path="scripts/:scriptId" element={<TestScriptDetailPage />} />  {/* legacy */}

        {/* Test Cycles */}
        <Route path="systems/:systemId/cycles" element={<TestCyclesPage />} />
        <Route path="test-cycles/:cycleId" element={<TestCycleDetailPage />} />
        <Route path="test-cycles/:cycleId/assignments/:assignmentId/execute" element={<ExecuteTestPage />} />

        {/* Agents */}
        <Route path="agents" element={<AgentsPage />} />
        <Route path="agents/start" element={<StartAgentPage />} />
        <Route path="agents/:runId" element={<AgentRunDetailPage />} />
        <Route path="systems/:systemId/agents" element={<AgentsPage />} />
        <Route path="systems/:systemId/agents/start" element={<StartAgentPage />} />
        <Route path="agent_runs/:runId" element={<AgentRunDetailPage />} />  {/* legacy */}

        {/* Schedules */}
        <Route path="systems/:systemId/schedules" element={<SchedulesPage />} />
        <Route path="systems/:systemId/schedules/new" element={<NewSchedulePage />} />
        <Route path="schedules" element={<SchedulerPage />} />  {/* legacy */}

        {/* Evidence / Executions */}
        <Route path="systems/:systemId/evidence" element={<ExecutionRunsPage />} />
        <Route path="evidence/:executionId" element={<ExecutionRunDetailPage />} />
        <Route path="scripts/:scriptId/executions" element={<ExecutionRunsPage />} />
        <Route path="executions/:executionId" element={<ExecutionRunDetailPage />} />
        <Route path="executions/:executionId/evidence" element={<EvidenceViewerPage />} />  {/* legacy */}

        {/* Reports */}
        <Route path="reports" element={<CompanyOverviewPage />} />
        <Route path="reports/coverage" element={<CoverageReportPage />} />
        <Route path="reports/execution-history" element={<ExecutionHistoryPage />} />
        <Route path="reports/ai-usage" element={<AIUsagePage />} />
        <Route path="systems/:systemId/reports/coverage" element={<CoverageReportPage />} />
        <Route path="systems/:systemId/reports/execution-history" element={<ExecutionHistoryPage />} />

        {/* Admin */}
        <Route path="admin" element={<AdminDashboardPage />} />
        <Route path="admin/companies/:companyId" element={<AdminCompanyDetailPage />} />
        <Route path="admin/audit-log" element={<AuditLogPage />} />
        <Route path="admin/webhooks" element={<WebhooksPage />} />
        <Route path="admin/users" element={<UsersPage />} />
        <Route path="admin/company" element={<CompanySettingsPage />} />
        <Route path="admin/global" element={<GlobalAdminPage />} />

        {/* Billing */}
        <Route path="billing" element={<BillingPage />} />

        {/* Onboarding wizard */}
        <Route path="onboarding" element={<OnboardingWizardPage />} />

        {/* Legacy stubs */}
        <Route path="agent_monitor" element={<AgentMonitorPage />} />
        <Route path="reports/legacy" element={<ReportsPage />} />
      </Route>
    </Routes>
  )
}
