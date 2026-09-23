import { useState, useRef, useEffect } from 'react'
import { useTheme } from '../../theme/context'
import { useTranslation } from '../../i18n/context'

/** Header popover for picking a colour theme and a font pairing. */
export default function AppearanceMenu() {
  const { theme, font, setThemeId, setFontId, themes, fonts } = useTheme()
  const { t, lang } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const label = (en: string, zh: string) => (lang === 'zh' ? zh : en)

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-label={t('appearance.title')}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={t('appearance.title')}
        className="flex items-center gap-2 px-2.5 py-1 rounded border border-cyber-border/60 text-xs font-medium
                   text-cyber-text cursor-pointer hover:border-cyber-accent/60 hover:text-cyber-accent transition-colors"
      >
        {/* Swatch preview doubles as the affordance */}
        <span className="flex items-center -space-x-1" aria-hidden="true">
          {theme.swatch.map((c, i) => (
            <span
              key={i}
              className="w-2.5 h-2.5 rounded-full border border-cyber-border"
              style={{ backgroundColor: c }}
            />
          ))}
        </span>
        <span>{label(theme.name, theme.nameZh)}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t('appearance.title')}
          className="absolute right-0 mt-2 w-[268px] z-50 rounded-xl border border-cyber-border
                     bg-cyber-surface shadow-glow-sm p-3 space-y-3"
          style={{ backgroundColor: 'rgb(var(--c-surface))' }}
        >
          <section>
            <h3 className="text-[11px] font-semibold text-cyber-muted uppercase tracking-wider mb-2">
              {t('appearance.theme')}
            </h3>
            <div className="space-y-1">
              {themes.map(th => (
                <button
                  key={th.id}
                  onClick={() => setThemeId(th.id)}
                  aria-pressed={th.id === theme.id}
                  className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md cursor-pointer
                              transition-colors duration-150 text-left
                              ${th.id === theme.id
                                ? 'bg-cyber-accent/[0.1] text-cyber-accent'
                                : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-text/[0.04]'}`}
                >
                  <span className="flex items-center -space-x-1 flex-shrink-0" aria-hidden="true">
                    {th.swatch.map((c, i) => (
                      <span
                        key={i}
                        className="w-3.5 h-3.5 rounded-full border border-cyber-border"
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </span>
                  <span className="text-[13px] font-medium">{label(th.name, th.nameZh)}</span>
                  <span className="ml-auto text-[10px] uppercase tracking-wider opacity-60">
                    {t(th.mode === 'dark' ? 'appearance.dark' : 'appearance.light')}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <div className="h-px bg-cyber-border/60" />

          <section>
            <h3 className="text-[11px] font-semibold text-cyber-muted uppercase tracking-wider mb-2">
              {t('appearance.font')}
            </h3>
            <div className="grid grid-cols-2 gap-1">
              {fonts.map(f => (
                <button
                  key={f.id}
                  onClick={() => setFontId(f.id)}
                  aria-pressed={f.id === font.id}
                  className={`px-2 py-1.5 rounded-md text-[13px] font-medium cursor-pointer text-left
                              transition-colors duration-150
                              ${f.id === font.id
                                ? 'bg-cyber-accent/[0.1] text-cyber-accent'
                                : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-text/[0.04]'}`}
                  style={{ fontFamily: `${f.sans}, system-ui, sans-serif` }}
                >
                  {label(f.name, f.nameZh)}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-cyber-muted mt-2 leading-relaxed">
              {t('appearance.hint')}
            </p>
          </section>
        </div>
      )}
    </div>
  )
}
