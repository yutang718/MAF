/**
 * Theme + font definitions.
 *
 * Colors are stored as space-separated RGB channels so Tailwind can apply its
 * own alpha modifiers: `rgb(var(--c-surface) / <alpha-value>)` makes existing
 * classes like `bg-cyber-surface/60` keep working unchanged across themes.
 */

export type ThemeMode = 'dark' | 'light'

export interface Theme {
  id: string
  name: string
  nameZh: string
  mode: ThemeMode
  /** Swatches shown in the picker: [background, surface, accent] */
  swatch: [string, string, string]
  colors: {
    bg: string
    surface: string
    'surface-light': string
    border: string
    accent: string
    green: string
    purple: string
    warning: string
    danger: string
    safe: string
    text: string
    muted: string
  }
  /** Opacity of the background grid and of glow shadows, 0 disables them. */
  gridAlpha: number
  glowAlpha: number
}

export const THEMES: Theme[] = [
  {
    id: 'cyber',
    name: 'Cyber',
    nameZh: '赛博',
    mode: 'dark',
    swatch: ['#06080d', '#0c1018', '#38bdf8'],
    colors: {
      bg: '6 8 13',
      surface: '12 16 24',
      'surface-light': '20 26 38',
      border: '28 36 54',
      accent: '56 189 248',
      green: '52 211 153',
      purple: '167 139 250',
      warning: '251 191 36',
      danger: '248 113 113',
      safe: '52 211 153',
      text: '237 240 245',
      muted: '122 130 148',
    },
    gridAlpha: 0.03,
    glowAlpha: 1,
  },
  {
    id: 'midnight',
    name: 'Midnight',
    nameZh: '午夜蓝',
    mode: 'dark',
    swatch: ['#0b1220', '#111c31', '#60a5fa'],
    colors: {
      bg: '11 18 32',
      surface: '17 28 49',
      'surface-light': '26 40 66',
      border: '30 42 66',
      accent: '96 165 250',
      green: '52 211 153',
      purple: '167 139 250',
      warning: '251 191 36',
      danger: '248 113 113',
      safe: '52 211 153',
      text: '232 237 247',
      muted: '132 148 174',
    },
    gridAlpha: 0.04,
    glowAlpha: 0.6,
  },
  {
    id: 'nord',
    name: 'Nord',
    nameZh: '极地',
    mode: 'dark',
    swatch: ['#171c24', '#1f252f', '#88c0d0'],
    colors: {
      bg: '23 28 36',
      surface: '31 37 47',
      'surface-light': '46 52 64',
      border: '56 63 76',
      accent: '136 192 208',
      green: '163 190 140',
      purple: '180 142 173',
      warning: '235 203 139',
      danger: '191 97 106',
      safe: '163 190 140',
      text: '236 239 244',
      muted: '141 153 170',
    },
    gridAlpha: 0.035,
    glowAlpha: 0.35,
  },
  {
    id: 'daylight',
    name: 'Daylight',
    nameZh: '日光',
    mode: 'light',
    swatch: ['#f8fafc', '#ffffff', '#1e40af'],
    colors: {
      bg: '248 250 252',
      surface: '255 255 255',
      'surface-light': '241 245 249',
      border: '203 213 225',
      accent: '30 64 175',
      green: '21 128 61',
      purple: '109 40 217',
      warning: '180 83 9',
      danger: '220 38 38',
      safe: '21 128 61',
      text: '15 23 42',
      muted: '85 100 122',
    },
    gridAlpha: 0.05,
    glowAlpha: 0,
  },
  {
    id: 'paper',
    name: 'Paper',
    nameZh: '纸张',
    mode: 'light',
    swatch: ['#fafaf9', '#ffffff', '#0f766e'],
    colors: {
      bg: '250 250 249',
      surface: '255 255 255',
      'surface-light': '245 245 244',
      border: '214 211 209',
      accent: '15 118 110',
      green: '21 128 61',
      purple: '109 40 217',
      warning: '161 98 7',
      danger: '185 28 28',
      safe: '21 128 61',
      text: '28 25 23',
      muted: '87 83 78',
    },
    gridAlpha: 0,
    glowAlpha: 0,
  },
]

export interface FontPairing {
  id: string
  name: string
  nameZh: string
  /** UI / body face */
  sans: string
  /** Tabular data, scores, code */
  mono: string
  /** Google Fonts href for this pairing */
  href: string
}

export const FONTS: FontPairing[] = [
  {
    id: 'jakarta',
    name: 'Jakarta',
    nameZh: '雅加达',
    sans: "'Plus Jakarta Sans'",
    mono: "'JetBrains Mono'",
    href: 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap',
  },
  {
    id: 'inter',
    name: 'Inter',
    nameZh: 'Inter',
    sans: "'Inter'",
    mono: "'JetBrains Mono'",
    href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap',
  },
  {
    id: 'fira',
    name: 'Fira',
    nameZh: 'Fira',
    sans: "'Fira Sans'",
    mono: "'Fira Code'",
    href: 'https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500;600;700&display=swap',
  },
  {
    id: 'plex',
    name: 'IBM Plex',
    nameZh: 'IBM Plex',
    sans: "'IBM Plex Sans'",
    mono: "'IBM Plex Mono'",
    href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap',
  },
]

export const DEFAULT_THEME = 'cyber'
export const DEFAULT_FONT = 'jakarta'
