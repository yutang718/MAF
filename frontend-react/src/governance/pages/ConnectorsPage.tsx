import { useEffect, useState, type FormEvent } from 'react'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import type { ConnectorField, ConnectorInfo, ConnectorType } from '../../types/governance'
import { useGovAuth } from '../authState'
import { ErrorPanel, Field, Loading, PageHeader } from '../ui'
import { formatAgo, formatTime, useL10n, useLoad } from '../hooks'
import { RunStatus } from './OverviewPage'

export default function ConnectorsPage() {
  const { t } = useTranslation()
  const { can } = useGovAuth()
  const types = useLoad(() => govApi.connectorTypes(), [])
  const list = useLoad(() => govApi.connectors(), [])
  const [editing, setEditing] = useState<ConnectorInfo | 'new' | null>(null)
  const [selected, setSelected] = useState<number | null>(null)

  // Poll while something is queued or running so the status settles without a manual refresh.
  const busy = list.data?.some(c => c.running || c.run_requested)
  useEffect(() => {
    if (!busy) return
    const id = setInterval(list.reload, 5000)
    return () => clearInterval(id)
  }, [busy, list.reload])

  if ((types.loading && !types.data) || (list.loading && !list.data)) return <Loading />
  if (types.error || list.error) return <ErrorPanel message={types.error || list.error} onRetry={() => { types.reload(); list.reload() }} />
  if (!types.data || !list.data) return null

  return (
    <div className="space-y-5">
      <PageHeader title={t('gov.conn.title')} subtitle={t('gov.conn.subtitle')}
        actions={can('admin') && <button className="btn-primary" onClick={() => setEditing('new')}>{t('gov.conn.add')}</button>} />

      {editing && (
        <ConnectorForm types={types.data} existing={editing === 'new' ? null : editing}
          onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload() }} />
      )}

      {list.data.length === 0 && !editing && <div className="panel text-sm text-cyber-muted">{t('gov.conn.none')}</div>}
      <ul className="space-y-3">
        {list.data.map(c => (
          <ConnectorCard key={c.id} connector={c} type={types.data!.find(x => x.kind === c.kind)!}
            expanded={selected === c.id} onToggle={() => setSelected(selected === c.id ? null : c.id)}
            onEdit={() => setEditing(c)} onChanged={list.reload} />
        ))}
      </ul>
    </div>
  )
}

function ConnectorCard({ connector: c, type, expanded, onToggle, onEdit, onChanged }: {
  connector: ConnectorInfo; type: ConnectorType; expanded: boolean; onToggle: () => void; onEdit: () => void; onChanged: () => void
}) {
  const { t, lang } = useTranslation()
  const { can } = useGovAuth()
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const detail = useLoad(() => (expanded ? govApi.connector(c.id) : Promise.resolve(null)), [expanded, c.id, c.last_run_at])

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true); setMessage(null)
    try {
      const res = await fn()
      if (res && typeof res === 'object' && 'ok' in res) {
        const r = res as { ok: boolean; message: string }
        setMessage({ ok: r.ok, text: r.message })
      } else if (ok) setMessage({ ok: true, text: ok })
      onChanged()
    } catch (e) { setMessage({ ok: false, text: errorMessage(e, t) }) } finally { setBusy(false) }
  }
  const remove = () => {
    if (window.confirm(t('gov.conn.confirmDelete', { name: c.name }))) act(() => govApi.deleteConnector(c.id))
  }
  const status = !c.enabled ? 'disabled' : c.running ? 'running' : c.run_requested ? 'queued' : c.last_status

  return (
    <li className="panel-sm space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <button onClick={onToggle} aria-expanded={expanded} className="text-left min-w-0">
          <p className="text-[15px] font-semibold text-cyber-text">{c.name}</p>
          <p className="text-xs text-cyber-muted mt-0.5">
            {t(`gov.kind.${c.kind}`)} · {t('gov.conn.every', { n: c.schedule_minutes })} · {t('gov.conn.last', { ago: formatAgo(c.last_run_at, t) })}
          </p>
        </button>
        <div className="flex items-center gap-2 flex-wrap">
          <RunStatus status={status} />
          {can('admin') && <>
            <button disabled={busy} className="btn-ghost text-sm px-3 py-1.5" onClick={() => act(() => govApi.testConnector(c.id))}>{t('gov.conn.test')}</button>
            <button disabled={busy || c.running || c.run_requested || !c.enabled} className="btn-ghost text-sm px-3 py-1.5"
              onClick={() => act(() => govApi.runConnector(c.id), t('gov.conn.queued'))}>{t('gov.conn.runNow')}</button>
            <button className="btn-ghost text-sm px-3 py-1.5" onClick={onEdit}>{t('gov.edit')}</button>
            <button className="btn-ghost text-sm px-3 py-1.5 text-cyber-danger" onClick={remove}>{t('gov.delete')}</button>
          </>}
        </div>
      </div>
      {message && <p className={`text-sm ${message.ok ? 'text-cyber-safe' : 'text-cyber-danger'}`} role="status">{message.text}</p>}
      {c.last_error && <p className="text-sm text-cyber-warning break-words">{c.last_error}</p>}
      {expanded && detail.data?.runs && (
        <div className="border-t border-cyber-border/40 pt-3 space-y-2">
          <p className="text-xs text-cyber-muted uppercase tracking-wider">{t('gov.conn.runs')}</p>
          {detail.data.runs.length === 0 && <p className="text-sm text-cyber-muted">{t('gov.conn.noRuns')}</p>}
          <ul className="space-y-2">
            {detail.data.runs.slice(0, 8).map(r => (
              <li key={r.id} className="text-sm">
                <div className="flex items-center gap-3 flex-wrap">
                  <RunStatus status={r.status} />
                  <span className="text-cyber-muted">{formatTime(r.started_at, lang)}</span>
                  {r.stats?.checks !== undefined && (
                    <span className="text-xs text-cyber-muted">{t('gov.conn.stats', {
                      checks: r.stats.checks, events: r.stats.new_events ?? 0, alerts: r.stats.alerts ?? 0 })}</span>
                  )}
                </div>
                {Object.keys(r.unavailable ?? {}).length > 0 && (
                  <details className="mt-1 ml-1">
                    <summary className="text-xs text-cyber-muted cursor-pointer">
                      {t('gov.conn.unavailable', { n: Object.keys(r.unavailable).length })}
                    </summary>
                    <ul className="mt-1 space-y-0.5">
                      {Object.entries(r.unavailable).map(([k, v]) => (
                        <li key={k} className="text-xs text-cyber-muted"><span className="font-mono text-cyber-text">{k}</span>: {v}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {r.error && <p className="text-xs text-cyber-warning mt-1 break-words">{r.error}</p>}
              </li>
            ))}
          </ul>
          <p className="text-xs text-cyber-muted">{t('gov.conn.provides', { checks: type.checks.length, rules: type.rules.length })}</p>
        </div>
      )}
    </li>
  )
}

function ConnectorForm({ types, existing, onCancel, onSaved }: {
  types: ConnectorType[]; existing: ConnectorInfo | null; onCancel: () => void; onSaved: () => void
}) {
  const { t } = useTranslation()
  const l = useL10n()
  const [kind, setKind] = useState(existing?.kind ?? types[0].kind)
  const type = types.find(x => x.kind === kind)!
  const [name, setName] = useState(existing?.name ?? '')
  const [schedule, setSchedule] = useState(existing?.schedule_minutes ?? 360)
  const [enabled, setEnabled] = useState(existing?.enabled ?? true)
  const [values, setValues] = useState<Record<string, unknown>>(() => initial(type, existing))
  const [tuning, setTuning] = useState(() => {
    const cfg = existing?.config ?? {}
    const extra = { thresholds: cfg.thresholds, rules: cfg.rules }
    return extra.thresholds || extra.rules ? JSON.stringify(extra, null, 2) : ''
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    let extra = {}
    if (tuning.trim()) {
      try { extra = JSON.parse(tuning) } catch { setError(t('gov.conn.badJson')); setBusy(false); return }
    }
    const config: Record<string, unknown> = { ...extra }
    const secrets: Record<string, string> = {}
    for (const f of type.fields) {
      if (f.type === 'secret') secrets[f.name] = String(values[f.name] ?? '')
      else config[f.name] = values[f.name]
    }
    const body = { kind, name, config, secrets, enabled, schedule_minutes: Number(schedule) }
    try {
      if (existing) await govApi.updateConnector(existing.id, body)
      else await govApi.createConnector(body)
      onSaved()
    } catch (err) { setError(errorMessage(err, t)) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="panel space-y-5" aria-labelledby="conn-form-title">
      <h2 id="conn-form-title" className="text-lg font-semibold text-cyber-text">
        {existing ? t('gov.conn.editTitle', { name: existing.name }) : t('gov.conn.addTitle')}
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Field label={t('gov.conn.kind')} htmlFor="cf-kind">
          <select id="cf-kind" value={kind} disabled={!!existing} className="gov-select w-full py-3" onChange={e => {
            setKind(e.target.value)
            setValues(initial(types.find(x => x.kind === e.target.value)!, null))
          }}>
            {types.map(x => <option key={x.kind} value={x.kind}>{l(x.title)}</option>)}
          </select>
        </Field>
        <Field label={t('gov.conn.name')} htmlFor="cf-name">
          <input id="cf-name" required value={name} onChange={e => setName(e.target.value)} className="input-field py-2.5" />
        </Field>
        <Field label={t('gov.conn.schedule')} hint={t('gov.conn.scheduleHint')} htmlFor="cf-schedule">
          <input id="cf-schedule" type="number" min={15} step={15} value={schedule} onChange={e => setSchedule(Number(e.target.value))}
            className="input-field py-2.5" />
        </Field>
      </div>

      <div className="rounded-lg border border-cyber-accent/20 bg-cyber-accent/[0.04] px-4 py-3">
        <p className="text-sm font-medium text-cyber-text">{t('gov.conn.permissions')}</p>
        <p className="text-sm text-cyber-muted mt-1 leading-relaxed break-words">{l(type.permissions_help)}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {type.fields.map(f => (
          <FieldInput key={f.name} field={f} value={values[f.name]} isSet={!!existing?.secrets_set.includes(f.name)}
            onChange={v => setValues(prev => ({ ...prev, [f.name]: v }))} />
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-cyber-text">
        <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />{t('gov.conn.enabled')}
      </label>

      <details>
        <summary className="text-sm text-cyber-muted cursor-pointer">{t('gov.conn.tuning')}</summary>
        <div className="mt-2 space-y-2">
          <p className="text-xs text-cyber-muted leading-relaxed">{t('gov.conn.tuningHelp')}</p>
          <ul className="text-xs text-cyber-muted space-y-0.5">
            {type.rules.map(r => (
              <li key={r.id}><span className="font-mono text-cyber-text">{r.id}</span> — {l(r.title)}
                {Object.keys(r.defaults).length > 0 && <span className="font-mono"> {JSON.stringify(r.defaults)}</span>}</li>
            ))}
          </ul>
          <label htmlFor="cf-tuning" className="sr-only">{t('gov.conn.tuning')}</label>
          <textarea id="cf-tuning" value={tuning} onChange={e => setTuning(e.target.value)} spellCheck={false}
            placeholder={'{\n  "thresholds": {"m365.secure_score": {"pass_at": 75}},\n  "rules": {"github.bulk_download": {"actor_allowlist": ["ci-bot"]}}\n}'}
            className="input-field h-32 font-mono text-xs resize-y" />
        </div>
      </details>

      {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="btn-ghost">{t('gov.cancel')}</button>
        <button type="submit" disabled={busy || !name.trim()} className="btn-primary">{busy ? t('gov.saving') : t('gov.save')}</button>
      </div>
    </form>
  )
}

function initial(type: ConnectorType, existing: ConnectorInfo | null): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of type.fields) {
    if (f.type === 'secret') out[f.name] = ''
    else out[f.name] = existing?.config[f.name] ?? f.default ?? (f.type === 'bool' ? false : '')
  }
  return out
}

function FieldInput({ field: f, value, isSet, onChange }: {
  field: ConnectorField; value: unknown; isSet: boolean; onChange: (v: unknown) => void
}) {
  const { t } = useTranslation()
  const l = useL10n()
  const id = `cf-${f.name}`
  const label = l(f.label) + (f.required ? ' *' : '')
  if (f.type === 'bool') {
    return (
      <div className="space-y-1">
        <label className="flex items-center gap-2 text-sm text-cyber-text">
          <input id={id} type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} />{l(f.label)}
        </label>
        {f.help && <p className="text-xs text-cyber-muted">{l(f.help)}</p>}
      </div>
    )
  }
  if (f.type === 'secret') {
    const multiline = f.name.includes('dsns')
    const common = {
      id, value: String(value ?? ''), autoComplete: 'off', spellCheck: false,
      placeholder: isSet ? t('gov.conn.secretSet') : '',
      onChange: (e: { target: { value: string } }) => onChange(e.target.value),
    }
    return (
      <Field label={label} hint={(f.help ? l(f.help) + ' ' : '') + t('gov.conn.secretHint')} htmlFor={id}>
        {multiline
          ? <textarea {...common} className="input-field h-24 font-mono text-xs resize-y" />
          : <input {...common} type="password" className="input-field py-2.5" required={f.required && !isSet} />}
      </Field>
    )
  }
  const text = Array.isArray(value) ? value.join(', ') : String(value ?? '')
  return (
    <Field label={label} hint={f.help ? l(f.help) : f.type === 'list' ? t('gov.conn.listHint') : null} htmlFor={id}>
      <input id={id} value={text} type={f.type === 'int' ? 'number' : 'text'} required={f.required}
        onChange={e => onChange(f.type === 'int' ? Number(e.target.value) : e.target.value)} className="input-field py-2.5" />
    </Field>
  )
}
