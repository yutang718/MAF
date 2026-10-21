import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { THEMES, FONTS, DEFAULT_THEME, DEFAULT_FONT, THEME_FONT, CJK_FONT, type Theme, type FontPairing } from './tokens'

interface ThemeContextValue {
  theme: Theme
  /** The pairing in effect: the theme's own unless the user picked one */
  font: FontPairing
  /** The raw choice, THEME_FONT when following the theme */
  fontId: string
  setThemeId: (id: string) => void
  setFontId: (id: string) => void
  themes: Theme[]
  fonts: FontPairing[]
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

function apply(theme: Theme, font: FontPairing) {
  const root = document.documentElement
  Object.entries(theme.colors).forEach(([key, rgb]) => root.style.setProperty(`--c-${key}`, rgb))
  root.style.setProperty('--grid-alpha', String(theme.gridAlpha))
  root.style.setProperty('--glow-alpha', String(theme.glowAlpha))
  root.style.setProperty('--font-sans', `${font.sans}, ${CJK_FONT.family}, system-ui, sans-serif`)
  root.style.setProperty('--font-mono', `${font.mono}, ${CJK_FONT.family}, ui-monospace, monospace`)
  root.dataset.theme = theme.id
  root.dataset.mode = theme.mode
  root.style.colorScheme = theme.mode
  loadStylesheet('app-font-link', font.href)
  // unicode-range subsets mean only glyphs actually on screen are fetched
  loadStylesheet('app-cjk-font-link', CJK_FONT.href)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState(() => stored('app-theme', DEFAULT_THEME))
  const [fontId, setFontIdState] = useState(() => stored('app-font', DEFAULT_FONT))

  const theme = THEMES.find(t => t.id === themeId) ?? THEMES[0]
  const font = FONTS.find(f => f.id === (fontId === THEME_FONT ? theme.font : fontId))
    ?? FONTS.find(f => f.id === theme.font)
    ?? FONTS[0]

  useEffect(() => { apply(theme, font) }, [theme, font])

  const setThemeId = useCallback((id: string) => {
    setThemeIdState(id)
    persist('app-theme', id)
  }, [])

  const setFontId = useCallback((id: string) => {
    setFontIdState(id)
    persist('app-font', id)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, font, fontId, setThemeId, setFontId, themes: THEMES, fonts: FONTS }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider')
  return ctx
}
