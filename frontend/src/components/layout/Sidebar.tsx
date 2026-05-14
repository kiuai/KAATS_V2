import { NavLink, useParams } from 'react-router-dom'
import {
  LayoutDashboard, Server, FileText, Code2, ClipboardList,
  Bot, Calendar, Shield, BarChart2, Users, ChevronLeft, ChevronRight,
  FolderOpen,
} from 'lucide-react'
import { useUiStore } from '@/store/uiStore'
import { usePermission } from '@/hooks/usePermission'

const linkClass = (isActive: boolean, collapsed: boolean) =>
  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
    isActive
      ? 'bg-blue-50 text-blue-700'
      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
  } ${collapsed ? 'justify-center' : ''}`

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
  collapsed: boolean
  end?: boolean
}

function NavItem({ to, icon, label, collapsed, end = false }: NavItemProps) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => linkClass(isActive, collapsed)}>
      <span className="shrink-0">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  )
}

export default function Sidebar() {
  const { systemId } = useParams<{ systemId?: string }>()
  const { sidebarCollapsed, toggleSidebar } = useUiStore()

  const canSeeAgents  = usePermission('agent:crawl')
  const canSeeSchedule = usePermission('schedule:read')
  const canSeeAdmin    = usePermission('admin:company')
  const canSeeReports  = usePermission('report:read')

  const w = sidebarCollapsed ? 'w-16' : 'w-60'

  return (
    <aside className={`${w} bg-white border-r border-gray-200 flex flex-col transition-all duration-200 shrink-0`}>
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-gray-200 justify-between">
        {!sidebarCollapsed && (
          <span className="text-lg font-bold text-blue-600 select-none">KAATS</span>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5">
        {/* Top-level */}
        <NavItem to="/dashboard" icon={<LayoutDashboard size={18} />} label="Dashboard" collapsed={sidebarCollapsed} end />
        <NavItem to="/systems" icon={<Server size={18} />} label="Systems" collapsed={sidebarCollapsed} />

        {/* System-context section */}
        {systemId && (
          <div className="mt-3">
            {!sidebarCollapsed && (
              <p className="px-3 mb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                Current System
              </p>
            )}
            <NavItem to={`/systems/${systemId}`} icon={<FolderOpen size={18} />} label="Overview" collapsed={sidebarCollapsed} end />
            <NavItem to={`/systems/${systemId}/requirements`} icon={<FileText size={18} />} label="Requirements" collapsed={sidebarCollapsed} />
            <NavItem to={`/systems/${systemId}/scripts`} icon={<Code2 size={18} />} label="Test Scripts" collapsed={sidebarCollapsed} />
            <NavItem to={`/systems/${systemId}/cycles`} icon={<ClipboardList size={18} />} label="Test Cycles" collapsed={sidebarCollapsed} />
            {canSeeAgents && (
              <NavItem to={`/systems/${systemId}/agents`} icon={<Bot size={18} />} label="Agents" collapsed={sidebarCollapsed} />
            )}
            {canSeeSchedule && (
              <NavItem to={`/systems/${systemId}/schedules`} icon={<Calendar size={18} />} label="Schedules" collapsed={sidebarCollapsed} />
            )}
          </div>
        )}

        <div className="h-px bg-gray-100 my-3" />

        {canSeeReports && (
          <NavItem to="/reports" icon={<BarChart2 size={18} />} label="Reports" collapsed={sidebarCollapsed} />
        )}
        {canSeeAdmin && (
          <NavItem to="/admin/users" icon={<Users size={18} />} label="Administration" collapsed={sidebarCollapsed} />
        )}
        {!canSeeAdmin && (
          <NavItem to="/admin/users" icon={<Users size={18} />} label="Users" collapsed={sidebarCollapsed} />
        )}
      </nav>
    </aside>
  )
}
