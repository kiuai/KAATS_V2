/**
 * Cmd+K / Ctrl+K command palette for global search.
 * Mount once at app root; it opens/closes via keyboard shortcut.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Server, FileText, Code2, ClipboardList, Bot } from 'lucide-react'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'

interface SearchResult {
  type: string
  id: string
  label: string
  description: string | null
  url: string
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  system: <Server size={14} className="text-gray-400" />,
  requirement: <FileText size={14} className="text-blue-400" />,
  test_script: <Code2 size={14} className="text-green-400" />,
  test_cycle: <ClipboardList size={14} className="text-purple-400" />,
  agent_run: <Bot size={14} className="text-orange-400" />,
}

const TYPE_LABELS: Record<string, string> = {
  system: 'System',
  requirement: 'Requirement',
  test_script: 'Test Script',
  test_cycle: 'Test Cycle',
  agent_run: 'Agent Run',
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

  // Open on Cmd+K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setQuery('')
      setActiveIdx(0)
    }
  }, [open])

  const { data: results = [], isFetching } = useQuery<SearchResult[]>({
    queryKey: ['search', query],
    queryFn: () =>
      api.get(`/search?q=${encodeURIComponent(query)}&limit=20`).then((r) => r.data),
    enabled: isAuthenticated && open && query.trim().length >= 2,
    staleTime: 10_000,
  })

  const navigate_to = useCallback(
    (url: string) => {
      navigate(url)
      setOpen(false)
    },
    [navigate],
  )

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && results[activeIdx]) {
      navigate_to(results[activeIdx].url)
    }
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] bg-black/40"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl bg-white rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search size={16} className="text-gray-400 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIdx(0) }}
            onKeyDown={handleKey}
            placeholder="Search systems, requirements, scripts…"
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          />
          {isFetching && (
            <span className="text-xs text-gray-400">Searching…</span>
          )}
          <kbd className="hidden md:inline text-[10px] text-gray-400 border border-gray-200 rounded px-1.5 py-0.5">
            Esc
          </kbd>
        </div>

        {/* Results */}
        {query.trim().length >= 2 ? (
          results.length === 0 && !isFetching ? (
            <p className="px-4 py-6 text-sm text-center text-gray-400">No results for "{query}"</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto py-2">
              {results.map((r, i) => (
                <li key={r.id}>
                  <button
                    onClick={() => navigate_to(r.url)}
                    onMouseEnter={() => setActiveIdx(i)}
                    className={`w-full text-left flex items-center gap-3 px-4 py-2.5 ${
                      i === activeIdx ? 'bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    <span className="shrink-0">{TYPE_ICONS[r.type] ?? <Search size={14} />}</span>
                    <span className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-gray-900 truncate block">
                        {r.label}
                      </span>
                      {r.description && (
                        <span className="text-xs text-gray-400 truncate block">{r.description}</span>
                      )}
                    </span>
                    <span className="text-[10px] text-gray-400 shrink-0">
                      {TYPE_LABELS[r.type] ?? r.type}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          <div className="px-4 py-5 text-xs text-gray-400 text-center">
            Type at least 2 characters to search
          </div>
        )}

        <div className="border-t border-gray-100 px-4 py-2 flex gap-4 text-[10px] text-gray-400">
          <span><kbd className="border border-gray-200 rounded px-1">↑↓</kbd> Navigate</span>
          <span><kbd className="border border-gray-200 rounded px-1">↵</kbd> Open</span>
          <span><kbd className="border border-gray-200 rounded px-1">Esc</kbd> Close</span>
          <span className="ml-auto">
            <kbd className="border border-gray-200 rounded px-1">⌘K</kbd> Toggle
          </span>
        </div>
      </div>
    </div>
  )
}
