import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { errorMessage } from '../api/client'
import { useTranslation } from '../i18n/context'
import type { L10n } from '../types/governance'

export function useL10n() {
  const { lang } = useTranslation()
  return useCallback((v: L10n | null | undefined) => (v ? (lang === 'zh' ? v.zh : v.en) || v.en : ''), [lang])
}

/**
 * Load whenever `deps` change; `reload` runs it again. A response that arrives
 * after newer deps is dropped. The error is kept raw, so its message follows a
 * language switch without refetching.
 */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const { t } = useTranslation()
  const fnRef = useRef(fn)
  useLayoutEffect(() => { fnRef.current = fn })
  const [tick, setTick] = useState(0)
  const key = `${JSON.stringify(deps)}#${tick}`
  const [state, setState] = useState<{ key: string | null; data: T | null; failure: unknown }>(
    { key: null, data: null, failure: null })

  useEffect(() => {
    let live = true
    fnRef.current().then(
      data => { if (live) setState({ key, data, failure: null }) },
      failure => { if (live) setState(s => ({ key, data: s.data, failure })) },
    )
    return () => { live = false }
  }, [key])

  const reload = useCallback(() => setTick(n => n + 1), [])
  const setData = useCallback((update: (d: T | null) => T | null) => setState(s => ({ ...s, data: update(s.data) })), [])
  return {
    data: state.data,
    error: state.failure ? errorMessage(state.failure, t) : '',
    loading: state.key !== key,
    reload,
    setData,
  }
}

export function formatTime(iso: string | null | undefined, lang: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-GB', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function formatAgo(iso: string | null | undefined, t: (k: string, v?: Record<string, string | number>) => string) {
  if (!iso) return t('gov.never')
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return t('gov.justNow')
  if (minutes < 60) return t('gov.minutesAgo', { n: minutes })
  const hours = Math.round(minutes / 60)
  if (hours < 48) return t('gov.hoursAgo', { n: hours })
  return t('gov.daysAgo', { n: Math.round(hours / 24) })
}
