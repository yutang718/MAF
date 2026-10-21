import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import type { AlertItem, AlertStatus, Severity } from '../../types/governance'
import { useGovAuth } from '../authState'
import { ErrorPanel, Loading, PageHeader, SeverityBadge } from '../ui'
import { formatTime, useL10n, useLoad } from '../hooks'

const STATUSES: AlertStatus[] = ['open', 'acknowledged', 'resolved', 'false_positive']
const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']
const PAGE = 50

export default function AlertsPage() {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'active'
  const severity = params.get('severity') ?? ''
  const days = Number(params.get('days') ?? 30)
  const [q, setQ] = useState(params.get('q') ?? '')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<number | null>(Number(params.get('id')) || null)

  const { data, error, loading, reload, setData } = useLoad(() => govApi.alerts({
    status: status === 'active' ? ['open', 'acknowledged'] : status === 'all' ? [] : [status as AlertStatus],
    severity: severity ? [severity] : [], q: params.get('q') ?? undefined, days, offset, limit: PAGE,
  }), [status, severity, days, params.get('q'), offset])

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value); else next.delete(key)
    next.delete('id')
    setParams(next, { replace: true })
    setOffset(0)
  }
  const current = data?.items.find(a => a.id === selected) ?? null
  const replace = (a: AlertItem) => setData(d => d && { ...d, items: d.items.map(x => (x.id === a.id ? a : x)) })

  return (
    <div className="space-y-5">
      <PageHeader title={t('gov.alerts.title')} subtitle={t('gov.alerts.subtitle')} />
      <form className="flex items-center gap-3 flex-wrap" onSubmit={e => { e.preventDefault(); set('q', q.trim()) }}>
        <label htmlFor="al-status" className="sr-only">{t('gov.alerts.status')}</label>
        <select id="al-status" value={status} onChange={e => set('status', e.target.value)} className="gov-select">
          <option value="active">{t('gov.alerts.active')}</option>
          {STATUSES.map(s => <option key={s} value={s}>{t(`gov.astatus.${s}`)}</option>)}
          <option value="all">{t('gov.alerts.all')}</option>
        </select>
        <label htmlFor="al-sev" className="sr-only">{t('gov.alerts.severity')}</label>
        <select id="al-sev" value={severity} onChange={e => set('severity', e.target.value)} className="gov-select">
          <option value="">{t('gov.alerts.anySeverity')}</option>
          {SEVERITIES.map(s => <option key={s} value={s}>{t(`gov.severity.${s}`)}</option>)}
        </select>
        <label htmlFor="al-days" className="sr-only">{t('gov.alerts.period')}</label>
        <select id="al-days" value={days} onChange={e => set('days', e.target.value)} className="gov-select">
          {[1, 7, 30, 90, 365].map(d => <option key={d} value={d}>{t('gov.alerts.lastDays', { n: d })}</option>)}
        </select>
        <label htmlFor="al-q" className="sr-only">{t('gov.alerts.search')}</label>
        <input id="al-q" value={q} onChange={e => setQ(e.target.value)} placeholder={t('gov.alerts.search')}
          className="input-field max-w-xs py-2 text-sm" />
      </form>

      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
          <div className="lg:col-span-3 space-y-2">
            {data.items.length === 0 && <div className="panel text-sm text-cyber-muted">{t('gov.alerts.none')}</div>}
            <ul className="panel-sm p-0 divide-y divide-cyber-border/40">
              {data.items.map(a => (
                <li key={a.id}>
                  <button onClick={() => setSelected(a.id)} aria-current={selected === a.id}
                    className={`w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-cyber-accent/[0.04] ${selected === a.id ? 'bg-cyber-accent/[0.06]' : ''}`}>
                    <SeverityBadge severity={a.severity} />
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm text-cyber-text truncate">{l(a.title)}</span>
                      <span className="block text-xs text-cyber-muted mt-0.5">
                        {l(a.rule)} · {a.connector_name} · {formatTime(a.occurred_at, lang)}
                      </span>
                    </span>
                    <span className="text-xs text-cyber-muted whitespace-nowrap">{t(`gov.astatus.${a.status}`)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {data.total > PAGE && (
              <div className="flex items-center justify-between text-sm text-cyber-muted">
                <span>{t('gov.alerts.range', { from: offset + 1, to: Math.min(offset + PAGE, data.total), total: data.total })}</span>
                <span className="flex gap-2">
                  <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>{t('gov.prev')}</button>
                  <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>{t('gov.next')}</button>
                </span>
              </div>
            )}
          </div>
          <div className="lg:col-span-2 lg:sticky lg:top-20">
            {current ? <AlertDetail key={current.id} alert={current} onChange={replace} /> :
              <div className="panel text-sm text-cyber-muted">{t('gov.alerts.pick')}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

function AlertDetail({ alert, onChange }: { alert: AlertItem; onChange: (a: AlertItem) => void }) {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const { can } = useGovAuth()
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = async (status?: AlertStatus) => {
    setBusy(true); setError('')
    try {
      onChange(await govApi.updateAlert(alert.id, { ...(status ? { status } : {}), ...(note.trim() ? { note } : {}) }))
      setNote('')
    } catch (e) { setError(errorMessage(e, t)) } finally { setBusy(false) }
  }
  // title_zh is the alert's own Chinese title, already shown above.
  const detail = Object.entries(alert.detail).filter(([k, v]) => k !== 'title_zh' && v !== null && v !== '' && v !== undefined)

  return (
    <div className="panel-sm space-y-4" aria-live="polite">
      <div className="flex items-start gap-3">
        <SeverityBadge severity={alert.severity} />
        <h2 className="text-[15px] font-semibold text-cyber-text">{l(alert.title)}</h2>
      </div>
      <dl className="grid grid-cols-3 gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-cyber-muted">{t('gov.alerts.rule')}</dt><dd className="col-span-2 text-cyber-text">{l(alert.rule)}</dd>
        <dt className="text-cyber-muted">{t('gov.alerts.source')}</dt><dd className="col-span-2 text-cyber-text">{alert.connector_name}</dd>
        <dt className="text-cyber-muted">{t('gov.alerts.actor')}</dt><dd className="col-span-2 font-mono text-cyber-text break-all">{alert.actor || '—'}</dd>
        <dt className="text-cyber-muted">{t('gov.alerts.when')}</dt><dd className="col-span-2 text-cyber-text">{formatTime(alert.occurred_at, lang)}</dd>
        <dt className="text-cyber-muted">{t('gov.alerts.status')}</dt><dd className="col-span-2 text-cyber-text">{t(`gov.astatus.${alert.status}`)}</dd>
      </dl>
      <div>
        <p className="text-xs text-cyber-muted uppercase tracking-wider mb-1">{t('gov.alerts.detail')}</p>
        <dl className="text-sm space-y-1 max-h-72 overflow-y-auto">
          {detail.map(([k, v]) => (
            <div key={k} className="grid grid-cols-3 gap-3">
              <dt className="text-cyber-muted break-all">{k}</dt>
              <dd className="col-span-2 font-mono text-xs text-cyber-text break-all whitespace-pre-wrap">
                {typeof v === 'object' ? JSON.stringify(v, null, 1) : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
      {alert.notes.length > 0 && (
        <div>
          <p className="text-xs text-cyber-muted uppercase tracking-wider mb-1">{t('gov.alerts.history')}</p>
          <ol className="space-y-2">
            {alert.notes.map((n, i) => (
              <li key={i} className="text-sm border-l-2 border-cyber-border pl-3">
                <p className="text-cyber-text whitespace-pre-wrap">{n.text}</p>
                <p className="text-xs text-cyber-muted">{n.by} · {formatTime(n.at, lang)} · {t(`gov.astatus.${n.status}`)}</p>
              </li>
            ))}
          </ol>
        </div>
      )}
      {can('auditor') && (
        <div className="space-y-2 border-t border-cyber-border/40 pt-3">
          <label htmlFor="al-note" className="text-sm font-medium text-cyber-text">{t('gov.alerts.note')}</label>
          <textarea id="al-note" value={note} onChange={e => setNote(e.target.value)} className="input-field h-20 resize-none"
            placeholder={t('gov.alerts.notePlaceholder')} />
          {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
          <div className="flex flex-wrap gap-2">
            {alert.status === 'open' && (
              <button disabled={busy} onClick={() => update('acknowledged')} className="btn-ghost text-sm px-3 py-1.5">{t('gov.alerts.ack')}</button>
            )}
            {!['resolved', 'false_positive'].includes(alert.status) && <>
              <button disabled={busy || !note.trim()} onClick={() => update('resolved')} className="btn-ghost text-sm px-3 py-1.5">{t('gov.alerts.resolve')}</button>
              <button disabled={busy || !note.trim()} onClick={() => update('false_positive')} className="btn-ghost text-sm px-3 py-1.5">{t('gov.alerts.falsePositive')}</button>
            </>}
            {['resolved', 'false_positive'].includes(alert.status) && (
              <button disabled={busy} onClick={() => update('open')} className="btn-ghost text-sm px-3 py-1.5">{t('gov.alerts.reopen')}</button>
            )}
            <button disabled={busy || !note.trim()} onClick={() => update()} className="btn-ghost text-sm px-3 py-1.5">{t('gov.alerts.addNote')}</button>
          </div>
          <p className="text-xs text-cyber-muted">{t('gov.alerts.closeHint')}</p>
        </div>
      )}
    </div>
  )
}
