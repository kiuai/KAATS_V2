import { Outlet, Link, useMatches, useNavigate } from 'react-router-dom'
import { Bell, LogOut, ChevronDown, User, Search } from 'lucide-react'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import api from '@/services/api'
import CommandPalette from '@/components/CommandPalette'
import Sidebar from './Sidebar'
import type { Company } from '@/types'

interface BackendNotification {
  id: string
  type: string
  title: string
  body: string | null
  action_url: string | null
  resource_type: string | null
  resource_id: string | null
  is_read: boolean
  created_at: string
}

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

const TYPE_STYLES: Record<string, string> = {
  success: 'text-green-600',
  error: 'text-red-600',
  warning: 'text-yellow-600',
  info: 'text-blue-600',
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

  const { data: notifications = [] } = useQuery<BackendNotification[]>({
    queryKey: ['notifications'],
    queryFn: () => api.get('/notifications?limit=20').then((r) => r.data),
    refetchInterval: 30_000, // poll every 30 s
    enabled: isAuthenticated,
  })

  const { data: countData } = useQuery<{ count: number }>({
    queryKey: ['notifications-count'],
    queryFn: () => api.get('/notifications/count').then((r) => r.data),
    refetchInterval: 30_000,
    enabled: isAuthenticated,
  })

  const markAll = useMutation({
    mutationFn: () => api.patch('/notifications/read-all'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] })
    },
  })

  const markOne = useMutation({
    mutationFn: (id: string) => api.patch(`/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] })
    },
  })

  const count = countData?.count ?? 0

  const handleOpen = () => {
    setOpen((v) => {
      if (!v && count > 0) markAll.mutate()
      return !v
    })
  }

  const handleClick = (n: BackendNotification) => {
    if (!n.is_read) markOne.mutate(n.id)
    if (n.action_url) {
      navigate(n.action_url)
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={handleOpen}
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
        <div className="absolute top-full right-0 mt-1 z-50 bg-white border border-gray-200 rounded-xl shadow-lg w-80 py-2">
          <p className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Notifications
          </p>
          {notifications.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400">No notifications</p>
          ) : (
            notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => handleClick(n)}
                className={`w-full text-left px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0 ${!n.is_read ? 'bg-blue-50/40' : ''}`}
              >
                <p className={`text-sm font-medium ${TYPE_STYLES[n.type] ?? 'text-gray-700'}`}>
                  {n.title}
                </p>
                {n.body && <p className="text-xs text-gray-500 mt-0.5 truncate">{n.body}</p>}
                <p className="text-[10px] text-gray-400 mt-1">
                  {new Date(n.created_at).toLocaleTimeString()}
                </p>
              </button>
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
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-semibold flex items-center justify-center ring-2 ring-white">
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
      <CommandPalette />
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header */}
        <header className="h-14 bg-white border-b border-gray-100 flex items-center justify-between px-5 shrink-0 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <Breadcrumbs />
          <div className="flex items-center gap-2">
            {/* Cmd+K search trigger */}
            <button
              onClick={() => {
                const e = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true })
                document.dispatchEvent(e)
              }}
              className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-400 hover:bg-white hover:border-gray-300 hover:text-gray-600 transition-colors"
            >
              <Search size={13} />
              <span>Search</span>
              <kbd className="ml-1 px-1.5 py-0.5 text-[10px] font-medium bg-white border border-gray-200 rounded text-gray-400">⌘K</kbd>
            </button>
            <div className="h-5 w-px bg-gray-100 mx-1" />
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
