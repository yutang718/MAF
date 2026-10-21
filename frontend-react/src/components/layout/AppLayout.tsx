import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { ExclamationTriangleIcon } from '@heroicons/react/20/solid'
import { useTranslation } from '../../i18n/context'
import { useHealth, type ApiStatus } from '../../health/state'
import AppearanceMenu from './AppearanceMenu'

const STATUS_STYLE: Record<ApiStatus, { dot: string; text: string; label: string }> = {
  checking: { dot: 'bg-cyber-muted', text: 'text-cyber-muted', label: 'nav.checking' },
  online: { dot: 'bg-cyber-safe', text: 'text-cyber-safe', label: 'nav.online' },
  degraded: { dot: 'bg-cyber-warning', text: 'text-cyber-warning', label: 'nav.degraded' },
  offline: { dot: 'bg-cyber-danger', text: 'text-cyber-danger', label: 'nav.offline' },
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useTranslation()
  const { status, health, checkedAt } = useHealth()
  const style = STATUS_STYLE[status]
  const time = checkedAt?.toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) ?? ''
  const statusTitle = status === 'offline'
    ? t('nav.statusTitleOffline', { time })
    : health ? t('nav.statusTitle', { version: health.version, time }) : undefined
  const modelsLoaded = health?.components.guard_models.models_count

  const navigation = [
    { name: t('nav.overview'), to: '/' },
    { name: t('nav.promptAnalysis'), to: '/prompt-injection' },
    { name: t('nav.piiScanner'), to: '/pii-detection' },
    { name: t('nav.compliance'), to: '/islamic-compliance' },
  ]

  return (
    <div className="min-h-screen bg-cyber-bg bg-grid flex flex-col">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 border-b border-cyber-border/60 bg-cyber-bg/90 backdrop-blur-xl">
        <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <img src="/evyd-logo.png" alt="Evyd" className="h-5 w-auto app-logo" />
              <div className="h-4 w-px bg-cyber-border/60" />
              <span className="text-sm text-cyber-accent font-semibold tracking-tight">{t('nav.platformName')}</span>
            </div>

            {/* Nav Links */}
            <nav className="flex items-center gap-1">
              {navigation.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `nav-link ${isActive ? 'nav-link-active' : ''}`
                  }
                >
                  {item.name}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right side: status read from the health endpoint, never assumed */}
          <div className="flex items-center gap-5">
            <span className="text-xs text-cyber-muted whitespace-nowrap">
              {t('nav.models')}: <span className="font-mono text-cyber-text font-semibold">{modelsLoaded ?? '—'}</span>
            </span>
            <div className="h-4 w-px bg-cyber-border/60" />
            <div className="flex items-center gap-2 whitespace-nowrap" title={statusTitle} role="status">
              <span className={`w-2 h-2 rounded-full ${style.dot}`} aria-hidden="true" />
              <span className={`text-xs font-medium ${style.text}`}>{t(style.label)}</span>
            </div>
            <div className="h-4 w-px bg-cyber-border/60" />
            {/* Language Toggle */}
            <button
              onClick={() => setLang(lang === 'en' ? 'zh' : 'en')}
              aria-label={lang === 'en' ? 'Switch to Chinese' : '切换到英文'}
              className="px-2.5 py-1 rounded border border-cyber-border/60 text-xs font-medium text-cyber-text cursor-pointer hover:border-cyber-accent/60 hover:text-cyber-accent transition-colors"
            >
              {lang === 'en' ? '中文' : 'EN'}
            </button>
            <AppearanceMenu />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1">
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          <ApiStatusBanner />
          {children}
        </div>
      </main>
    </div>
  )
}

/**
 * One explanation for a down or half-loaded backend, so pages don't each repeat
 * the same failure once per model.
 */
function ApiStatusBanner() {
  const { t } = useTranslation()
  const { status, error, recheck } = useHealth()
  const [retrying, setRetrying] = useState(false)
  if (status !== 'offline' && status !== 'degraded') return null

  const offline = status === 'offline'
  const retry = async () => {
    setRetrying(true)
    await recheck()
    setRetrying(false)
  }

  return (
    <div
      role="alert"
      className={`mb-6 flex items-start gap-3 rounded-lg border px-4 py-3
                  ${offline ? 'border-cyber-danger/40 bg-cyber-danger/[0.06]' : 'border-cyber-warning/40 bg-cyber-warning/[0.06]'}`}
    >
      <ExclamationTriangleIcon
        className={`w-5 h-5 mt-0.5 flex-shrink-0 ${offline ? 'text-cyber-danger' : 'text-cyber-warning'}`}
        aria-hidden="true"
      />
      <div className="flex-1 min-w-0">
        <p className="text-[15px] font-semibold text-cyber-text">
          {t(offline ? 'status.offlineTitle' : 'status.degradedTitle')}
        </p>
        <p className="text-sm text-cyber-muted mt-0.5 leading-relaxed">
          {offline ? t('status.offlineBody', { reason: error ?? '' }) : t('status.degradedBody')}
        </p>
      </div>
      <button onClick={retry} disabled={retrying} className="btn-ghost text-sm px-3 py-1.5 flex-shrink-0">
        {t(retrying ? 'status.retrying' : 'status.retry')}
      </button>
    </div>
  )
}
