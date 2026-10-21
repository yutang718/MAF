import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { govApi } from '../../api/governance'
import { useTranslation } from '../../i18n/context'
import type { ControlStatus } from '../../types/governance'
import { useGovAuth } from '../authState'
import { ControlStatusBadge, ErrorPanel, Loading, PageHeader, ScoreMeter, StatusBreakdown } from '../ui'
import { useL10n, useLoad } from '../hooks'

const FRAMEWORKS = ['iso27001', 'nist_csf', 'hipaa']
const FILTERS: ('all' | 'gaps' | ControlStatus)[] = ['all', 'gaps', 'fail', 'partial', 'needs_evidence', 'evidence_expired', 'no_data', 'pass', 'evidenced', 'not_applicable']
const GAPS = new Set<ControlStatus>(['fail', 'partial', 'needs_evidence', 'evidence_expired', 'no_data'])

export default function FrameworkPage() {
  const { t, lang } = useTranslation()
  const l = useL10n()
  const { can } = useGovAuth()
  const navigate = useNavigate()
  const { fw = 'iso27001' } = useParams()
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('gaps')
  const [query, setQuery] = useState('')
  const { data, error, loading, reload } = useLoad(() => govApi.framework(fw), [fw])

  const visible = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.controls.filter(c =>
      (filter === 'all' || (filter === 'gaps' ? GAPS.has(c.status) : c.status === filter)) &&
      (!q || c.id.toLowerCase().includes(q) || c.title.en.toLowerCase().includes(q) || c.title.zh.includes(q)))
  }, [data, filter, query])

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('gov.fw.title')}
        subtitle={t('gov.fw.subtitle')}
        actions={can('auditor') && (
          <a className="btn-ghost text-sm" href={govApi.reportUrl(fw, lang)} download>{t('gov.fw.export')}</a>
        )}
      />

      <div role="tablist" aria-label={t('gov.fw.choose')} className="flex items-center gap-1 p-1 bg-cyber-surface/40 rounded-lg border border-cyber-border/40 w-fit">
        {FRAMEWORKS.map(id => (
          <button key={id} role="tab" aria-selected={fw === id} onClick={() => navigate(`/governance/frameworks/${id}`)}
            className={`tab-btn ${fw === id ? 'tab-btn-active' : ''}`}>
            {t(`gov.fw.name.${id}`)}
          </button>
        ))}
      </div>

      {loading && !data && <Loading />}
      {error && <ErrorPanel message={error} onRetry={reload} />}
      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="panel-sm space-y-3">
              <ScoreMeter score={data.summary.score} label={t('gov.overview.readiness')} />
              <p className="text-xs text-cyber-muted leading-relaxed">{l(data.description)}</p>
            </div>
            <div className="panel-sm md:col-span-2">
              <StatusBreakdown counts={data.summary.counts} />
              <p className="text-xs text-cyber-muted mt-3">
                {t('gov.overview.coverage', { automated: data.summary.automated, applicable: data.summary.applicable })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <label className="sr-only" htmlFor="gov-control-filter">{t('gov.fw.filter')}</label>
            <select id="gov-control-filter" value={filter} onChange={e => setFilter(e.target.value as typeof filter)} className="gov-select">
              {FILTERS.map(f => (
                <option key={f} value={f}>
                  {f === 'all' ? t('gov.fw.filterAll') : f === 'gaps' ? t('gov.fw.filterGaps') : t(`gov.cstatus.${f}`)}
                </option>
              ))}
            </select>
            <label className="sr-only" htmlFor="gov-control-search">{t('gov.fw.search')}</label>
            <input id="gov-control-search" value={query} onChange={e => setQuery(e.target.value)}
              placeholder={t('gov.fw.search')} className="input-field max-w-xs py-2 text-sm" />
            <span className="text-sm text-cyber-muted">{t('gov.fw.showing', { n: visible.length, total: data.controls.length })}</span>
          </div>

          {data.groups.map(g => {
            const rows = visible.filter(c => c.group === g.id)
            if (!rows.length) return null
            return (
              <section key={g.id} className="panel-sm p-0 overflow-hidden" aria-labelledby={`grp-${g.id}`}>
                <h2 id={`grp-${g.id}`} className="px-5 py-3 text-sm font-semibold text-cyber-text border-b border-cyber-border/40">
                  {l(g.name)} <span className="text-cyber-muted font-normal">· {rows.length}</span>
                </h2>
                <table className="w-full">
                  <thead className="sr-only">
                    <tr><th>{t('gov.fw.col.control')}</th><th>{t('gov.fw.col.status')}</th><th>{t('gov.fw.col.basis')}</th></tr>
                  </thead>
                  <tbody>
                    {rows.map(c => (
                      <tr key={c.id} className="table-row-hover">
                        <td className="table-cell w-full">
                          <Link to={`/governance/frameworks/${fw}/controls/${encodeURIComponent(c.id)}`} className="group flex gap-3 items-baseline">
                            <span className="font-mono text-sm text-cyber-muted w-48 flex-shrink-0 whitespace-nowrap">{c.id}</span>
                            <span className="text-cyber-text group-hover:text-cyber-accent">{l(c.title)}</span>
                          </Link>
                        </td>
                        <td className="table-cell whitespace-nowrap"><ControlStatusBadge status={c.status} /></td>
                        <td className="table-cell whitespace-nowrap text-xs text-cyber-muted">
                          {basis(c, t)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )
          })}
          {visible.length === 0 && <div className="panel text-sm text-cyber-muted">{t('gov.fw.none')}</div>}
        </>
      )}
    </div>
  )
}

function basis(c: { mapped_checks: number; check_counts: Record<string, number | undefined>; evidence_current: number },
  t: (k: string, v?: Record<string, string | number>) => string) {
  const parts = []
  const graded = ['pass', 'partial', 'fail', 'accepted'].reduce((s, k) => s + (c.check_counts[k] ?? 0), 0)
  if (c.mapped_checks) parts.push(t('gov.fw.basisChecks', { n: graded, total: c.mapped_checks }))
  if (c.evidence_current) parts.push(t('gov.fw.basisEvidence', { n: c.evidence_current }))
  return parts.join(' · ') || t('gov.fw.basisNone')
}
