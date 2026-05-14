import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Column<T> {
  key: string
  header: string
  render: (row: T) => React.ReactNode
  className?: string
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  getKey: (row: T) => string
  total: number
  offset: number
  limit: number
  onOffsetChange: (offset: number) => void
  isLoading?: boolean
  emptyMessage?: string
  selectedKeys?: Set<string>
  onSelectionChange?: (keys: Set<string>) => void
}

export default function PaginatedTable<T>({
  columns,
  rows,
  getKey,
  total,
  offset,
  limit,
  onOffsetChange,
  isLoading = false,
  emptyMessage = 'No items found.',
  selectedKeys,
  onSelectionChange,
}: Props<T>) {
  const pageCount = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1
  const hasSelection = selectedKeys !== undefined && onSelectionChange !== undefined

  const toggleAll = () => {
    if (!onSelectionChange) return
    const allKeys = new Set(rows.map(getKey))
    const allSelected = rows.every((r) => selectedKeys?.has(getKey(r)))
    onSelectionChange(allSelected ? new Set() : allKeys)
  }

  const toggleRow = (key: string) => {
    if (!onSelectionChange || !selectedKeys) return
    const next = new Set(selectedKeys)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onSelectionChange(next)
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50">
            <tr>
              {hasSelection && (
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-blue-600"
                    checked={rows.length > 0 && rows.every((r) => selectedKeys.has(getKey(r)))}
                    onChange={toggleAll}
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide ${col.className ?? ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {hasSelection && <td className="px-4 py-3"><div className="h-4 w-4 bg-gray-200 rounded" /></td>}
                    {columns.map((col) => (
                      <td key={col.key} className="px-4 py-3">
                        <div className="h-4 bg-gray-200 rounded w-24" />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.length === 0
              ? (
                <tr>
                  <td
                    colSpan={columns.length + (hasSelection ? 1 : 0)}
                    className="px-4 py-12 text-center text-sm text-gray-400"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              )
              : rows.map((row) => {
                  const key = getKey(row)
                  const isSelected = selectedKeys?.has(key)
                  return (
                    <tr
                      key={key}
                      className={`transition-colors ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'}`}
                    >
                      {hasSelection && (
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            className="rounded border-gray-300 text-blue-600"
                            checked={isSelected ?? false}
                            onChange={() => toggleRow(key)}
                          />
                        </td>
                      )}
                      {columns.map((col) => (
                        <td key={col.key} className={`px-4 py-3 text-sm text-gray-700 ${col.className ?? ''}`}>
                          {col.render(row)}
                        </td>
                      ))}
                    </tr>
                  )
                })}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      {total > limit && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <p className="text-sm text-gray-500">
            Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onOffsetChange(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-gray-600 px-2">
              {currentPage} / {pageCount}
            </span>
            <button
              onClick={() => onOffsetChange(offset + limit)}
              disabled={offset + limit >= total}
              className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
