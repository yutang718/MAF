import { useState, type FormEvent } from 'react'
import { govApi } from '../../api/governance'
import { errorMessage } from '../../api/client'
import { Tabs, TabPanel } from '../../components/Tabs'
import { useTranslation } from '../../i18n/context'
import type { Role } from '../../types/governance'
import { useGovAuth } from '../authState'
import { ErrorPanel, Field, Loading, PageHeader } from '../ui'
import { formatTime, useLoad } from '../hooks'

const ROLES: Role[] = ['viewer', 'auditor', 'admin']

export default function AdminPage() {
  const { t } = useTranslation()
  const { can } = useGovAuth()
  const [tab, setTab] = useState(0)
  const labels = [t('gov.admin.auditLog'), t('gov.admin.account'), ...(can('admin') ? [t('gov.admin.users')] : [])]
  return (
    <div className="space-y-5">
      <PageHeader title={t('gov.admin.title')} subtitle={t('gov.admin.subtitle')} />
      <Tabs id="gov-admin" labels={labels} active={tab} onChange={setTab} className="w-fit" />
      <TabPanel id="gov-admin" index={0} active={tab}><AuditLog /></TabPanel>
      <TabPanel id="gov-admin" index={1} active={tab}><Account /></TabPanel>
      {can('admin') && <TabPanel id="gov-admin" index={2} active={tab}><Users /></TabPanel>}
    </div>
  )
}

function AuditLog() {
  const { t, lang } = useTranslation()
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const { data, error, loading, reload } = useLoad(() => govApi.auditLog({ offset, limit: 100, action: action || undefined }), [offset, action])
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <label htmlFor="audit-filter" className="sr-only">{t('gov.admin.filterAction')}</label>
        <select id="audit-filter" value={action} onChange={e => { setAction(e.target.value); setOffset(0) }} className="gov-select">
          <option value="">{t('gov.admin.allActions')}</option>
          {['login', 'connector', 'evidence', 'exception', 'alert', 'control', 'user', 'report'].map(a => <option key={a} value={a}>{a}.*</option>)}
        </select>
        <p className="text-xs text-cyber-muted">{t('gov.admin.auditHelp')}</p>
      </div>
      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && (
        <div className="panel-sm p-0 overflow-x-auto">
          <table className="w-full">
            <thead><tr>
              <th className="table-header">{t('gov.admin.when')}</th><th className="table-header">{t('gov.admin.who')}</th>
              <th className="table-header">{t('gov.admin.action')}</th><th className="table-header">{t('gov.admin.target')}</th>
              <th className="table-header">IP</th>
            </tr></thead>
            <tbody>
              {data.items.map(e => (
                <tr key={e.id} className="table-row-hover align-top">
                  <td className="table-cell text-sm whitespace-nowrap">{formatTime(e.at, lang)}</td>
                  <td className="table-cell text-sm">{e.user || '—'}</td>
                  <td className="table-cell text-sm font-mono">{e.action}</td>
                  <td className="table-cell text-xs font-mono break-all">
                    {e.target_type}{e.target_id && ` #${e.target_id}`}
                    {Object.keys(e.detail).length > 0 && <div className="text-cyber-muted mt-0.5">{JSON.stringify(e.detail)}</div>}
                  </td>
                  <td className="table-cell text-xs font-mono">{e.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-3 text-sm text-cyber-muted border-t border-cyber-border/40">
            <span>{t('gov.alerts.range', { from: data.total ? offset + 1 : 0, to: Math.min(offset + 100, data.total), total: data.total })}</span>
            <span className="flex gap-2">
              <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>{t('gov.prev')}</button>
              <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset + 100 >= data.total} onClick={() => setOffset(offset + 100)}>{t('gov.next')}</button>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function Account() {
  const { t } = useTranslation()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await govApi.changePassword(current, next)
      setCurrent(''); setNext('')
      setMsg({ ok: true, text: t('gov.admin.passwordChanged') })
    } catch (err) { setMsg({ ok: false, text: errorMessage(err, t) }) }
  }
  return (
    <form onSubmit={submit} className="panel-sm max-w-md space-y-4">
      <Field label={t('gov.admin.currentPassword')} htmlFor="pw-cur">
        <input id="pw-cur" type="password" autoComplete="current-password" required value={current} onChange={e => setCurrent(e.target.value)} className="input-field py-2.5" />
      </Field>
      <Field label={t('gov.admin.newPassword')} hint={t('gov.admin.passwordRule')} htmlFor="pw-new">
        <input id="pw-new" type="password" autoComplete="new-password" required minLength={12} value={next} onChange={e => setNext(e.target.value)} className="input-field py-2.5" />
      </Field>
      {msg && <p className={`text-sm ${msg.ok ? 'text-cyber-safe' : 'text-cyber-danger'}`} role="status">{msg.text}</p>}
      <button type="submit" className="btn-primary">{t('gov.admin.changePassword')}</button>
    </form>
  )
}

function Users() {
  const { t, lang } = useTranslation()
  const { user: me } = useGovAuth()
  const { data, error, loading, reload } = useLoad(() => govApi.users(), [])
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setMsg('')
    try {
      await govApi.createUser({ email, name, role, password })
      setEmail(''); setName(''); setPassword(''); setRole('viewer')
      reload()
    } catch (err) { setMsg(errorMessage(err, t)) }
  }
  const update = async (id: number, body: Parameters<typeof govApi.updateUser>[1]) => {
    setMsg('')
    try { await govApi.updateUser(id, body); reload() } catch (err) { setMsg(errorMessage(err, t)) }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-cyber-muted max-w-3xl leading-relaxed">{t('gov.admin.rolesHelp')}</p>
      {msg && <ErrorPanel message={msg} />}
      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && (
        <div className="panel-sm p-0 overflow-x-auto">
          <table className="w-full">
            <thead><tr>
              <th className="table-header">{t('gov.signIn.email')}</th><th className="table-header">{t('gov.admin.role')}</th>
              <th className="table-header">{t('gov.admin.lastLogin')}</th><th className="table-header">{t('gov.admin.state')}</th>
            </tr></thead>
            <tbody>
              {data.map(u => (
                <tr key={u.id} className="table-row-hover">
                  <td className="table-cell text-sm">{u.email}{u.name && <span className="text-cyber-muted"> · {u.name}</span>}</td>
                  <td className="table-cell">
                    <label className="sr-only" htmlFor={`role-${u.id}`}>{t('gov.admin.role')}</label>
                    <select id={`role-${u.id}`} value={u.role} disabled={u.id === me?.id}
                      onChange={e => update(u.id, { role: e.target.value as Role })} className="gov-select">
                      {ROLES.map(r => <option key={r} value={r}>{t(`gov.role.${r}`)}</option>)}
                    </select>
                  </td>
                  <td className="table-cell text-sm">{formatTime(u.last_login_at, lang)}</td>
                  <td className="table-cell">
                    <button disabled={u.id === me?.id} onClick={() => update(u.id, { active: !u.active })} className="btn-ghost text-sm px-3 py-1.5">
                      {u.active ? t('gov.admin.deactivate') : t('gov.admin.activate')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form onSubmit={create} className="panel-sm space-y-4" aria-labelledby="new-user-title">
        <h3 id="new-user-title" className="text-sm font-semibold text-cyber-text">{t('gov.admin.addUser')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Field label={t('gov.signIn.email')} htmlFor="nu-email">
            <input id="nu-email" type="email" required value={email} onChange={e => setEmail(e.target.value)} className="input-field py-2.5" />
          </Field>
          <Field label={t('gov.admin.name')} htmlFor="nu-name">
            <input id="nu-name" value={name} onChange={e => setName(e.target.value)} className="input-field py-2.5" />
          </Field>
          <Field label={t('gov.admin.role')} htmlFor="nu-role">
            <select id="nu-role" value={role} onChange={e => setRole(e.target.value as Role)} className="gov-select w-full py-3">
              {ROLES.map(r => <option key={r} value={r}>{t(`gov.role.${r}`)}</option>)}
            </select>
          </Field>
          <Field label={t('gov.admin.initialPassword')} hint={t('gov.admin.passwordRule')} htmlFor="nu-pw">
            <input id="nu-pw" type="password" autoComplete="new-password" required minLength={12} value={password}
              onChange={e => setPassword(e.target.value)} className="input-field py-2.5" />
          </Field>
        </div>
        <button type="submit" className="btn-primary">{t('gov.admin.create')}</button>
      </form>
    </div>
  )
}
