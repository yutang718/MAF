import { useState, useRef, useEffect, type ReactNode } from 'react'
import { CheckIcon } from '@heroicons/react/20/solid'
import { useTheme } from '../../theme/context'
import { loadFontPreviews } from '../../theme/fontPreviews'
import { useTranslation } from '../../i18n/context'
import { THEME_FONT, type Theme, type FontPairing } from '../../theme/tokens'

/**
 * Header popover for picking a theme and, optionally, overriding its typeface.
 * Each theme ships with the font it was designed with; "Match theme" follows it.
 */
export default function AppearanceMenu() {
  const { theme, font, fontId, setThemeId, setFontId, themes, fonts } = useTheme()
  const { t, lang } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    loadFontPreviews(fonts, [...themes.map(th => th.name), t('appearance.matchTheme')])
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
  }, [open, fonts, themes, t])

  const label = (en: string, zh: string) => (lang === 'zh' ? zh : en)
  const fontById = (id: string) => fonts.find(f => f.id === id) ?? font
  const themeFont = fontById(theme.font)
  const followsTheme = fontId === THEME_FONT
  const groups: { mode: Theme['mode']; items: Theme[] }[] = [
    { mode: 'dark', items: themes.filter(th => th.mode === 'dark') },
    { mode: 'light', items: themes.filter(th => th.mode === 'light') },
  ]

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
        <Swatch colors={theme.swatch} />
        <span>{label(theme.name, theme.nameZh)}</span>
        {!followsTheme && (
          <>
            <span className="hidden sm:inline text-cyber-muted">·</span>
            <span className="hidden sm:inline text-cyber-muted">{label(font.name, font.nameZh)}</span>
          </>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t('appearance.title')}
          className="absolute right-0 mt-2 w-[380px] max-w-[calc(100vw-32px)] max-h-[min(80vh,680px)] overflow-y-auto
                     overscroll-contain z-50 rounded-xl border border-cyber-border bg-cyber-surface p-3 space-y-4
                     shadow-[0_12px_32px_-8px_rgb(0_0_0/0.35)] animate-count-up"
          style={{ backgroundColor: 'rgb(var(--c-surface))', animationDuration: '160ms' }}
        >
          <section>
            <SectionTitle>{t('appearance.theme')}</SectionTitle>
            {groups.map(g => (
              <div key={g.mode} className="mb-2.5 last:mb-0">
                <p className="text-[11px] text-cyber-muted mb-1.5 px-0.5">
                  {t(g.mode === 'dark' ? 'appearance.dark' : 'appearance.light')}
                </p>
                <div className="grid grid-cols-2 gap-1.5">
                  {g.items.map(th => (
                    <ThemeCard
                      key={th.id}
                      theme={th}
                      font={fontById(th.font)}
                      active={th.id === theme.id}
                      name={label(th.name, th.nameZh)}
                      onSelect={() => setThemeId(th.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
            <p className="text-[12px] text-cyber-muted leading-snug mt-2.5 px-0.5">
              {label(theme.scene, theme.sceneZh)}
            </p>
          </section>

          <div className="h-px bg-cyber-border/60" />

          <section>
            <SectionTitle>{t('appearance.font')}</SectionTitle>
            <div className="grid grid-cols-2 gap-1.5">
              <FontOption
                font={themeFont}
                active={followsTheme}
                name={t('appearance.matchTheme')}
                detail={label(themeFont.name, themeFont.nameZh)}
                onSelect={() => setFontId(THEME_FONT)}
              />
              {fonts.map(f => (
                <FontOption
                  key={f.id}
                  font={f}
                  active={!followsTheme && f.id === font.id}
                  name={label(f.name, f.nameZh)}
                  detail={label(f.mood, f.moodZh)}
                  onSelect={() => setFontId(f.id)}
                />
              ))}
            </div>
            <p className="text-[12px] text-cyber-muted mt-2.5 leading-snug px-0.5">
              {t('appearance.hint')}
            </p>
          </section>
        </div>
      )}
    </div>
  )
}

function fontStack(f: FontPairing) {
  return `${f.sans}, system-ui, sans-serif`
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-[12px] font-semibold text-cyber-text mb-2 px-0.5">
      {children}
    </h3>
  )
}

function Swatch({ colors }: { colors: string[] }) {
  return (
    <span className="flex items-center -space-x-1 flex-shrink-0" aria-hidden="true">
      {colors.map((c, i) => (
        <span key={i} className="w-2.5 h-2.5 rounded-full ring-1 ring-cyber-border" style={{ backgroundColor: c }} />
      ))}
    </span>
  )
}

/** A miniature of the theme itself: its ground, a surface row set in its own face, and its accent. */
function ThemeCard({ theme, font, active, name, onSelect }: {
  theme: Theme; font: FontPairing; active: boolean; name: string; onSelect: () => void
}) {
  const [bg, surface, accent] = theme.swatch
  const rgb = (k: keyof Theme['colors']) => `rgb(${theme.colors[k]})`
  return (
    <button
      onClick={onSelect}
      aria-pressed={active}
      title={theme.scene}
      className={`relative rounded-lg border p-1.5 text-left cursor-pointer transition-[border-color,box-shadow] duration-150
                  ${active
                    ? 'border-cyber-accent ring-1 ring-cyber-accent/40'
                    : 'border-cyber-border/60 hover:border-cyber-muted/60'}`}
      style={{ backgroundColor: bg }}
    >
      <span
        className="flex items-center gap-1.5 rounded-md px-2 py-1.5"
        style={{ backgroundColor: surface, boxShadow: `inset 0 0 0 1px ${rgb('border')}` }}
      >
        <span className="text-[13px] font-semibold truncate" style={{ color: rgb('text'), fontFamily: fontStack(font) }}>
          {name}
        </span>
        {active && <CheckIcon className="ml-auto w-3.5 h-3.5 flex-shrink-0" style={{ color: accent }} aria-hidden="true" />}
      </span>
      <span className="flex items-center justify-between gap-2 mt-1 px-1" aria-hidden="true">
        <span className="text-[10px] truncate" style={{ color: rgb('muted'), fontFamily: fontStack(font) }}>
          {font.name}
        </span>
        <span className="flex items-center gap-0.5">
          {(['accent', 'safe', 'warning', 'danger'] as const).map(k => (
            <span key={k} className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: rgb(k) }} />
          ))}
        </span>
      </span>
    </button>
  )
}

function FontOption({ font, active, name, detail, onSelect }: {
  font: FontPairing; active: boolean; name: string; detail: string; onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      aria-pressed={active}
      className={`relative px-2.5 py-2 rounded-lg border text-left cursor-pointer min-h-[48px]
                  transition-colors duration-150
                  ${active
                    ? 'border-cyber-accent/50 bg-cyber-accent/[0.08]'
                    : 'border-cyber-border/60 hover:border-cyber-muted/50 hover:bg-cyber-text/[0.03]'}`}
    >
      <span
        className={`block text-[14px] font-semibold leading-tight pr-4 ${active ? 'text-cyber-accent' : 'text-cyber-text'}`}
        style={{ fontFamily: fontStack(font) }}
      >
        {name}
      </span>
      <span className="block text-[11px] text-cyber-muted leading-snug mt-0.5">{detail}</span>
      {active && <CheckIcon className="absolute top-2 right-2 w-3.5 h-3.5 text-cyber-accent" aria-hidden="true" />}
    </button>
  )
}
