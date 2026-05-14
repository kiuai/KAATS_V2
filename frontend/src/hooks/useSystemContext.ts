import { useSystemContext as _useSystemContext } from '@/contexts/SystemContext'
import type { System } from '@/types'

export function useSystemContext(): System | null {
  return _useSystemContext().activeSystem
}
