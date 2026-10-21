import { useState } from 'react'
import { Link } from 'react-router-dom'
import { govApi } from '../../api/governance'
import { useTranslation } from '../../i18n/context'
import type { PostureDomain, PostureItem, PostureStatus, Severity, SlaMetrics } from '../../types/governance'
import { useGovAuth } from '../authState'
import { formatTime, useL10n, useLoad } from '../hooks'
import { CheckStatusBadge, ErrorPanel, Loading, PageHeader, SeverityBadge } from '../ui'

const SOURCES = ['all', 'gitlab', 'm365'] as const
type Show = 'problems' | 'all'

export default function PosturePage() {
  const { t } = useTranslation()
  const { can } = useGovAuth()
  const { data, error, loading, reload } = useLoad(() => govApi.posture(), [])
  const [source, setSource] = useState<(typeof SOURCES)[number]>('all')
  const [show, setShow] = useState<Show>('problems')

  if (loading && !data) return <Loading />
  if (error) return <ErrorPanel message={error} onRetry={reload} />
  if (!data) return null

  const t_ = data.totals
  const noSources = data.domains.every(d => d.items.every(i => i.status === 'no_source' || i.type === 'rule'))
  const domains = data.domains.filter(d => source === 'all' || d.source === source)

  return (
    <div className="space-y-6">
      <PageHeader title={t('gov.posture.title')} subtitle={t('gov.posture.subtitle')} />

      {noSources && (
        <div className="panel border-cyber-accent/30 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[15px] font-semibold text-cyber-text">{t('gov.posture.setupTitle')}</p>
            <p className="text-sm text-cyber-muted mt-1 leading-relaxed max-w-2xl">{t('gov.posture.setupBody')}</p>
          </div>
          {can('admin') && <Link to="/governance/connectors" className="btn-primary">{t('gov.overview.setupAction')}</Link>}
        </div>
      )}

      <dl className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {([
          ['fail', t('gov.posture.kpi.failing'), 'text-cyber-danger'],
          ['open', t('gov.posture.kpi.open'), 'text-cyber-text'],
          ['overdue', t('gov.posture.kpi.overdue'), 'text-cyber-danger'],
          ['new', t('gov.posture.kpi.new', { n: data.period_days }), 'text-cyber-warning'],
          ['resolved', t('gov.posture.kpi.resolved', { n: data.period_days }), 'text-cyber-safe'],
        ] as const).map(([k, label, tone]) => (
          <div key={k} className="panel-sm py-4">
            <dt className="text-xs text-cyber-muted">{label}</dt>
            <dd className={`font-mono text-2xl font-bold mt-1 ${(t_[k] ?? 0) > 0 ? tone : 'text-cyber-text'}`}>{t_[k] ?? 0}</dd>
          </div>
        ))}
      </dl>

      <div className="flex items-center gap-3 flex-wrap">
        <div role="tablist" aria-label={t('gov.posture.source')} className="flex items-center gap-1 p-1 bg-cyber-surface/40 rounded-lg border border-cyber-border/40">
          {SOURCES.map(s => (
            <button key={s} role="tab" aria-selected={source === s} onClick={() => setSource(s)}
              className={`tab-btn ${source === s ? 'tab-btn-active' : ''}`}>
              {s === 'all' ? t('gov.posture.allSources') : t(`gov.kind.${s}`)}
            </button>
          ))}
        </div>
        <label htmlFor="posture-show" className="sr-only">{t('gov.checks.show')}</label>
        <select id="posture-show" value={show} onChange={e => setShow(e.target.value as Show)} className="gov-select">
          <option value="problems">{t('gov.posture.showProblems')}</option>
          <option value="all">{t('gov.posture.showAll')}</option>
        </select>
        <span className="text-xs text-cyber-muted">{t('gov.posture.slaLegend', {
          e: data.sla.exploited, c: data.sla.critical, h: data.sla.high, m: data.sla.medium, l: data.sla.low })}</span>
      </div>

      {domains.map(d => <DomainSection key={d.id} domain={d} show={show} />)}
    </div>
  )
}

const PROBLEM = new Set<PostureStatus>(['fail', 'partial', 'error'])

function DomainSection({ domain, show }: { domain: PostureDomain; show: Show }) {
  const { t } = useTranslation()
  const l = useL10n()
  const [open, setOpen] = useState<string | null>(null)
  const items = domain.items.filter(i => show === 'all' || PROBLEM.has(i.status) || i.open > 0)
  return (
    <section className="panel-sm p-0 overflow-hidden" aria-labelledby={`dom-${domain.id}`}>
      <div className="px-5 py-3 border-b border-cyber-border/40 flex items-center justify-between gap-3 flex-wrap">
        <h2 id={`dom-${domain.id}`} className="text-[15px] font-semibold text-cyber-text">{l(domain.name)}</h2>
        <p className="text-xs text-cyber-muted">
          {t('gov.posture.domainStats', { failing: domain.failing, open: domain.open, overdue: domain.overdue })}
        </p>
      </div>
      {domain.id === 'vuln' && <VulnSla />}
      {items.length === 0 ? (
        <p className="px-5 py-4 text-sm text-cyber-muted">{t('gov.posture.domainClean')}</p>
      ) : (
        <ul className="divide-y divide-cyber-border/40">
          {items.map(i => (
            <li key={i.code}>
              <button className="w-full text-left px-5 py-3 flex items-center gap-3 flex-wrap hover:bg-cyber-accent/[0.04]"
                aria-expanded={open === i.code} onClick={() => setOpen(open === i.code ? null : i.code)}>
                <span className="font-mono text-xs text-cyber-muted w-20 flex-shrink-0">{i.code}</span>
                <span className="flex-1 min-w-[220px]">
                  <span className="block text-sm text-cyber-text">{l(i.title)}</span>
                  {i.summary && <span className="block text-xs text-cyber-muted mt-0.5">{l(i.summary)}</span>}
                </span>
                <SeverityBadge severity={i.severity} />
                <ItemStatus item={i} />
                <span className="text-xs text-cyber-muted w-40 text-right">
                  {i.open > 0 && t('gov.posture.openCount', { n: i.open })}
                  {i.overdue > 0 && <span className="text-cyber-danger"> · {t('gov.posture.overdueCount', { n: i.overdue })}</span>}
                </span>
              </button>
              {open === i.code && <ItemDetail item={i} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function ItemStatus({ item }: { item: PostureItem }) {
  const { t } = useTranslation()
  if (item.status === 'no_source') return <span className="gov-badge-muted gov-badge">{t('gov.checks.noConnector')}</span>
  if (item.type === 'rule') {
    return item.open
      ? <span className="badge-danger gov-badge">{t('gov.posture.openAlerts', { n: item.open })}</span>
      : <span className="badge-safe gov-badge">{t('gov.posture.noAlerts')}</span>
  }
  return <CheckStatusBadge status={item.status} />
}

function ItemDetail({ item }: { item: PostureItem }) {
  const { t } = useTranslation()
  if (item.type === 'rule') {
    return (
      <div className="px-5 pb-4 text-sm">
        <Link to={`/governance/alerts?rule=${encodeURIComponent(item.id)}`} className="text-cyber-accent hover:underline">
          {t('gov.posture.viewAlerts')}
        </Link>
      </div>
    )
  }
  return <FindingsTable checkId={item.id} sla={item.sla} />
}

const PAGE = 50

function FindingsTable({ checkId, sla }: { checkId: string; sla: boolean }) {
  const { t, lang } = useTranslation()
  const [overdue, setOverdue] = useState(false)
  const [resolved, setResolved] = useState(false)
  const [offset, setOffset] = useState(0)
  const { data, error, loading, reload } = useLoad(
    () => govApi.findings(checkId, { overdue, resolved, offset, limit: PAGE }), [checkId, overdue, resolved, offset])

  return (
    <div className="px-5 pb-4 space-y-3 border-t border-cyber-border/30 pt-3 bg-cyber-bg/30">
      <div className="flex items-center gap-4 flex-wrap text-sm">
        <label className="flex items-center gap-2 text-cyber-text">
          <input type="checkbox" checked={overdue} onChange={e => { setOverdue(e.target.checked); setOffset(0) }} />
          {t('gov.posture.overdueOnly')}
        </label>
        <label className="flex items-center gap-2 text-cyber-text">
          <input type="checkbox" checked={resolved} onChange={e => { setResolved(e.target.checked); setOffset(0) }} />
          {t('gov.posture.includeResolved')}
        </label>
        {sla && <span className="text-xs text-cyber-muted">{t('gov.posture.slaGraded')}</span>}
      </div>
      {loading && !data && <p className="text-sm text-cyber-muted">{t('gov.loading')}</p>}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && data.total === 0 && <p className="text-sm text-cyber-muted">{t('gov.posture.noFindings')}</p>}
      {data && data.total > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr>
              <th className="table-header py-2">{t('gov.posture.col.item')}</th>
              <th className="table-header py-2">{t('gov.posture.col.severity')}</th>
              <th className="table-header py-2">{t('gov.posture.col.firstSeen')}</th>
              <th className="table-header py-2">{t('gov.posture.col.due')}</th>
              <th className="table-header py-2">{t('gov.posture.col.state')}</th>
            </tr></thead>
            <tbody>
              {data.items.map(f => (
                <tr key={f.id} className="table-row-hover align-top">
                  <td className="table-cell py-2 text-sm">
                    <span className="text-cyber-text break-all">{f.label || f.key}</span>
                    {f.exploited && <span className="badge-danger gov-badge ml-2">{t('gov.posture.exploited')}</span>}
                    {f.reopened > 0 && <span className="gov-badge-muted gov-badge ml-2">{t('gov.posture.reopened', { n: f.reopened })}</span>}
                  </td>
                  <td className="table-cell py-2"><SeverityBadge severity={f.severity as Severity} /></td>
                  <td className="table-cell py-2 text-xs whitespace-nowrap">
                    {formatTime(f.first_seen, lang)}<div className="text-cyber-muted">{t('gov.posture.ageDays', { n: f.age_days })}</div>
                  </td>
                  <td className={`table-cell py-2 text-xs whitespace-nowrap ${f.overdue ? 'text-cyber-danger font-semibold' : ''}`}>
                    {formatTime(f.due_at, lang).slice(0, 10)}
                  </td>
                  <td className="table-cell py-2 text-xs whitespace-nowrap">
                    {f.resolved_at ? <span className="text-cyber-safe">{t('gov.posture.fixedOn', { date: formatTime(f.resolved_at, lang).slice(0, 10) })}</span>
                      : f.overdue ? <span className="badge-danger gov-badge">{t('gov.posture.overdue')}</span>
                        : <span className="badge-warn gov-badge">{t('gov.posture.withinSla')}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.total > PAGE && (
            <div className="flex items-center justify-between text-sm text-cyber-muted pt-2">
              <span>{t('gov.alerts.range', { from: offset + 1, to: Math.min(offset + PAGE, data.total), total: data.total })}</span>
              <span className="flex gap-2">
                <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>{t('gov.prev')}</button>
                <button className="btn-ghost text-sm px-3 py-1.5" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>{t('gov.next')}</button>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const SLA_ROWS: (keyof SlaMetrics['by_severity'])[] = ['exploited', 'critical', 'high', 'medium', 'low']

function VulnSla() {
  const { t } = useTranslation()
  const { data } = useLoad(() => govApi.slaMetrics(), [])
  if (!data || SLA_ROWS.every(k => !data.by_severity[k].open && !data.by_severity[k].resolved)) return null
  return (
    <div className="px-5 py-3 border-b border-cyber-border/40 overflow-x-auto">
      <p className="text-xs text-cyber-muted mb-2">{t('gov.posture.vulnSlaTitle', { n: data.window_days })}</p>
      <table className="w-full text-sm">
        <thead><tr className="text-xs text-cyber-muted">
          <th className="text-left font-medium py-1">{t('gov.posture.col.class')}</th>
          <th className="text-right font-medium py-1">{t('gov.posture.col.slaDays')}</th>
          <th className="text-right font-medium py-1">{t('gov.posture.col.open')}</th>
          <th className="text-right font-medium py-1">{t('gov.posture.col.openOverdue')}</th>
          <th className="text-right font-medium py-1">{t('gov.posture.col.withinSla')}</th>
          <th className="text-right font-medium py-1">MTTR</th>
        </tr></thead>
        <tbody className="font-mono">
          {SLA_ROWS.map(k => {
            const r = data.by_severity[k]
            return (
              <tr key={k} className="border-t border-cyber-border/30">
                <td className="py-1.5 font-sans">{t(`gov.posture.sla.${k}`)}</td>
                <td className="py-1.5 text-right">{r.sla_days}</td>
                <td className="py-1.5 text-right">{r.open}</td>
                <td className={`py-1.5 text-right ${r.open_overdue ? 'text-cyber-danger' : ''}`}>{r.open_overdue}</td>
                <td className="py-1.5 text-right">{r.within_sla_pct === null ? '—' : `${r.within_sla_pct}%`}</td>
                <td className="py-1.5 text-right">{r.mttr_days === null ? '—' : t('gov.posture.days', { n: r.mttr_days })}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
