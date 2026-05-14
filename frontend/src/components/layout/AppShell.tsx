import { Outlet, Link, useMatches } from 'react-router-dom'
import { Bell, LogOut, ChevronDown, User } from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useUiStore } from '@/store/uiStore'
import Sidebar from './Sidebar'
import type { Company } from '@/types'

// ── Breadcrumbs ───────────────────────────────────────────────────────────

interface BreadcrumbHandle {
  breadcrumb?: string | ((params: Record<string, string | undefined>) => string)
}

function Breadcrumbs() {
  const matches = useMatches()
  const crumbs = matches
    .filter((m) => (m.handle as BreadcrumbHandle | null)?.breadcrumb)
    .map((m) => {
      const h = m.handle as BreadcrumbHandle
      const label =
        typeof h.breadcrumb === 'function'
          ? h.breadcrumb(m.params as Record<string, string | undefined>)
          : (h.breadcrumb ?? '')
      return { label, path: m.pathname }
    })

  if (crumbs.length === 0) return null

  return (
    <nav aria-label="breadcrumb" className="flex items-center gap-1 text-sm">
      {crumbs.map((crumb, i) => (
        <span key={crumb.path} className="flex items-center gap-1 text-gray-500">
          {i > 0 && <span>/</span>}
          {i === crumbs.length - 1 ? (
            <span className="text-gray-900 font-medium">{crumb.label}</span>
          ) : (
            <Link to={crumb.path} className="hover:text-gray-900">{crumb.label}</Link>
          )}
        </span>
      ))}
    </nav>
  )
}

// ── Company selector ──────────────────────────────────────────────────────

function CompanySelector() {
  const { currentCompany, companies, setCurrentCompany } = useAuthStore()
  const [open, setOpen] = useState(false)

  if (companies.length <= 1) {
    return (
      <span className="text-sm font-medium text-gray-700">
        {currentCompany?.name ?? '—'}
      </span>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 px-2 py-1 rounded-lg hover:bg-gray-100"
      >
        {currentCompany?.name ?? 'Select company'}
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 z-50 bg-white border border-gray-200 rounded-xl shadow-lg w-52 py-1">
          {companies.map((c: Company) => (
            <button
              key={c.id}
              onClick={() => { setCurrentCompany(c); setOpen(false) }}
              className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                c.id === currentCompany?.id ? 'text-blue-600 font-medium' : 'text-gray-700'
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Notification bell ─────────────────────────────────────────────────────

function NotificationBell() {
  const { notifications, unreadCount, markAllRead } = useUiStore()
  const [open, setOpen] = useState(false)
  const count = unreadCount()

  return (
    <div className="relative">
      <button
        onClick={() => { setOpen((v) => !v); if (count > 0) markAllRead() }}
        className="relative p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100"
        aria-label="Notifications"
      >
        <Bell size={18} />
        {count > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 bg-white border border-gray-200 rounded-xl shadow-lg w-72 py-2">
          <p className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Notifications
          </p>
          {notifications.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400">No notifications</p>
          ) : (
            notifications.slice(0, 10).map((n) => (
              <div key={n.id} className="px-4 py-2 hover:bg-gray-50">
                <p className="text-sm text-gray-700">{n.message}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(n.timestamp).toLocaleTimeString()}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── User menu ─────────────────────────────────────────────────────────────

function UserMenu() {
  const { user, clearAuth } = useAuthStore()
  const [open, setOpen] = useState(false)

  const initials = user?.display_name
    ? user.display_name.split(' ').map((w) => w[0]).slice(0, 2).join('')
    : user?.email?.slice(0, 2).toUpperCase() ?? '?'

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100"
      >
        <div className="w-8 h-8 rounded-full bg-blue-600 text-white text-xs font-semibold flex items-center justify-center">
          {initials}
        </div>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 bg-white border border-gray-200 rounded-xl shadow-lg w-48 py-1">
          <div className="px-4 py-2 border-b border-gray-100">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.display_name ?? 'User'}
            </p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>
          <Link
            to="/admin/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            <User size={14} />
            Profile
          </Link>
          <button
            onClick={clearAuth}
            className="flex items-center gap-2 w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}

// ── App shell ─────────────────────────────────────────────────────────────

export default function AppShell() {
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
          <Breadcrumbs />
          <div className="flex items-center gap-3">
            <CompanySelector />
            <NotificationBell />
            <UserMenu />
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
