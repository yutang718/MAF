import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import en from './en'
import zh from './zh'

type Lang = 'en' | 'zh'

const translations: Record<Lang, Record<string, string>> = { en, zh }

interface I18nContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: string, vars?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function getInitialLang(): Lang {
  try {
    const stored = localStorage.getItem('app-lang')
    if (stored === 'zh' || stored === 'en') return stored
  } catch {
    // localStorage unavailable
  }
  return 'en'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getInitialLang)

  const setLang = useCallback((newLang: Lang) => {
    setLangState(newLang)
    try { localStorage.setItem('app-lang', newLang) } catch { /* noop */ }
  }, [])

  const t = useCallback((key: string, vars?: Record<string, string | number>): string => {
    let text = translations[lang][key] ?? translations['en'][key] ?? key
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
      })
    }
    return text
  }, [lang])

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useTranslation() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useTranslation must be used within I18nProvider')
  return ctx
}
