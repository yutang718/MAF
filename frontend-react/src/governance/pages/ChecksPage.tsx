import { useMemo, useState, type FormEvent } from 'react'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import type { CheckCatalogEntry, CheckResult } from '../../types/governance'
import { useGovAuth } from '../authState'
import { CheckStatusBadge, ErrorPanel, Field, Loading, PageHeader, SeverityBadge } from '../ui'
import { useL10n, useLoad } from '../hooks'
import { ResultCard } from './ControlPage'

const KINDS = ['m365', 'github', 'gitlab', 'archery']
type Show = 'problems' | 'all' | 'unavailable'

export default function ChecksPage() {
  const { t } = useTranslation()
  const l = useL10n()
  const { can } = useGovAuth()
  const { data, error, loading, reload } = useLoad(() => govApi.checks(), [])
  const [kind, setKind] = useState('all')
  const [show, setShow] = useState<Show>('problems')
  const [open, setOpen] = useState<string | null>(null)
  const [excepting, setExcepting] = useState<{ check: CheckCatalogEntry; result: CheckResult } | null>(null)

  const rows = useMemo(() => (data ?? []).filter(c => {
    if (kind !== 'all' && c.kind !== kind) return false
    if (show === 'all') return true
    if (show === 'unavailable') return c.results.some(r => ['not_available', 'error'].includes(r.status))
    return c.results.some(r => ['fail', 'partial', 'error'].includes(r.status))
  }), [data, kind, show])

  return (
    <div className="space-y-5">
      <PageHeader title={t('gov.checks.title')} subtitle={t('gov.checks.subtitle')} />
      <div className="flex items-center gap-3 flex-wrap">
        <label htmlFor="chk-kind" className="sr-only">{t('gov.checks.source')}</label>
        <select id="chk-kind" value={kind} onChange={e => setKind(e.target.value)} className="gov-select">
          <option value="all">{t('gov.checks.allSources')}</option>
          {KINDS.map(k => <option key={k} value={k}>{t(`gov.kind.${k}`)}</option>)}
        </select>
        <label htmlFor="chk-show" className="sr-only">{t('gov.checks.show')}</label>
        <select id="chk-show" value={show} onChange={e => setShow(e.target.value as Show)} className="gov-select">
          <option value="problems">{t('gov.checks.showProblems')}</option>
          <option value="unavailable">{t('gov.checks.showUnavailable')}</option>
          <option value="all">{t('gov.checks.showAll')}</option>
        </select>
      </div>
      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && rows.length === 0 && (
        <div className="panel text-sm text-cyber-muted">{show === 'problems' ? t('gov.checks.noProblems') : t('gov.checks.none')}</div>
      )}
      <ul className="space-y-2">
        {rows.map(c => (
          <li key={c.id} className="panel-sm p-0">
            <button className="w-full text-left px-5 py-3 flex items-center gap-3 flex-wrap" aria-expanded={open === c.id}
              onClick={() => setOpen(open === c.id ? null : c.id)}>
              <span className="badge-info gov-badge">{t(`gov.kind.${c.kind}`)}</span>
              <span className="text-[15px] text-cyber-text flex-1 min-w-[200px]">{l(c.title)}</span>
              {c.severity && <SeverityBadge severity={c.severity} />}
              {c.results.length === 0
                ? <span className="gov-badge-muted gov-badge">{t('gov.checks.noConnector')}</span>
                : c.results.map(r => <CheckStatusBadge key={r.id} status={r.status} />)}
            </button>
            {open === c.id && (
              <div className="px-5 pb-4 space-y-3 border-t border-cyber-border/40 pt-3">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-cyber-muted">
                  {Object.entries(c.mappings).map(([fw, ids]) => (
                    <span key={fw}>{t(`gov.fw.name.${fw}`)}: <span className="font-mono text-cyber-text">{ids.join(', ')}</span></span>
                  ))}
                </div>
                {c.results.map(r => (
                  <div key={r.id} className="space-y-2">
                    <DetailedResult id={r.id} fallback={r} />
                    {can('auditor') && ['fail', 'partial'].includes(r.status) && (
                      <button className="btn-ghost text-sm px-3 py-1.5" onClick={() => setExcepting({ check: c, result: r })}>
                        {t('gov.exc.request')}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      {excepting && <ExceptionForm entry={excepting} onClose={() => setExcepting(null)} onDone={() => { setExcepting(null); reload() }} />}
    </div>
  )
}

/** Fetches the result with its items when expanded; the catalog only carries counts. */
function DetailedResult({ id, fallback }: { id: number; fallback: CheckResult }) {
  const { data } = useLoad(() => govApi.checkResult(id), [id])
  return <ResultCard result={data ? { ...data, status: fallback.status } : fallback} />
}

function ExceptionForm({ entry, onClose, onDone }: {
  entry: { check: CheckCatalogEntry; result: CheckResult }; onClose: () => void; onDone: () => void
}) {
  const { t } = useTranslation()
  const l = useL10n()
  const [reason, setReason] = useState('')
  const [compensating, setCompensating] = useState('')
  const [expires, setExpires] = useState(() => new Date(Date.now() + 90 * 864e5).toISOString().slice(0, 10))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await govApi.requestException({ check_id: entry.check.id, connector_id: entry.result.connector_id, reason,
        compensating_controls: compensating, expires_on: expires })
      onDone()
    } catch (err) { setError(errorMessage(err, t)) } finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-50 bg-cyber-bg/70 backdrop-blur-sm flex items-center justify-center p-4" role="dialog"
      aria-modal="true" aria-labelledby="exc-title" onKeyDown={e => e.key === 'Escape' && onClose()}>
      <form onSubmit={submit} className="panel w-full max-w-lg space-y-4 bg-cyber-surface">
        <div>
          <h2 id="exc-title" className="text-lg font-semibold text-cyber-text">{t('gov.exc.request')}</h2>
          <p className="text-sm text-cyber-muted mt-1">{l(entry.check.title)} · {entry.result.connector_name}</p>
          <p className="text-xs text-cyber-muted mt-2 leading-relaxed">{t('gov.exc.help')}</p>
        </div>
        <Field label={t('gov.exc.reason')} hint={t('gov.exc.reasonHint')} htmlFor="exc-reason">
          <textarea id="exc-reason" autoFocus required value={reason} onChange={e => setReason(e.target.value)} className="input-field h-24 resize-none" />
        </Field>
        <Field label={t('gov.exc.compensating')} htmlFor="exc-comp">
          <textarea id="exc-comp" value={compensating} onChange={e => setCompensating(e.target.value)} className="input-field h-16 resize-none" />
        </Field>
        <Field label={t('gov.exc.expires')} hint={t('gov.exc.expiresHint')} htmlFor="exc-exp">
          <input id="exc-exp" type="date" required value={expires} onChange={e => setExpires(e.target.value)} className="input-field py-2" />
        </Field>
        {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">{t('gov.cancel')}</button>
          <button type="submit" disabled={busy || reason.trim().length < 20} className="btn-primary">{t('gov.exc.submit')}</button>
        </div>
      </form>
    </div>
  )
}
