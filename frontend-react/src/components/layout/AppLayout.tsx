import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const navigation = [
  { name: 'Overview', to: '/' },
  { name: 'Prompt Analysis', to: '/prompt-injection' },
  { name: 'PII Scanner', to: '/pii-detection' },
  { name: 'Compliance', to: '/islamic-compliance' },
]

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-cyber-bg flex flex-col">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 border-b border-cyber-border/60 bg-cyber-bg/80 backdrop-blur-xl">
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <img src="/evyd-logo.png" alt="Evyd" className="h-5 w-auto" />
              <span className="text-xs text-cyber-muted font-medium bg-cyber-surface-light px-2 py-0.5 rounded">AI Security Platform</span>
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

          {/* Right side */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs text-cyber-muted">System Online</span>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1">
        <div className="max-w-[1200px] mx-auto px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  )
}
