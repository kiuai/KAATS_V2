/**
 * Generic multi-select hook for table rows.
 *
 * Usage:
 *   const { selected, toggle, toggleAll, clear, isSelected, isAllSelected } = useBulkSelect(items)
 */
import { useState, useCallback } from 'react'

export function useBulkSelect<T extends { id: string }>(items: T[]) {
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleAll = useCallback(() => {
    setSelected((prev) => {
      if (prev.size === items.length) return new Set()
      return new Set(items.map((i) => i.id))
    })
  }, [items])

  const clear = useCallback(() => setSelected(new Set()), [])

  const isSelected = useCallback((id: string) => selected.has(id), [selected])

  const isAllSelected = items.length > 0 && selected.size === items.length

  const isIndeterminate = selected.size > 0 && selected.size < items.length

  const selectedIds = Array.from(selected)

  return { selected, selectedIds, toggle, toggleAll, clear, isSelected, isAllSelected, isIndeterminate }
}
