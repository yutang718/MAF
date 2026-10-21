import { useState, useEffect } from 'react'
import { getMafGuardInfo } from '../api/prompt'
import type { MafGuardInfo } from '../types/prompt'

// The EVYD Defender release actually loaded by the backend (resolved from the Hub tag), fetched once per page load.
let infoPromise: Promise<MafGuardInfo | null> | null = null

export function useMafGuardInfo(): MafGuardInfo | null {
  const [info, setInfo] = useState<MafGuardInfo | null>(null)
  useEffect(() => {
    if (!infoPromise) infoPromise = getMafGuardInfo().catch(() => { infoPromise = null; return null })
    let alive = true
    infoPromise.then(i => { if (alive) setInfo(i) })
    return () => { alive = false }
  }, [])
  return info
}

export function mafGuardName(version?: string | null): string {
  return version ? `EVYD Defender ${version}` : 'EVYD Defender'
}

export function useMafGuardName(): string {
  return mafGuardName(useMafGuardInfo()?.version)
}
