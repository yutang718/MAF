import { createContext, useContext } from 'react'
import type { GovUser, Role } from '../types/governance'

export interface GovAuth {
  user: GovUser | null
  checking: boolean
  /** Set when the service itself couldn't be reached (not merely "signed out"). */
  unreachable: string | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  can: (role: Role) => boolean
  refresh: () => Promise<void>
}

export const GovAuthContext = createContext<GovAuth | null>(null)

export function useGovAuth(): GovAuth {
  const ctx = useContext(GovAuthContext)
  if (!ctx) throw new Error('useGovAuth must be used within GovAuthProvider')
  return ctx
}
