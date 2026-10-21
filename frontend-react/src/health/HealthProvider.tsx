import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react'
import { getHealth, type HealthResponse } from '../api/health'
import { errorMessage } from '../api/client'
import { useTranslation } from '../i18n/context'
import { HealthContext, type ApiStatus } from './state'

const POLL_MS = 30_000

/** Polls the backend health endpoint so every status indicator reflects reality. */
export function HealthProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [status, setStatus] = useState<ApiStatus>('checking')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  // Kept raw so the message follows a language switch without re-probing.
  const [failure, setFailure] = useState<unknown>(null)
  const inFlight = useRef(false)

  // State is only set in the promise callbacks, never synchronously, so the
  // probe is safe to start from an effect.
  const probe = useCallback((): Promise<void> => {
    if (inFlight.current) return Promise.resolve()
    inFlight.current = true
    return getHealth()
      .then((data) => {
        setHealth(data)
        setStatus(data.components.guard_models.status === 'up' ? 'online' : 'degraded')
        setFailure(null)
      })
      .catch((err) => {
        setHealth(null)
        setStatus('offline')
        setFailure(err)
      })
      .finally(() => {
        setCheckedAt(new Date())
        inFlight.current = false
      })
  }, [])

  useEffect(() => {
    probe()
    const timer = setInterval(probe, POLL_MS)
    // Coming back to the tab is when a stale status misleads most.
    const onFocus = () => probe()
    window.addEventListener('focus', onFocus)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [probe])

  return (
    <HealthContext.Provider
      value={{ status, health, checkedAt, error: failure ? errorMessage(failure, t) : null, recheck: probe }}
    >
      {children}
    </HealthContext.Provider>
  )
}
