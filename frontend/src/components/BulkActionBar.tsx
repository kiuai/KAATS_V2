/**
 * Floating bulk-action toolbar that appears when rows are selected in a table.
 * Renders above the table via a portal.
 */
import { X } from 'lucide-react'

interface BulkAction {
  label: string
  variant?: 'default' | 'danger'
  onClick: () => void
  loading?: boolean
}

interface BulkActionBarProps {
  selectedCount: number
  actions: BulkAction[]
  onClear: () => void
}

export default function BulkActionBar({ selectedCount, actions, onClear }: BulkActionBarProps) {
  if (selectedCount === 0) return null

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-gray-900 text-white px-4 py-2.5 rounded-xl shadow-xl animate-in slide-in-from-bottom-4">
      <span className="text-sm font-medium">{selectedCount} selected</span>
      <div className="w-px h-4 bg-gray-600" />
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={action.onClick}
          disabled={action.loading}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
            action.variant === 'danger'
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-gray-700 hover:bg-gray-600 text-white'
          }`}
        >
          {action.loading ? 'Working…' : action.label}
        </button>
      ))}
      <button
        onClick={onClear}
        className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700"
        aria-label="Clear selection"
      >
        <X size={14} />
      </button>
    </div>
  )
}
