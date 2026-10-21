import { useRef, type KeyboardEvent, type ReactNode } from 'react'

/**
 * WAI-ARIA tablist: arrow keys / Home / End move between tabs, only the active
 * tab is in the tab order. State is the tab index, never the translated label,
 * so switching language keeps the user where they were.
 */
export function Tabs({ id, labels, active, onChange, className = '' }: {
  id: string
  labels: string[]
  active: number
  onChange: (index: number) => void
  className?: string
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const last = labels.length - 1
    const next = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1, Home: 0, End: last }[e.key]
    if (next === undefined) return
    e.preventDefault()
    onChange(next)
    refs.current[next]?.focus()
  }

  return (
    <div role="tablist" className={`flex items-center gap-1 p-1 bg-cyber-surface/40 rounded-lg border border-cyber-border/40 ${className}`}>
      {labels.map((label, i) => (
        <button
          key={i}
          ref={el => { refs.current[i] = el }}
          id={`${id}-tab-${i}`}
          role="tab"
          aria-selected={active === i}
          aria-controls={`${id}-panel-${i}`}
          tabIndex={active === i ? 0 : -1}
          onClick={() => onChange(i)}
          onKeyDown={e => onKeyDown(e, i)}
          className={`tab-btn whitespace-nowrap ${active === i ? 'tab-btn-active' : ''}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

/** Stays mounted while hidden, so work in one tab survives a visit to another. */
export function TabPanel({ id, index, active, children }: {
  id: string; index: number; active: number; children: ReactNode
}) {
  return (
    <div role="tabpanel" id={`${id}-panel-${index}`} aria-labelledby={`${id}-tab-${index}`} hidden={active !== index}>
      {children}
    </div>
  )
}
