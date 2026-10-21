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
  /** Id of the font pairing this theme was designed with */
  font: string
  /** One-line use scene: who looks at it, under what light. It decides light vs dark. */
  scene: string
  sceneZh: string
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
    font: 'jakarta',
    scene: "Demos and presentations: the brand's neon identity.",
    sceneZh: '演示与汇报：品牌的霓虹识别。',
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
    font: 'inter',
    scene: 'Daily operator work: brand blue, no glow, low glare.',
    sceneZh: '日常运维工作：品牌蓝、无光晕、低眩光。',
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
    gridAlpha: 0,
    glowAlpha: 0,
  },
  {
    id: 'nord',
    name: 'Nord',
    nameZh: '极地',
    font: 'fira',
    scene: 'Long sessions in a dim room: muted arctic tones.',
    sceneZh: '昏暗环境长时间工作：低饱和极地色。',
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
      muted: '148 160 177',
    },
    gridAlpha: 0.035,
    glowAlpha: 0.35,
  },
  {
    id: 'harbor',
    name: 'Harbor',
    nameZh: '港湾',
    font: 'hanken',
    scene: 'Night watch in a chart room: sea-glass on deep petrol.',
    sceneZh: '海图室夜班：深石油蓝上的海玻璃色。',
    mode: 'dark',
    swatch: ['#05171b', '#0a1f24', '#67dfd1'],
    colors: {
      bg: '5 23 27',
      surface: '10 31 36',
      'surface-light': '20 42 48',
      border: '37 60 66',
      accent: '103 223 209',
      green: '117 215 141',
      purple: '187 163 232',
      warning: '244 195 82',
      danger: '249 119 112',
      safe: '117 215 141',
      text: '230 241 242',
      muted: '144 170 175',
    },
    gridAlpha: 0,
    glowAlpha: 0,
  },
  {
    id: 'basalt',
    name: 'Basalt',
    nameZh: '玄武',
    font: 'barlow',
    scene: 'Studio desk after hours: warm stone that eases glare.',
    sceneZh: '下班后的工作台：暖色岩石，缓解眩光。',
    mode: 'dark',
    swatch: ['#191512', '#211d1a', '#a4b3f8'],
    colors: {
      bg: '25 21 18',
      surface: '33 29 26',
      'surface-light': '45 40 36',
      border: '63 57 52',
      accent: '164 179 248',
      green: '121 210 141',
      purple: '220 160 214',
      warning: '244 195 82',
      danger: '245 116 109',
      safe: '121 210 141',
      text: '242 238 233',
      muted: '171 163 155',
    },
    gridAlpha: 0,
    glowAlpha: 0,
  },
  {
    id: 'daylight',
    name: 'Daylight',
    nameZh: '日光',
    font: 'geist',
    scene: 'Bright office: crisp white, sharp blue actions.',
    sceneZh: '明亮办公室：清爽白底、锐利蓝色操作。',
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
    font: 'source',
    scene: 'Reading reports: stone paper, teal ink.',
    sceneZh: '阅读报告：石纸底色、青色墨水。',
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
  {
    id: 'blueprint',
    name: 'Blueprint',
    nameZh: '蓝图',
    font: 'archivo',
    scene: 'Drafting table in daylight: the grid is the working surface.',
    sceneZh: '日光下的绘图桌：网格即工作面。',
    mode: 'light',
    swatch: ['#eff8fe', '#ffffff', '#00548c'],
    colors: {
      bg: '239 248 254',
      surface: '255 255 255',
      'surface-light': '230 242 250',
      border: '194 216 229',
      accent: '0 84 140',
      green: '19 119 56',
      purple: '108 68 164',
      warning: '157 99 0',
      danger: '194 40 38',
      safe: '19 119 56',
      text: '16 35 52',
      muted: '79 103 120',
    },
    gridAlpha: 0.07,
    glowAlpha: 0,
  },
  {
    id: 'mulberry',
    name: 'Mulberry',
    nameZh: '桑葚',
    font: 'franklin',
    scene: 'Afternoon review: lilac paper, plum ink.',
    sceneZh: '午后评审：淡紫纸张、梅子色墨水。',
    mode: 'light',
    swatch: ['#faf5f9', '#ffffff', '#8e2b6b'],
    colors: {
      bg: '250 245 249',
      surface: '255 255 255',
      'surface-light': '245 237 244',
      border: '223 211 222',
      accent: '142 43 107',
      green: '19 119 56',
      purple: '95 73 171',
      warning: '160 96 11',
      danger: '194 39 45',
      safe: '19 119 56',
      text: '39 26 38',
      muted: '109 93 108',
    },
    gridAlpha: 0,
    glowAlpha: 0,
  },
  {
    id: 'field',
    name: 'Field',
    nameZh: '旷野',
    font: 'atkinson',
    scene: 'Projector in a lit room: maximum legibility, firm borders.',
    sceneZh: '明亮会议室投影：最高可读性、清晰边框。',
    mode: 'light',
    swatch: ['#fcfcfc', '#ffffff', '#5737c8'],
    colors: {
      bg: '252 252 252',
      surface: '255 255 255',
      'surface-light': '243 243 245',
      border: '189 189 196',
      accent: '87 55 200',
      green: '0 114 46',
      purple: '157 35 152',
      warning: '151 88 0',
      danger: '190 18 25',
      safe: '0 114 46',
      text: '17 17 22',
      muted: '76 76 85',
    },
    gridAlpha: 0,
    glowAlpha: 0,
  },
]

export interface FontPairing {
  id: string
  name: string
  nameZh: string
  /** UI / body face; product UI uses one family for headings, labels and body */
  sans: string
  /** Tabular data, scores, code */
  mono: string
  /** Short descriptor shown under the name in the picker */
  mood: string
  moodZh: string
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
    mood: 'Rounded, friendly',
    moodZh: '圆润友好',
    href: 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'inter',
    name: 'Inter',
    nameZh: 'Inter',
    sans: "'Inter'",
    mono: "'Roboto Mono'",
    mood: 'Neutral workhorse',
    moodZh: '中性主力',
    href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Roboto+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'fira',
    name: 'Fira',
    nameZh: 'Fira',
    sans: "'Fira Sans'",
    mono: "'Fira Code'",
    mood: 'Humanist, data-dense',
    moodZh: '人文、高密度',
    href: 'https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500;600;700&display=swap',
  },
  {
    id: 'hanken',
    name: 'Hanken',
    nameZh: 'Hanken',
    sans: "'Hanken Grotesk'",
    mono: "'Spline Sans Mono'",
    mood: 'Calm grotesk',
    moodZh: '沉静无衬线',
    href: 'https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@300;400;500;600;700;800&family=Spline+Sans+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'barlow',
    name: 'Barlow',
    nameZh: 'Barlow',
    sans: "'Barlow'",
    mono: "'Red Hat Mono'",
    mood: 'Signage, compact',
    moodZh: '标识风、紧凑',
    href: 'https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700;800&family=Red+Hat+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'geist',
    name: 'Geist',
    nameZh: 'Geist',
    sans: "'Geist'",
    mono: "'Geist Mono'",
    mood: 'Precise, minimal',
    moodZh: '精确极简',
    href: 'https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700;800&family=Geist+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'source',
    name: 'Source',
    nameZh: '思源',
    sans: "'Source Sans 3'",
    mono: "'Source Code Pro'",
    mood: 'Long-form reading',
    moodZh: '长文阅读',
    href: 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700;800&family=Source+Code+Pro:wght@400;500;600;700&display=swap',
  },
  {
    id: 'archivo',
    name: 'Archivo',
    nameZh: 'Archivo',
    sans: "'Archivo'",
    mono: "'Azeret Mono'",
    mood: 'Engineered, firm',
    moodZh: '工程感、稳重',
    href: 'https://fonts.googleapis.com/css2?family=Archivo:wght@300;400;500;600;700;800&family=Azeret+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'franklin',
    name: 'Franklin',
    nameZh: 'Franklin',
    sans: "'Libre Franklin'",
    mono: "'Overpass Mono'",
    mood: 'Classic gothic',
    moodZh: '经典哥特体',
    href: 'https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@300;400;500;600;700;800&family=Overpass+Mono:wght@400;500;600;700&display=swap',
  },
  {
    id: 'atkinson',
    name: 'Atkinson',
    nameZh: 'Atkinson',
    sans: "'Atkinson Hyperlegible Next'",
    mono: "'Atkinson Hyperlegible Mono'",
    mood: 'Maximum legibility',
    moodZh: '极致易读',
    href: 'https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@300;400;500;600;700;800&family=Atkinson+Hyperlegible+Mono:wght@400;500;600;700&display=swap',
  },
]

/** Font id meaning "use the pairing the current theme was designed with". */
export const THEME_FONT = 'theme'

export interface CJKFont {
  id: string
  name: string
  nameZh: string
  /** CSS family list placed after the Latin face, so Chinese glyphs fall through to it */
  family: string
  /** Stylesheet split by unicode-range, so only glyphs on screen download; null = installed fonts */
  href: string | null
  mood: string
  moodZh: string
}

/** Chinese typeface, chosen independently of the theme's Latin pairing. */
export const CJK_FONTS: CJKFont[] = [
  {
    id: 'noto-sans',
    name: 'Source Han Sans',
    nameZh: '思源黑体',
    family: "'Noto Sans SC'",
    href: 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;800&display=swap',
    mood: 'Neutral sans, all weights',
    moodZh: '中性黑体，字重齐全',
  },
  {
    id: 'wenkai',
    name: 'LXGW WenKai',
    nameZh: '霞鹜文楷',
    // Screen edition, GB glyph forms: tuned for reading on displays
    family: "'LXGW WenKai Screen'",
    href: 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaigbscreen.css',
    mood: 'Warm kai, easy reading',
    moodZh: '温润楷体，适合阅读',
  },
  {
    id: 'noto-serif',
    name: 'Source Han Serif',
    nameZh: '思源宋体',
    family: "'Noto Serif SC'",
    href: 'https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;600;700&display=swap',
    mood: 'Classic serif, formal',
    moodZh: '经典宋体，正式稳重',
  },
  {
    id: 'xiaowei',
    name: 'ZCOOL XiaoWei',
    nameZh: '站酷小薇',
    family: "'ZCOOL XiaoWei'",
    href: 'https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&display=swap',
    mood: 'Literary serif, one weight',
    moodZh: '文艺宋体，单一字重',
  },
  {
    id: 'system',
    name: 'System',
    nameZh: '系统字体',
    family: "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei'",
    href: null,
    mood: 'PingFang / YaHei, no download',
    moodZh: '苹方 / 微软雅黑，无需下载',
  },
]

export const DEFAULT_CJK_FONT = 'noto-sans'

/** Calm working theme by default; Cyber stays in the picker as the demo look. */
export const DEFAULT_THEME = 'midnight'
export const DEFAULT_FONT = THEME_FONT
