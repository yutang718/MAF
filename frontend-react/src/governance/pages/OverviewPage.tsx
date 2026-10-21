import { Link } from 'react-router-dom'
import { govApi } from '../../api/governance'
import { useTranslation } from '../../i18n/context'
import type { Severity } from '../../types/governance'
import { useGovAuth } from '../authState'
import { Empty, ErrorPanel, Loading, PageHeader, ScoreMeter, SeverityBadge, Sparkline, StatusBreakdown } from '../ui'
import { formatAgo, useL10n, useLoad } from '../hooks'

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

export default function OverviewPage() {
  const { t } = useTranslation()
  const l = useL10n()
  const { can } = useGovAuth()
  const { data, error, loading, reload } = useLoad(() => govApi.overview(), [])

  if (loading && !data) return <Loading />
  if (error) return <ErrorPanel message={error} onRetry={reload} />
  if (!data) return null

  const noConnectors = data.connectors.length === 0

  return (
    <div className="space-y-6">
      <PageHeader title={t('gov.overview.title')} subtitle={t('gov.overview.subtitle')} />

      {noConnectors && (
        <div className="panel border-cyber-accent/30 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[15px] font-semibold text-cyber-text">{t('gov.overview.setupTitle')}</p>
            <p className="text-sm text-cyber-muted mt-1 leading-relaxed max-w-2xl">{t('gov.overview.setupBody')}</p>
          </div>
          {can('admin') && <Link to="/governance/connectors" className="btn-primary">{t('gov.overview.setupAction')}</Link>}
        </div>
      )}

      <section aria-labelledby="gov-fw-heading">
        <h2 id="gov-fw-heading" className="text-sm font-semibold text-cyber-muted uppercase tracking-wider mb-3">
          {t('gov.overview.frameworks')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {data.frameworks.map(fw => (
            <Link key={fw.id} to={`/governance/frameworks/${fw.id}`}
              className="panel-sm block hover:border-cyber-accent/40 transition-colors space-y-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-[15px] font-semibold text-cyber-text">{l(fw.name)}</h3>
                <Sparkline points={(fw.trend ?? []).map(p => p.score)} label={t('gov.overview.trend')} />
              </div>
              <ScoreMeter score={fw.score} label={t('gov.overview.readiness')} />
              <StatusBreakdown counts={fw.counts} />
              <p className="text-xs text-cyber-muted">
                {t('gov.overview.coverage', { automated: fw.automated, applicable: fw.applicable })}
              </p>
            </Link>
          ))}
        </div>
        <p className="text-xs text-cyber-muted mt-3 leading-relaxed max-w-3xl">{t('gov.overview.disclaimer')}</p>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <section className="panel-sm lg:col-span-3 space-y-3" aria-labelledby="gov-alerts-heading">
          <div className="flex items-center justify-between">
            <h2 id="gov-alerts-heading" className="text-[15px] font-semibold text-cyber-text">{t('gov.overview.openAlerts')}</h2>
            <Link to="/governance/alerts" className="text-sm text-cyber-accent hover:underline">{t('gov.overview.viewAll')}</Link>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {SEVERITIES.map(s => (
              <Link key={s} to={`/governance/alerts?severity=${s}`}
                className="rounded-lg border border-cyber-border/50 px-3 py-2 hover:border-cyber-accent/40 transition-colors">
                <div className="font-mono text-xl font-bold text-cyber-text">{data.open_alerts[s]}</div>
                <div className="text-xs text-cyber-muted mt-0.5">{t(`gov.severity.${s}`)}</div>
              </Link>
            ))}
          </div>
          {data.recent_alerts.length === 0 ? (
            <p className="text-sm text-cyber-muted">{t('gov.overview.noAlerts')}</p>
          ) : (
            <ul className="divide-y divide-cyber-border/40">
              {data.recent_alerts.map(a => (
                <li key={a.id} className="py-2 flex items-center gap-3">
                  <SeverityBadge severity={a.severity} />
                  <Link to={`/governance/alerts?id=${a.id}`} className="text-sm text-cyber-text hover:text-cyber-accent truncate flex-1">
                    {l(a.title)}
                  </Link>
                  <span className="text-xs text-cyber-muted whitespace-nowrap">{formatAgo(a.occurred_at, t)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel-sm lg:col-span-2 space-y-3" aria-labelledby="gov-sources-heading">
          <div className="flex items-center justify-between">
            <h2 id="gov-sources-heading" className="text-[15px] font-semibold text-cyber-text">{t('gov.overview.sources')}</h2>
            <Link to="/governance/connectors" className="text-sm text-cyber-accent hover:underline">{t('gov.overview.manage')}</Link>
          </div>
          {noConnectors ? <Empty>{t('gov.overview.noSources')}</Empty> : (
            <ul className="divide-y divide-cyber-border/40">
              {data.connectors.map(c => (
                <li key={c.id} className="py-2 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-cyber-text truncate">{c.name}</p>
                    <p className="text-xs text-cyber-muted">{t(`gov.kind.${c.kind}`)} · {c.running ? t('gov.running') : formatAgo(c.last_run_at, t)}</p>
                  </div>
                  <RunStatus status={c.enabled ? c.last_status : 'disabled'} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

export function RunStatus({ status }: { status: string }) {
  const { t } = useTranslation()
  const style = { ok: 'badge-safe', partial: 'badge-warn', error: 'badge-danger', running: 'badge-info' }[status] ?? 'gov-badge-muted'
  return <span className={`${style} gov-badge`}>{t(`gov.run.${status}`)}</span>
}
