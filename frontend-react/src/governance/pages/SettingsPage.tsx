import { useState, type FormEvent } from 'react'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { useTranslation } from '../../i18n/context'
import type { NotifySettings } from '../../types/governance'
import { formatTime, useLoad } from '../hooks'
import { ErrorPanel, Field, Loading, PageHeader } from '../ui'

const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7]
const SLA_KEYS = ['exploited', 'critical', 'high', 'medium', 'low'] as const

export default function SettingsPage() {
  const { t } = useTranslation()
  return (
    <div className="space-y-6">
      <PageHeader title={t('gov.settings.title')} subtitle={t('gov.settings.subtitle')} />
      <NotifyForm />
      <SlaForm />
    </div>
  )
}

function NotifyForm() {
  const { t, lang } = useTranslation()
  const { data, error, loading, reload, setData } = useLoad(() => govApi.notifySettings(), [])
  const [webhook, setWebhook] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  if (loading && !data) return <Loading />
  if (error) return <ErrorPanel message={error} onRetry={reload} />
  if (!data) return null
  const set = (patch: Partial<NotifySettings>) => setData(d => d && { ...d, ...patch })

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setMsg(null)
    try {
      const { enabled, weekday, hour, timezone, base_url, realtime_critical } = data
      const saved = await govApi.saveNotify({ enabled, weekday, hour, timezone, base_url, realtime_critical,
        ...(webhook ? { teams_webhook: webhook } : {}) })
      setData(() => saved)
      setWebhook('')
      setMsg({ ok: true, text: t('gov.settings.saved') })
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err, t) })
      reload()
    } finally { setBusy(false) }
  }
  const test = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await govApi.testNotify()
      setMsg({ ok: r.ok, text: r.ok ? t('gov.settings.testSent') : r.message })
    } catch (err) { setMsg({ ok: false, text: errorMessage(err, t) }) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={save} className="panel space-y-5" aria-labelledby="notify-title">
      <div>
        <h2 id="notify-title" className="text-[15px] font-semibold text-cyber-text">{t('gov.settings.teams')}</h2>
        <p className="text-sm text-cyber-muted mt-1 leading-relaxed max-w-3xl">{t('gov.settings.teamsHelp')}</p>
      </div>
      <Field label={t('gov.settings.webhook')} hint={t('gov.settings.webhookHint')} htmlFor="ns-webhook">
        <input id="ns-webhook" type="password" autoComplete="off" value={webhook} onChange={e => setWebhook(e.target.value)}
          placeholder={data.webhook_set ? t('gov.conn.secretSet') : 'https://…'} className="input-field py-2.5" />
      </Field>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Field label={t('gov.settings.weekday')} htmlFor="ns-day">
          <select id="ns-day" value={data.weekday} onChange={e => set({ weekday: Number(e.target.value) })} className="gov-select w-full py-3">
            {WEEKDAYS.map(d => <option key={d} value={d}>{t(`gov.settings.day.${d}`)}</option>)}
          </select>
        </Field>
        <Field label={t('gov.settings.hour')} htmlFor="ns-hour">
          <input id="ns-hour" type="number" min={0} max={23} value={data.hour} onChange={e => set({ hour: Number(e.target.value) })}
            className="input-field py-2.5" />
        </Field>
        <Field label={t('gov.settings.timezone')} htmlFor="ns-tz">
          <input id="ns-tz" value={data.timezone} onChange={e => set({ timezone: e.target.value })} className="input-field py-2.5" />
        </Field>
        <Field label={t('gov.settings.baseUrl')} hint={t('gov.settings.baseUrlHint')} htmlFor="ns-base">
          <input id="ns-base" value={data.base_url} onChange={e => set({ base_url: e.target.value })}
            placeholder="https://maf.example.com" className="input-field py-2.5" />
        </Field>
      </div>
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-cyber-text">
          <input type="checkbox" checked={data.enabled} onChange={e => set({ enabled: e.target.checked })} />
          {t('gov.settings.weeklyOn')}
        </label>
        <label className="flex items-center gap-2 text-sm text-cyber-text">
          <input type="checkbox" checked={data.realtime_critical} onChange={e => set({ realtime_critical: e.target.checked })} />
          {t('gov.settings.realtimeOn')}
        </label>
      </div>
      <p className="text-xs text-cyber-muted">
        {data.state.last_sent_at ? t('gov.settings.lastSent', { time: formatTime(data.state.last_sent_at, lang) }) : t('gov.settings.neverSent')}
        {data.state.last_error && <span className="text-cyber-warning"> · {data.state.last_error}</span>}
      </p>
      {msg && <p className={`text-sm ${msg.ok ? 'text-cyber-safe' : 'text-cyber-danger'}`} role="status">{msg.text}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">{t('gov.save')}</button>
        <button type="button" disabled={busy || !data.webhook_set} onClick={test} className="btn-ghost">{t('gov.settings.sendTest')}</button>
      </div>
    </form>
  )
}

function SlaForm() {
  const { t } = useTranslation()
  const { data, error, reload, setData } = useLoad(() => govApi.slaSettings(), [])
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  if (error) return <ErrorPanel message={error} onRetry={reload} />
  if (!data) return null
  const save = async (e: FormEvent) => {
    e.preventDefault()
    setMsg(null)
    try {
      const saved = await govApi.saveSla(data)
      setData(() => saved)
      setMsg({ ok: true, text: t('gov.settings.saved') })
    } catch (err) { setMsg({ ok: false, text: errorMessage(err, t) }) }
  }
  return (
    <form onSubmit={save} className="panel space-y-5" aria-labelledby="sla-title">
      <div>
        <h2 id="sla-title" className="text-[15px] font-semibold text-cyber-text">{t('gov.settings.sla')}</h2>
        <p className="text-sm text-cyber-muted mt-1 leading-relaxed max-w-3xl">{t('gov.settings.slaHelp')}</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {SLA_KEYS.map(k => (
          <Field key={k} label={t(`gov.posture.sla.${k}`)} htmlFor={`sla-${k}`}>
            <input id={`sla-${k}`} type="number" min={1} max={365} value={data[k]}
              onChange={e => setData(d => d && { ...d, [k]: Number(e.target.value) })} className="input-field py-2.5" />
          </Field>
        ))}
      </div>
      {msg && <p className={`text-sm ${msg.ok ? 'text-cyber-safe' : 'text-cyber-danger'}`} role="status">{msg.text}</p>}
      <button type="submit" className="btn-primary">{t('gov.save')}</button>
    </form>
  )
}
