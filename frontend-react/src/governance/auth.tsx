import { useCallback, useEffect, useState, type ReactNode } from 'react'
import axios from 'axios'
import { govApi } from '../api/governance'
import type { GovUser, Role } from '../types/governance'
import { GovAuthContext } from './authState'

const RANK: Record<Role, number> = { viewer: 0, auditor: 1, admin: 2 }

export function GovAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<GovUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [unreachable, setUnreachable] = useState<string | null>(null)

  // State is only set in the promise callbacks, so this is safe to start from an effect.
  const refresh = useCallback((): Promise<void> => govApi.me()
    .then(me => {
      setUser(me)
      setUnreachable(null)
    })
    .catch(e => {
      setUser(null)
      const status = axios.isAxiosError(e) ? e.response?.status : undefined
      setUnreachable(status === 401 ? null : String(status ?? 'network'))
    })
    .finally(() => setChecking(false)), [])

  useEffect(() => { refresh() }, [refresh])

  const signIn = useCallback(async (email: string, password: string) => {
    setUser(await govApi.login(email, password))
    setUnreachable(null)
  }, [])

  const signOut = useCallback(async () => {
    try { await govApi.logout() } finally { setUser(null) }
  }, [])

  const can = useCallback((role: Role) => !!user && RANK[user.role] >= RANK[role], [user])

  return (
    <GovAuthContext.Provider value={{ user, checking, unreachable, signIn, signOut, can, refresh }}>
      {children}
    </GovAuthContext.Provider>
  )
}
