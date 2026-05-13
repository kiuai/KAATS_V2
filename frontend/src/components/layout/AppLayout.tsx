import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Server,
  FileText,
  PlayCircle,
  Bot,
  Calendar,
  BarChart2,
  Users,
  LogOut,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/systems', label: 'Systems', icon: Server },
  { to: '/agents', label: 'Agent Runs', icon: Bot },
  { to: '/schedules', label: 'Schedules', icon: Calendar },
  { to: '/reports', label: 'Reports', icon: BarChart2 },
  { to: '/users', label: 'Users', icon: Users },
]

export default function AppLayout() {
  const clearAuth = useAuthStore((s) => s.clearAuth)

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="h-16 flex items-center px-5 border-b border-gray-200">
          <span className="text-lg font-bold text-blue-600">KAATS</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={clearAuth}
          className="flex items-center gap-3 px-6 py-4 text-sm text-gray-500 hover:text-gray-900 border-t border-gray-200"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
