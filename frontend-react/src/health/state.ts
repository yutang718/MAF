import { createContext, useContext } from 'react'
import type { HealthResponse } from '../api/health'

/**
 * checking: first probe still in flight
 * online:   API reachable and guard models loaded
 * degraded: API reachable but no guard model loaded
 * offline:  API unreachable or erroring
 */
export type ApiStatus = 'checking' | 'online' | 'degraded' | 'offline'

export interface HealthState {
  status: ApiStatus
  health: HealthResponse | null
  /** When the last probe finished, success or not */
  checkedAt: Date | null
  /** Plain-language reason the last probe failed */
  error: string | null
  recheck: () => Promise<void>
}

export const HealthContext = createContext<HealthState | null>(null)

export function useHealth(): HealthState {
  const ctx = useContext(HealthContext)
  if (!ctx) throw new Error('useHealth must be used within a HealthProvider')
  return ctx
}
