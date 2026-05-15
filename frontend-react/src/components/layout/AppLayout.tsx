import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from '../../i18n/context'

export default function AppLayout({ children }: { children: ReactNode }) {
  const { t, lang, setLang } = useTranslation()

  const navigation = [
    { name: t('nav.overview'), to: '/' },
    { name: t('nav.promptAnalysis'), to: '/prompt-injection' },
    { name: t('nav.piiScanner'), to: '/pii-detection' },
    { name: t('nav.compliance'), to: '/islamic-compliance' },
  ]

  return (
    <div className="min-h-screen bg-cyber-bg flex flex-col">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 border-b border-cyber-border/60 bg-cyber-bg/90 backdrop-blur-xl">
        <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <img src="/evyd-logo.png" alt="Evyd" className="h-5 w-auto" />
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

          {/* Right side - live metrics */}
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="text-cyber-muted">{t('nav.models')}: <span className="text-cyber-text font-semibold">3</span></span>
              <span className="text-cyber-muted">{t('nav.lang')}: <span className="text-cyber-text font-semibold">100+</span></span>
              <span className="text-cyber-muted">{t('nav.uptime')}: <span className="text-emerald-400 font-semibold">99.9%</span></span>
            </div>
            <div className="h-4 w-px bg-cyber-border/60" />
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-glow" />
              <span className="text-xs text-emerald-400 font-medium">{t('nav.online')}</span>
            </div>
            <div className="h-4 w-px bg-cyber-border/60" />
            {/* Language Toggle */}
            <button
              onClick={() => setLang(lang === 'en' ? 'zh' : 'en')}
              className="px-2.5 py-1 rounded border border-cyber-border/60 text-xs font-medium text-cyber-text hover:border-cyber-accent/60 hover:text-cyber-accent transition-colors"
            >
              {lang === 'en' ? '中文' : 'EN'}
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1">
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}
