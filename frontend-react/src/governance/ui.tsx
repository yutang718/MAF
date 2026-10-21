import type { ReactNode } from 'react'
import { useTranslation } from '../i18n/context'
import type { CheckStatus, ControlStatus, Severity } from '../types/governance'

// Status colour carries meaning only together with its label, never alone.
const CONTROL_STYLE: Record<ControlStatus, string> = {
  pass: 'badge-safe', evidenced: 'badge-safe', partial: 'badge-warn', fail: 'badge-danger',
  needs_evidence: 'badge-info', evidence_expired: 'badge-warn', no_data: 'gov-badge-muted', not_applicable: 'gov-badge-muted',
}
const CHECK_STYLE: Record<CheckStatus, string> = {
  pass: 'badge-safe', partial: 'badge-warn', fail: 'badge-danger', not_available: 'gov-badge-muted',
  error: 'badge-danger', accepted: 'badge-info',
}
const SEVERITY_STYLE: Record<Severity, string> = {
  critical: 'badge-danger', high: 'badge-danger', medium: 'badge-warn', low: 'badge-info',
}

export function ControlStatusBadge({ status }: { status: ControlStatus }) {
  const { t } = useTranslation()
  return <span className={`${CONTROL_STYLE[status]} gov-badge`}>{t(`gov.cstatus.${status}`)}</span>
}

export function CheckStatusBadge({ status }: { status: CheckStatus }) {
  const { t } = useTranslation()
  return <span className={`${CHECK_STYLE[status]} gov-badge`}>{t(`gov.status.${status}`)}</span>
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { t } = useTranslation()
  return (
    <span className={`${SEVERITY_STYLE[severity]} gov-badge ${severity === 'critical' ? 'gov-badge-solid' : ''}`}>
      {t(`gov.severity.${severity}`)}
    </span>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-cyber-text">{title}</h1>
        {subtitle && <p className="text-sm text-cyber-muted mt-0.5 max-w-3xl leading-relaxed">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  )
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="panel border-cyber-danger/30 flex items-start justify-between gap-4" role="alert">
      <p className="text-sm text-cyber-danger leading-relaxed">{message}</p>
      {onRetry && <button className="btn-ghost text-sm px-3 py-1.5 flex-shrink-0" onClick={onRetry}>{t('status.retry')}</button>}
    </div>
  )
}

export function Loading() {
  const { t } = useTranslation()
  return <div className="panel text-sm text-cyber-muted" role="status">{t('gov.loading')}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="panel text-sm text-cyber-muted leading-relaxed">{children}</div>
}

/** Score out of 100 as a labelled horizontal meter. */
export function ScoreMeter({ score, label }: { score: number; label: string }) {
  const tone = score >= 80 ? 'bg-cyber-safe' : score >= 50 ? 'bg-cyber-warning' : 'bg-cyber-danger'
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-cyber-muted uppercase tracking-wider">{label}</span>
        <span className="font-mono text-2xl font-bold text-cyber-text">{score.toFixed(0)}<span className="text-sm text-cyber-muted">/100</span></span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-cyber-border/50 overflow-hidden" role="meter" aria-valuemin={0}
        aria-valuemax={100} aria-valuenow={Math.round(score)} aria-label={label}>
        <div className={`h-full ${tone} rounded-full`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
    </div>
  )
}

/** Stacked bar of control statuses, with a legend so colour is never the only cue. */
export function StatusBreakdown({ counts }: { counts: Partial<Record<ControlStatus, number>> }) {
  const { t } = useTranslation()
  const order: ControlStatus[] = ['pass', 'evidenced', 'partial', 'fail', 'needs_evidence', 'evidence_expired', 'no_data', 'not_applicable']
  const colour: Record<ControlStatus, string> = {
    pass: 'bg-cyber-safe', evidenced: 'bg-cyber-safe/60', partial: 'bg-cyber-warning', fail: 'bg-cyber-danger',
    needs_evidence: 'bg-cyber-accent/50', evidence_expired: 'bg-cyber-warning/50', no_data: 'bg-cyber-muted/40',
    not_applicable: 'bg-cyber-border',
  }
  const total = order.reduce((s, k) => s + (counts[k] ?? 0), 0) || 1
  return (
    <div>
      <div className="flex h-2 rounded-full overflow-hidden bg-cyber-border/40" aria-hidden="true">
        {order.map(k => (counts[k] ?? 0) > 0 && (
          <div key={k} className={colour[k]} style={{ width: `${((counts[k] ?? 0) / total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
        {order.filter(k => (counts[k] ?? 0) > 0).map(k => (
          <li key={k} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex items-center gap-1.5 text-cyber-muted">
              <span className={`w-2 h-2 rounded-sm ${colour[k]}`} aria-hidden="true" />{t(`gov.cstatus.${k}`)}
            </span>
            <span className="font-mono text-cyber-text">{counts[k]}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Sparkline({ points, label }: { points: number[]; label: string }) {
  if (points.length < 2) return null
  const w = 120, h = 28
  const min = Math.min(...points, 0), max = Math.max(...points, 100)
  const xy = points.map((p, i) => `${(i / (points.length - 1)) * w},${h - ((p - min) / (max - min || 1)) * h}`)
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label} className="text-cyber-accent">
      <polyline points={xy.join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

/** Renders a check-result item (a failing user, device, repo...) as compact key: value pairs. */
export function ItemRow({ item }: { item: Record<string, unknown> }) {
  const entries = Object.entries(item).filter(([, v]) => v !== null && v !== undefined && v !== '')
  return (
    <li className="py-1.5 border-b border-cyber-border/30 last:border-0 text-sm flex flex-wrap gap-x-4 gap-y-0.5">
      {entries.map(([k, v]) => (
        <span key={k} className="min-w-0 break-all">
          <span className="text-cyber-muted">{k}: </span>
          <span className="font-mono text-cyber-text">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
        </span>
      ))}
    </li>
  )
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-cyber-text">{label}</label>
      {children}
      {hint && <p className="text-xs text-cyber-muted leading-relaxed">{hint}</p>}
    </div>
  )
}

export function RunStatus({ status }: { status: string }) {
  const { t } = useTranslation()
  const style = { ok: 'badge-safe', partial: 'badge-warn', error: 'badge-danger', running: 'badge-info' }[status] ?? 'gov-badge-muted'
  return <span className={`${style} gov-badge`}>{t(`gov.run.${status}`)}</span>
}
