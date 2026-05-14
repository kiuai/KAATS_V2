import { createContext, useContext, useState } from 'react'
import type { System } from '@/types'

interface SystemContextValue {
  activeSystem: System | null
  setActiveSystem: (system: System | null) => void
}

const SystemContext = createContext<SystemContextValue>({
  activeSystem: null,
  setActiveSystem: () => undefined,
})

export function SystemProvider({ children }: { children: React.ReactNode }) {
  const [activeSystem, setActiveSystem] = useState<System | null>(null)

  return (
    <SystemContext.Provider value={{ activeSystem, setActiveSystem }}>
      {children}
    </SystemContext.Provider>
  )
}

export function useSystemContext(): SystemContextValue {
  return useContext(SystemContext)
}
