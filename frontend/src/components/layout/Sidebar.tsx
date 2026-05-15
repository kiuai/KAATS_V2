import { NavLink, useParams } from 'react-router-dom'
import {
  LayoutDashboard, Server, FileText, Code2, ClipboardList,
  Bot, Calendar, BarChart2, Users, ChevronLeft, ChevronRight,
  FolderOpen, ShieldCheck, ScrollText, Webhook, CreditCard,
  Zap,
} from 'lucide-react'
import { useUiStore } from '@/store/uiStore'
import { usePermission } from '@/hooks/usePermission'

const linkClass = (isActive: boolean, collapsed: boolean) =>
  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
    isActive
      ? 'bg-indigo-600 text-white shadow-sm'
      : 'text-slate-400 hover:bg-slate-800 hover:text-white'
  } ${collapsed ? 'justify-center px-2' : ''}`

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
  collapsed: boolean
  end?: boolean
}

function NavItem({ to, icon, label, collapsed, end = false }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      className={({ isActive }) => linkClass(isActive, collapsed)}
    >
      <span className="shrink-0">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  )
}

function SectionLabel({ label, collapsed }: { label: string; collapsed: boolean }) {
  if (collapsed) return <div className="h-px bg-slate-800 mx-2 my-3" />
  return (
    <p className="px-3 pt-4 pb-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-widest select-none">
      {label}
    </p>
  )
}

export default function Sidebar() {
  const { systemId } = useParams<{ systemId?: string }>()
  const { sidebarCollapsed, toggleSidebar } = useUiStore()

  const canSeeAgents    = usePermission('agent:crawl')
  const canSeeSchedule  = usePermission('schedule:read')
  const canSeeAdmin     = usePermission('admin:company')
  const canSeeReports   = usePermission('report:read')
  const isPlatformAdmin = usePermission('admin:global')

  const w = sidebarCollapsed ? 'w-[60px]' : 'w-60'

  return (
    <aside
      className={`${w} bg-slate-900 flex flex-col transition-all duration-200 shrink-0 relative`}
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800 shrink-0">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2 select-none">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
              <Zap size={14} className="text-white" />
            </div>
            <span className="text-white font-bold tracking-tight text-base">KAATS</span>
          </div>
        )}
        {sidebarCollapsed && (
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center mx-auto">
            <Zap size={14} className="text-white" />
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className={`p-1.5 rounded-md text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors shrink-0 ${sidebarCollapsed ? 'absolute -right-3 top-5 bg-slate-900 border border-slate-700 rounded-full z-10' : ''}`}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5 sidebar-scroll">
        <NavItem to="/dashboard" icon={<LayoutDashboard size={16} />} label="Dashboard" collapsed={sidebarCollapsed} end />
        <NavItem to="/systems"   icon={<Server size={16} />}          label="Systems"   collapsed={sidebarCollapsed} />

        {/* System-context section */}
        {systemId && (
          <>
            <SectionLabel label="Current System" collapsed={sidebarCollapsed} />
            <NavItem to={`/systems/${systemId}`}              icon={<FolderOpen size={16} />}    label="Overview"      collapsed={sidebarCollapsed} end />
            <NavItem to={`/systems/${systemId}/requirements`} icon={<FileText size={16} />}      label="Requirements"  collapsed={sidebarCollapsed} />
            <NavItem to={`/systems/${systemId}/scripts`}      icon={<Code2 size={16} />}         label="Test Scripts"  collapsed={sidebarCollapsed} />
            <NavItem to={`/systems/${systemId}/cycles`}       icon={<ClipboardList size={16} />} label="Test Cycles"   collapsed={sidebarCollapsed} />
            {canSeeAgents   && <NavItem to={`/systems/${systemId}/agents`}    icon={<Bot size={16} />}      label="Agents"    collapsed={sidebarCollapsed} />}
            {canSeeSchedule && <NavItem to={`/systems/${systemId}/schedules`} icon={<Calendar size={16} />} label="Schedules" collapsed={sidebarCollapsed} />}
          </>
        )}

        <SectionLabel label="Platform" collapsed={sidebarCollapsed} />

        {canSeeReports   && <NavItem to="/reports"      icon={<BarChart2 size={16} />}  label="Reports"        collapsed={sidebarCollapsed} />}
        {canSeeAdmin     && <NavItem to="/admin/users"  icon={<Users size={16} />}      label="Administration" collapsed={sidebarCollapsed} />}
        {!canSeeAdmin    && <NavItem to="/admin/users"  icon={<Users size={16} />}      label="Users"          collapsed={sidebarCollapsed} />}
        {isPlatformAdmin && <NavItem to="/admin"        icon={<ShieldCheck size={16} />} label="Platform Admin" collapsed={sidebarCollapsed} end />}
        {isPlatformAdmin && <NavItem to="/admin/audit-log" icon={<ScrollText size={16} />} label="Audit Log"   collapsed={sidebarCollapsed} />}
        {canSeeAdmin     && <NavItem to="/admin/webhooks"  icon={<Webhook size={16} />}    label="Webhooks"    collapsed={sidebarCollapsed} />}
        {canSeeAdmin     && <NavItem to="/billing"         icon={<CreditCard size={16} />} label="Billing"     collapsed={sidebarCollapsed} />}
      </nav>
    </aside>
  )
}
