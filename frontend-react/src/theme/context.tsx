import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { THEMES, FONTS, CJK_FONTS, DEFAULT_THEME, DEFAULT_FONT, DEFAULT_CJK_FONT, THEME_FONT, type Theme, type FontPairing, type CJKFont } from './tokens'

interface ThemeContextValue {
  theme: Theme
  /** The pairing in effect: the theme's own unless the user picked one */
  font: FontPairing
  /** The raw choice, THEME_FONT when following the theme */
  fontId: string
  /** Chinese typeface, independent of the theme and Latin pairing */
  cjkFont: CJKFont
  setThemeId: (id: string) => void
  setFontId: (id: string) => void
  setCjkFontId: (id: string) => void
  themes: Theme[]
  fonts: FontPairing[]
  cjkFonts: CJKFont[]
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function stored(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) || fallback
  } catch {
    return fallback
  }
}

function persist(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* private mode */ }
}

/** Swap the Google Fonts <link> rather than loading every pairing up front. */
function loadStylesheet(id: string, href: string) {
  let link = document.getElementById(id) as HTMLLinkElement | null
  if (!link) {
    link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    document.head.appendChild(link)
  }
  if (link.href !== href) link.href = href
}

function apply(theme: Theme, font: FontPairing, cjk: CJKFont) {
  const root = document.documentElement
  Object.entries(theme.colors).forEach(([key, rgb]) => root.style.setProperty(`--c-${key}`, rgb))
  root.style.setProperty('--grid-alpha', String(theme.gridAlpha))
  root.style.setProperty('--glow-alpha', String(theme.glowAlpha))
  root.style.setProperty('--font-sans', `${font.sans}, ${cjk.family}, system-ui, sans-serif`)
  root.style.setProperty('--font-mono', `${font.mono}, ${cjk.family}, ui-monospace, monospace`)
  root.dataset.theme = theme.id
  root.dataset.mode = theme.mode
  root.style.colorScheme = theme.mode
  loadStylesheet('app-font-link', font.href)
  // unicode-range subsets mean only glyphs actually on screen are fetched
  if (cjk.href) loadStylesheet('app-cjk-font-link', cjk.href)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState(() => stored('app-theme', DEFAULT_THEME))
  const [fontId, setFontIdState] = useState(() => stored('app-font', DEFAULT_FONT))
  const [cjkFontId, setCjkFontIdState] = useState(() => stored('app-cjk-font', DEFAULT_CJK_FONT))

  const theme = THEMES.find(t => t.id === themeId) ?? THEMES[0]
  const font = FONTS.find(f => f.id === (fontId === THEME_FONT ? theme.font : fontId))
    ?? FONTS.find(f => f.id === theme.font)
    ?? FONTS[0]

  const cjkFont = CJK_FONTS.find(f => f.id === cjkFontId) ?? CJK_FONTS[0]

  useEffect(() => { apply(theme, font, cjkFont) }, [theme, font, cjkFont])

  const setThemeId = useCallback((id: string) => {
    setThemeIdState(id)
    persist('app-theme', id)
  }, [])

  const setFontId = useCallback((id: string) => {
    setFontIdState(id)
    persist('app-font', id)
  }, [])

  const setCjkFontId = useCallback((id: string) => {
    setCjkFontIdState(id)
    persist('app-cjk-font', id)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, font, fontId, cjkFont, setThemeId, setFontId, setCjkFontId, themes: THEMES, fonts: FONTS, cjkFonts: CJK_FONTS }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider')
  return ctx
}
