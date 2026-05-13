import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import LoginPage from '@/pages/auth/LoginPage'
import DashboardPage from '@/pages/dashboard/DashboardPage'
import SystemsPage from '@/pages/systems/SystemsPage'
import SystemDetailPage from '@/pages/systems/SystemDetailPage'
import RequirementsPage from '@/pages/requirements/RequirementsPage'
import TestScriptsPage from '@/pages/scripts/TestScriptsPage'
import TestScriptDetailPage from '@/pages/scripts/TestScriptDetailPage'
import ExecutionsPage from '@/pages/executions/ExecutionsPage'
import ExecutionDetailPage from '@/pages/executions/ExecutionDetailPage'
import AgentMonitorPage from '@/pages/agents/AgentMonitorPage'
import SchedulerPage from '@/pages/scheduler/SchedulerPage'
import EvidenceViewerPage from '@/pages/evidence/EvidenceViewerPage'
import ReportsPage from '@/pages/reports/ReportsPage'
import UsersPage from '@/pages/users/UsersPage'
import AppLayout from '@/components/layout/AppLayout'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="systems" element={<SystemsPage />} />
        <Route path="systems/:systemId" element={<SystemDetailPage />} />
        <Route path="systems/:systemId/requirements" element={<RequirementsPage />} />
        <Route path="systems/:systemId/scripts" element={<TestScriptsPage />} />
        <Route path="scripts/:scriptId" element={<TestScriptDetailPage />} />
        <Route path="scripts/:scriptId/executions" element={<ExecutionsPage />} />
        <Route path="executions/:executionId" element={<ExecutionDetailPage />} />
        <Route path="executions/:executionId/evidence" element={<EvidenceViewerPage />} />
        <Route path="agents" element={<AgentMonitorPage />} />
        <Route path="agent_runs/:runId" element={<AgentMonitorPage />} />
        <Route path="schedules" element={<SchedulerPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>
    </Routes>
  )
}
