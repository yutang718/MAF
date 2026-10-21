import { useState, type FormEvent } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useTranslation } from '../i18n/context'
import { useGovAuth } from './authState'
import { Field } from './ui'

export default function GovernanceLayout() {
  const { t } = useTranslation()
  const { user, checking, unreachable, signOut, can } = useGovAuth()

  if (checking) return <div className="panel text-sm text-cyber-muted" role="status">{t('gov.loading')}</div>
  if (unreachable) return <Unreachable code={unreachable} />
  if (!user) return <SignIn />

  const links = [
    { to: '/governance', label: t('gov.nav.posture'), end: true },
    { to: '/governance/alerts', label: t('gov.nav.alerts') },
    { to: '/governance/exceptions', label: t('gov.nav.exceptions') },
    { to: '/governance/connectors', label: t('gov.nav.connectors') },
    { to: '/governance/frameworks', label: t('gov.nav.frameworks') },
    { to: '/governance/checks', label: t('gov.nav.checks') },
    ...(can('admin') ? [{ to: '/governance/settings', label: t('gov.nav.settings') }] : []),
    ...(can('auditor') ? [{ to: '/governance/admin', label: t('gov.nav.admin') }] : []),
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap border-b border-cyber-border/50 pb-3">
        <nav aria-label={t('gov.nav.label')} className="flex items-center gap-1 overflow-x-auto">
          {links.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end}
              className={({ isActive }) => `gov-subnav-link ${isActive ? 'gov-subnav-link-active' : ''}`}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-cyber-muted truncate max-w-[220px]" title={user.email}>{user.email}</span>
          <span className="badge-info gov-badge">{t(`gov.role.${user.role}`)}</span>
          <button onClick={signOut} className="btn-ghost text-sm px-3 py-1.5">{t('gov.signOut')}</button>
        </div>
      </div>
      <Outlet />
    </div>
  )
}

function SignIn() {
  const { t } = useTranslation()
  const { signIn } = useGovAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await signIn(email, password)
    } catch (err) {
      setError(errorMessage(err, t))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto mt-10">
      <form onSubmit={submit} className="panel space-y-5" aria-labelledby="gov-signin-title">
        <div>
          <h1 id="gov-signin-title" className="text-lg font-semibold text-cyber-text">{t('gov.signIn.title')}</h1>
          <p className="text-sm text-cyber-muted mt-1 leading-relaxed">{t('gov.signIn.body')}</p>
        </div>
        <Field label={t('gov.signIn.email')} htmlFor="gov-email">
          <input id="gov-email" type="email" autoComplete="username" required value={email}
            onChange={e => setEmail(e.target.value)} className="input-field" />
        </Field>
        <Field label={t('gov.signIn.password')} htmlFor="gov-password">
          <input id="gov-password" type="password" autoComplete="current-password" required value={password}
            onChange={e => setPassword(e.target.value)} className="input-field" />
        </Field>
        {error && <p className="text-sm text-cyber-danger" role="alert">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? t('gov.signIn.busy') : t('gov.signIn.submit')}
        </button>
      </form>
    </div>
  )
}

function Unreachable({ code }: { code: string }) {
  const { t } = useTranslation()
  const { refresh } = useGovAuth()
  return (
    <div className="panel border-cyber-warning/40 max-w-2xl space-y-3" role="alert">
      <h1 className="text-lg font-semibold text-cyber-text">{t('gov.unreachable.title')}</h1>
      <p className="text-sm text-cyber-muted leading-relaxed">{t('gov.unreachable.body', { code })}</p>
      <pre className="text-xs font-mono bg-cyber-bg/80 border border-cyber-border/60 rounded-lg p-3 overflow-x-auto">
        docker compose --profile governance up -d
      </pre>
      <button className="btn-ghost text-sm px-3 py-1.5" onClick={refresh}>{t('status.retry')}</button>
    </div>
  )
}
