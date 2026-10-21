import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useTranslation } from '../i18n/context'
import { useHealth } from '../health/state'
import { useMafGuardName } from '../utils/mafGuardVersion'

export default function HomePage() {
  const { t } = useTranslation()
  const { status, health } = useHealth()
  const statusView = {
    checking: { dot: 'bg-cyber-muted', text: 'text-cyber-muted', label: t('home.statusChecking') },
    online: { dot: 'bg-cyber-safe', text: 'text-cyber-safe', label: t('nav.online') },
    degraded: { dot: 'bg-cyber-warning', text: 'text-cyber-warning', label: t('home.statusDegraded') },
    offline: { dot: 'bg-cyber-danger', text: 'text-cyber-danger', label: t('home.statusOffline') },
  }[status]
  const { lang } = useTranslation()
  const { checkedAt } = useHealth()
  const mafName = useMafGuardName()
  const modelsLoaded = health?.components.guard_models.models_count
  const modelNames: Record<string, string> = {
    proventra: 'Proventra mDeBERTa v3', modernguard: 'ModernGuard-1', wolfdefender: 'Wolf Defender v2', mafguard: mafName,
  }
  const loadedModels = (health?.components.guard_models.loaded_models ?? []).map(k => modelNames[k] ?? k)
  const pii = health?.components.pii_detector
  const checkedTime = checkedAt?.toLocaleTimeString(lang === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' }) ?? ''
  const lastRun = lastBenchmarkRun()

  const modules = [
    {
      name: t('home.promptInjection'),
      desc: t('home.promptInjectionDesc'),
      to: '/prompt-injection',
      stats: { models: '4', accuracy: '99.6%', languages: '100+', latency: '~260ms' } as Record<string, string>,
      statKeys: ['models', 'accuracy', 'languages', 'latency'],
      accent: 'border-cyber-accent/20 hover:border-cyber-accent/50',
      glow: 'hover:shadow-glow-sm',
    },
    {
      name: t('home.piiScanner'),
      desc: t('home.piiScannerDesc'),
      to: '/pii-detection',
      stats: { entities: '8+', precision: '97.2%', region: 'SEA', mode: 'Real-time' } as Record<string, string>,
      statKeys: ['entities', 'precision', 'region', 'mode'],
      accent: 'border-cyber-green/20 hover:border-cyber-green/50',
      glow: 'hover:shadow-glow-green',
    },
    {
      name: t('home.complianceEngine'),
      desc: t('home.complianceEngineDesc'),
      to: '/islamic-compliance',
      stats: { rules: '24', languages: 'EN/AR', coverage: 'Halal', mode: 'Configurable' } as Record<string, string>,
      statKeys: ['rules', 'languages', 'coverage', 'mode'],
      accent: 'border-cyber-purple/20 hover:border-cyber-purple/50',
      glow: '',
    },
  ]

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-cyber-text">{t('home.title')}</h1>

      {/* What an operator checks first: is it up, what is loaded, what ran last */}
      <section aria-labelledby="ops-heading" className="panel">
        <h2 id="ops-heading" className="text-sm font-semibold text-cyber-text mb-4">{t('home.ops.title')}</h2>
        <dl className="grid grid-cols-4 gap-6">
          <OpsItem label={t('home.ops.api')}
            sub={health ? t('home.ops.apiSub', { version: health.version, time: checkedTime }) : status === 'offline' ? t('home.ops.apiDown', { time: checkedTime }) : ''}>
            <span className="inline-flex items-center gap-2" role="status">
              <span className={`w-2.5 h-2.5 rounded-full ${statusView.dot}`} aria-hidden="true" />
              <span className={statusView.text}>{statusView.label}</span>
            </span>
          </OpsItem>
          <OpsItem label={t('home.ops.models')}
            sub={loadedModels.length ? loadedModels.join(' · ') : health ? t('home.ops.noneLoaded') : t('home.ops.unknown')}>
            <span className="font-mono">{modelsLoaded ?? '—'}</span>
          </OpsItem>
          <OpsItem label={t('home.ops.pii')}
            sub={pii ? t('home.ops.piiSub', { total: pii.rules_count }) : t('home.ops.unknown')}>
            <span className="font-mono">{pii?.rules_enabled ?? '—'}</span>
          </OpsItem>
          <OpsItem label={t('home.ops.lastRun')}
            sub={lastRun ? t('home.ops.lastRunSub', { status: lastRun.status, models: lastRun.models.length }) : t('home.ops.noRuns')}>
            {lastRun
              ? <Link to="/prompt-injection" className="text-cyber-accent hover:underline break-all">{lastRun.dataset_id}</Link>
              : <span className="text-cyber-muted">—</span>}
          </OpsItem>
        </dl>
      </section>

      {/* Module Cards */}
      <div className="grid grid-cols-3 gap-5">
        {modules.map((m) => (
          <Link key={m.to} to={m.to}
            className={`panel-sm group transition-all duration-300 ${m.accent} ${m.glow}`}>
            <h2 className="text-lg font-bold text-cyber-text mb-2">{m.name}</h2>
            <p className="text-sm text-cyber-muted leading-relaxed mb-4">{m.desc}</p>
            <div className="grid grid-cols-2 gap-3">
              {m.statKeys.map((key) => (
                <div key={key}>
                  <div className="text-lg font-mono font-bold text-cyber-text">{(m.stats as Record<string, string>)[key]}</div>
                  <div className="text-xs text-cyber-muted capitalize">{t(`home.stat.${key}`)}</div>
                </div>
              ))}
            </div>
          </Link>
        ))}
      </div>

      {/* Model Benchmark Comparison */}
      <BenchmarkSection t={t} />

      {/* Tech Stack */}
      <TechStackSection t={t} />
    </div>
  )
}

function BenchmarkSection({ t }: { t: (key: string) => string }) {
  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-cyber-text">{t('home.benchmarks')}</h2>
      </div>
      <div className="grid grid-cols-4 gap-5">
        <BenchmarkCard
          name="EVYD Defender V4"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.882, color: 'bg-cyber-accent' },
            { label: t('home.benchmark.recall'), value: 1.000, color: 'bg-cyber-accent' },
            { label: t('home.benchmark.precision'), value: 0.789, color: 'bg-cyber-accent' },
          ]}
          meta={`mmBERT-base · ${t('home.benchmark.fineTuned')} · FPR 0.6%`}
        />
        <BenchmarkCard
          name="Proventra mDeBERTa v3"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.571, color: 'bg-cyber-green' },
            { label: t('home.benchmark.recall'), value: 0.667, color: 'bg-cyber-green' },
            { label: t('home.benchmark.precision'), value: 0.500, color: 'bg-cyber-green' },
          ]}
          meta="mDeBERTa-v3-base · 100+ Languages · FPR 1.5%"
        />
        <BenchmarkCard
          name="ModernGuard-1"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.471, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.recall'), value: 0.800, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.precision'), value: 0.333, color: 'bg-cyber-purple' },
          ]}
          meta="mmBERT-base · 1080 Languages · 8k ctx · FPR 3.5%"
        />
        <BenchmarkCard
          name="Wolf Defender v2"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.474, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.recall'), value: 0.600, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.precision'), value: 0.391, color: 'bg-cyber-purple' },
          ]}
          meta="mmBERT-base · Multilingual · FPR 2.1%"
        />
      </div>
      <p className="text-xs text-cyber-muted mt-3">{t('home.benchmark.note')}</p>
    </div>
  )
}

function TechStackSection({ t }: { t: (key: string) => string }) {
  const mafName = useMafGuardName()
  return (
    <div className="grid grid-cols-2 gap-5">
      <div className="panel-sm">
        <h3 className="text-sm font-bold text-cyber-muted uppercase tracking-wider mb-4">{t('home.detectionPipeline')}</h3>
        <table className="w-full">
          <thead><tr>
            <th className="table-header">{t('home.table.module')}</th>
            <th className="table-header">{t('home.table.model')}</th>
            <th className="table-header">{t('home.table.runtime')}</th>
            <th className="table-header">{t('home.table.size')}</th>
          </tr></thead>
          <tbody>
            <Row cells={[t('home.pipeline.promptFineTuned'), `${mafName} (mmBERT)`, 'PyTorch', '1.2 GB']} />
            <Row cells={[t('home.pipeline.promptMulti'), 'Proventra mDeBERTa v3', 'PyTorch', '300 MB']} />
            <Row cells={[t('home.pipeline.promptMulti'), 'ModernGuard-1 · Wolf Defender v2', 'PyTorch', '1.2 GB ×2']} />
            <Row cells={[t('home.pipeline.pii'), 'Presidio + spaCy', 'CPU', '~200 MB']} />
            <Row cells={[t('home.pipeline.compliance'), 'Rule Engine', 'CPU', '<1 MB']} />
          </tbody>
        </table>
      </div>
      <div className="panel-sm">
        <h3 className="text-sm font-bold text-cyber-muted uppercase tracking-wider mb-4">{t('home.infrastructure')}</h3>
        <table className="w-full">
          <thead><tr>
            <th className="table-header">{t('home.table.layer')}</th>
            <th className="table-header">{t('home.table.technology')}</th>
            <th className="table-header">{t('home.table.version')}</th>
          </tr></thead>
          <tbody>
            <Row cells={[t('home.infra.apiGateway'), 'FastAPI + Uvicorn', '0.104']} />
            <Row cells={[t('home.infra.mlRuntime'), 'PyTorch', '2.x']} />
            <Row cells={[t('home.infra.nlp'), 'Transformers + spaCy', '4.49']} />
            <Row cells={[t('home.infra.frontend'), 'React + Vite + Tailwind', '19.x']} />
            <Row cells={[t('home.infra.orchestration'), 'Docker Compose', '2.x']} />
          </tbody>
        </table>
      </div>
    </div>
  )
}


function BenchmarkCard({ name, metrics, meta }: {
  name: string; metrics: { label: string; value: number; color: string }[]; meta: string
}) {
  return (
    <div className="panel-sm space-y-4">
      <div>
        <h3 className="text-base font-bold text-cyber-text">{name}</h3>
        <p className="text-xs text-cyber-muted mt-0.5">{meta}</p>
      </div>
      <div className="space-y-3">
        {metrics.map((m) => (
          <div key={m.label}>
            <div className="flex justify-between mb-1">
              <span className="text-sm text-cyber-muted">{m.label}</span>
              <span className="text-sm font-mono font-bold text-cyber-text">{(m.value * 100).toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-cyber-bg rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${m.color} transition-all duration-1000`}
                style={{ width: `${m.value * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Row({ cells }: { cells: string[] }) {
  return (
    <tr>
      {cells.map((c, i) => <td key={i} className="table-cell">{c}</td>)}
    </tr>
  )
}

function OpsItem({ label, sub, children }: { label: string; sub: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-cyber-muted">{label}</dt>
      <dd className="mt-1.5 text-lg font-semibold text-cyber-text">{children}</dd>
      {sub && <dd className="mt-1 text-xs text-cyber-muted leading-snug">{sub}</dd>}
    </div>
  )
}

/** Most recent run the Benchmark tab saved in this browser, if any. */
function lastBenchmarkRun(): { dataset_id: string; status: string; models: string[] } | null {
  try {
    const raw = localStorage.getItem('maf_benchmark_state')
    const run = raw ? JSON.parse(raw)?.runs?.[0] : null
    return run?.dataset_id ? run : null
  } catch {
    return null
  }
}
