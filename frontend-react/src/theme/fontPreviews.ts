import type { FontPairing } from './tokens'

/**
 * Load just the glyphs needed to render the picker's labels in each pairing's
 * own face, so it can preview every font without pulling the full families.
 * `labels` adds text set in those faces besides the pairings' own names.
 */
export function loadFontPreviews(fonts: FontPairing[], labels: string[] = []) {
  const id = 'app-font-preview-link'
  if (document.getElementById(id)) return
  const families = new Set<string>()
  fonts.forEach(f => families.add(f.sans.replace(/'/g, '')))
  const text = Array.from(new Set(fonts.map(f => f.name).concat(labels).join(''))).join('')
  const link = document.createElement('link')
  link.id = id
  link.rel = 'stylesheet'
  link.href = 'https://fonts.googleapis.com/css2?'
    + Array.from(families).map(f => `family=${f.replace(/ /g, '+')}:wght@400;600`).join('&')
    + `&text=${encodeURIComponent(text)}&display=swap`
  document.head.appendChild(link)
}
