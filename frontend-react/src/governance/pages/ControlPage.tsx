import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import type { CheckResult } from '../../types/governance'
import { useGovAuth } from '../authState'
import { CheckStatusBadge, ControlStatusBadge, ErrorPanel, Field, ItemRow, Loading, SeverityBadge } from '../ui'
import { formatTime, useL10n, useLoad } from '../hooks'

export default function ControlPage() {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const { can } = useGovAuth()
  const { fw = '', cid = '' } = useParams()
  const { data, error, loading, reload } = useLoad(() => govApi.control(fw, cid), [fw, cid])

  if (loading && !data) return <Loading />
  if (error) return <ErrorPanel message={error} onRetry={reload} />
  if (!data) return null

  return (
    <div className="space-y-5">
      <nav aria-label={t('gov.breadcrumb')} className="text-sm text-cyber-muted">
        <Link to={`/governance/frameworks/${fw}`} className="hover:text-cyber-accent">{t(`gov.fw.name.${fw}`)}</Link>
        <span aria-hidden="true"> / </span><span>{l(data.group_name)}</span>
      </nav>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="font-mono text-sm text-cyber-muted">{data.id}</p>
          <h1 className="text-xl font-semibold text-cyber-text mt-0.5">{l(data.title)}</h1>
        </div>
        <ControlStatusBadge status={data.status} />
      </div>
      <p className="text-sm text-cyber-muted leading-relaxed max-w-3xl">{t(`gov.cstatus.help.${data.status}`)}</p>

      <section className="space-y-3" aria-labelledby="ctl-auto">
        <h2 id="ctl-auto" className="text-[15px] font-semibold text-cyber-text">{t('gov.ctl.automated')}</h2>
        {data.results.length === 0 && data.uncovered_checks.length === 0 && (
          <p className="text-sm text-cyber-muted">{t('gov.ctl.noAutomation')}</p>
        )}
        {data.results.map(r => <ResultCard key={r.id} result={r} />)}
        {data.uncovered_checks.length > 0 && (
          <div className="panel-sm">
            <p className="text-sm text-cyber-text font-medium">{t('gov.ctl.uncovered')}</p>
            <ul className="mt-2 space-y-1">
              {data.uncovered_checks.map(c => (
                <li key={c.id} className="text-sm text-cyber-muted flex gap-2">
                  <span className="badge-info gov-badge">{t(`gov.kind.${c.kind ?? 'unknown'}`)}</span>{l(c.title)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <EvidenceSection fw={fw} cid={cid} items={data.evidence} onChange={reload} canUpload={can('auditor')}
        canDelete={can('admin')} lang={lang} />

      {Object.keys(data.related).length > 0 && (
        <section className="panel-sm space-y-2" aria-labelledby="ctl-related">
          <h2 id="ctl-related" className="text-[15px] font-semibold text-cyber-text">{t('gov.ctl.related')}</h2>
          <p className="text-xs text-cyber-muted">{t('gov.ctl.relatedHelp')}</p>
          {Object.entries(data.related).map(([other, ids]) => (
            <div key={other} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-cyber-muted w-40">{t(`gov.fw.name.${other}`)}</span>
              {ids.map(id => (
                <Link key={id} to={`/governance/frameworks/${other}/controls/${encodeURIComponent(id)}`}
                  className="font-mono text-xs px-2 py-0.5 rounded border border-cyber-border/60 hover:border-cyber-accent/50 hover:text-cyber-accent">
                  {id}
                </Link>
              ))}
            </div>
          ))}
        </section>
      )}

      {can('admin') && <Applicability fw={fw} cid={cid} reason={data.not_applicable_reason} onChange={reload} />}
      {!can('admin') && data.not_applicable_reason && (
        <p className="text-sm text-cyber-muted">{t('gov.ctl.naReason')}: {data.not_applicable_reason}</p>
      )}
    </div>
  )
}

export function ResultCard({ result }: { result: CheckResult }) {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const [open, setOpen] = useState(false)
  const items = result.items ?? []
  const missing = (result.params?.missing ?? null) as Record<string, string> | null
  return (
    <div className="panel-sm space-y-2">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <p className="text-[15px] text-cyber-text font-medium">{l(result.check.title)}</p>
          <p className="text-xs text-cyber-muted mt-0.5">
            {result.connector_name} · {t('gov.ctl.evaluated', { time: formatTime(result.evaluated_at, lang) })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {result.check.severity && <SeverityBadge severity={result.check.severity} />}
          <CheckStatusBadge status={result.status} />
        </div>
      </div>
      {result.summary && <p className="text-sm text-cyber-text/90">{l(result.summary)}</p>}
      {missing && (
        <ul className="text-sm text-cyber-muted space-y-0.5">
          {Object.entries(missing).map(([k, why]) => <li key={k}><span className="font-mono">{k}</span>: {why}</li>)}
        </ul>
      )}
      {result.status === 'error' && typeof result.params?.error === 'string' && (
        <p className="text-sm text-cyber-danger">{String(result.params.error)}</p>
      )}
      {['fail', 'partial', 'accepted'].includes(result.status) && result.check.remediation && (
        <p className="text-sm text-cyber-muted"><span className="text-cyber-text">{t('gov.ctl.fix')}:</span> {l(result.check.remediation)}</p>
      )}
      {result.status === 'accepted' && <p className="text-sm text-cyber-accent">{t('gov.ctl.accepted')}</p>}
      {items.length > 0 && (
        <div>
          <button onClick={() => setOpen(!open)} aria-expanded={open} className="text-sm text-cyber-accent hover:underline">
            {open ? t('gov.ctl.hideItems') : t('gov.ctl.showItems', { n: items.length })}
          </button>
          {open && <ul className="mt-2 max-h-80 overflow-y-auto pr-2">{items.map((it, i) => <ItemRow key={i} item={it} />)}</ul>}
        </div>
      )}
    </div>
  )
}

function EvidenceSection({ fw, cid, items, onChange, canUpload, canDelete, lang }: {
  fw: string; cid: string; items: import('../../types/governance').EvidenceItem[]; onChange: () => void
  canUpload: boolean; canDelete: boolean; lang: string
}) {
  const { t } = useTranslation()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [formKey, setFormKey] = useState(0)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const form = new FormData()
    form.set('framework', fw)
    form.set('control_id', cid)
    form.set('title', title)
    form.set('description', description)
    form.set('valid_until', validUntil)
    if (file) form.set('file', file)
    try {
      await govApi.uploadEvidence(form)
      setTitle(''); setDescription(''); setValidUntil(''); setFile(null); setFormKey(k => k + 1)
      onChange()
    } catch (err) {
      setError(errorMessage(err, t))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number) => {
    if (!window.confirm(t('gov.ev.confirmDelete'))) return
    try { await govApi.deleteEvidence(id); onChange() } catch (err) { setError(errorMessage(err, t)) }
  }

  return (
    <section className="space-y-3" aria-labelledby="ctl-evidence">
      <h2 id="ctl-evidence" className="text-[15px] font-semibold text-cyber-text">{t('gov.ev.title')}</h2>
      {items.length === 0 ? <p className="text-sm text-cyber-muted">{t('gov.ev.none')}</p> : (
        <ul className="panel-sm p-0 divide-y divide-cyber-border/40">
          {items.map(e => (
            <li key={e.id} className="px-5 py-3 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm text-cyber-text font-medium">{e.title}</p>
                {e.description && <p className="text-sm text-cyber-muted mt-0.5">{e.description}</p>}
                <p className="text-xs text-cyber-muted mt-1">
                  {e.uploaded_by} · {formatTime(e.created_at, lang)}
                  {e.valid_until && <> · <span className={e.expired ? 'text-cyber-warning' : ''}>
                    {t(e.expired ? 'gov.ev.expired' : 'gov.ev.validUntil', { date: e.valid_until })}</span></>}
                  {e.sha256 && <> · <span className="font-mono" title={e.sha256}>sha256 {e.sha256.slice(0, 12)}…</span></>}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {e.file_name && canUpload && (
                  <a href={govApi.evidenceFileUrl(e.id)} className="btn-ghost text-sm px-3 py-1.5">{t('gov.ev.download')}</a>
                )}
                {canDelete && <button onClick={() => remove(e.id)} className="btn-ghost text-sm px-3 py-1.5 text-cyber-danger">{t('gov.delete')}</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {canUpload && (
        <form key={formKey} onSubmit={submit} className="panel-sm space-y-4" aria-labelledby="ev-form-title">
          <h3 id="ev-form-title" className="text-sm font-semibold text-cyber-text">{t('gov.ev.add')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('gov.ev.fTitle')} htmlFor="ev-title">
              <input id="ev-title" required value={title} onChange={e => setTitle(e.target.value)} className="input-field py-2" />
            </Field>
            <Field label={t('gov.ev.fValid')} hint={t('gov.ev.fValidHint')} htmlFor="ev-valid">
              <input id="ev-valid" type="date" value={validUntil} onChange={e => setValidUntil(e.target.value)} className="input-field py-2" />
            </Field>
          </div>
          <Field label={t('gov.ev.fDesc')} htmlFor="ev-desc">
            <textarea id="ev-desc" value={description} onChange={e => setDescription(e.target.value)} className="input-field h-20 resize-none" />
          </Field>
          <Field label={t('gov.ev.fFile')} hint={t('gov.ev.fFileHint')} htmlFor="ev-file">
            <input id="ev-file" type="file" onChange={e => setFile(e.target.files?.[0] ?? null)}
              className="block text-sm text-cyber-muted file:mr-3 file:btn-ghost file:px-3 file:py-1.5" />
          </Field>
          {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
          <button type="submit" disabled={busy || !title.trim()} className="btn-primary">{busy ? t('gov.saving') : t('gov.ev.submit')}</button>
        </form>
      )}
    </section>
  )
}

function Applicability({ fw, cid, reason, onChange }: { fw: string; cid: string; reason: string | null; onChange: () => void }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await fn(); setText(''); onChange() } catch (e) { setError(errorMessage(e, t)) } finally { setBusy(false) }
  }
  return (
    <section className="panel-sm space-y-3" aria-labelledby="ctl-na">
      <h2 id="ctl-na" className="text-[15px] font-semibold text-cyber-text">{t('gov.ctl.applicability')}</h2>
      {reason ? (
        <div className="flex items-start justify-between gap-4">
          <p className="text-sm text-cyber-muted">{t('gov.ctl.naReason')}: <span className="text-cyber-text">{reason}</span></p>
          <button disabled={busy} onClick={() => act(() => govApi.setApplicable(fw, cid))} className="btn-ghost text-sm px-3 py-1.5">
            {t('gov.ctl.markApplicable')}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-cyber-muted">{t('gov.ctl.naHelp')}</p>
          <label htmlFor="na-reason" className="sr-only">{t('gov.ctl.naReason')}</label>
          <textarea id="na-reason" value={text} onChange={e => setText(e.target.value)} className="input-field h-16 resize-none"
            placeholder={t('gov.ctl.naPlaceholder')} />
          <button disabled={busy || text.trim().length < 10} onClick={() => act(() => govApi.setNotApplicable(fw, cid, text))}
            className="btn-ghost text-sm px-3 py-1.5">{t('gov.ctl.markNa')}</button>
        </div>
      )}
      {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
    </section>
  )
}
