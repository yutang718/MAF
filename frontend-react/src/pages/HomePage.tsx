import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useTranslation } from '../i18n/context'

export default function HomePage() {
  const { t } = useTranslation()

  const modules = [
    {
      name: t('home.promptInjection'),
      desc: t('home.promptInjectionDesc'),
      to: '/prompt-injection',
      stats: { models: '3', accuracy: '99.9%', languages: '100+', latency: '45ms' } as Record<string, string>,
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
    <div className="space-y-8 bg-grid min-h-[calc(100vh-3.5rem)]">
      {/* Hero */}
      <div className="border-gradient rounded-xl">
        <div className="panel bg-cyber-surface/80">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-extrabold text-cyber-text text-glow">{t('home.title')}</h1>
              <p className="text-base text-cyber-muted mt-3 max-w-2xl leading-relaxed">
                {t('home.subtitle')}
              </p>
            </div>
            <div className="text-right">
              <div className="text-xs text-cyber-muted uppercase tracking-widest">{t('home.systemStatus')}</div>
              <div className="flex items-center gap-2 mt-1 justify-end">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse-glow" />
                <span className="text-sm text-emerald-400 font-semibold">{t('home.allOperational')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Live Stats Row */}
      <div className="grid grid-cols-6 gap-3">
        <AnimatedStat value={3} label={t('home.activeModels')} suffix="" />
        <AnimatedStat value={100} label={t('home.languages')} suffix="+" />
        <AnimatedStat value={99.9} label={t('home.jailbreakTPR')} suffix="%" decimal />
        <AnimatedStat value={30} label={t('home.testSamples')} suffix="" />
        <AnimatedStat value={45} label={t('home.avgLatency')} suffix="ms" />
        <AnimatedStat value={8} label={t('home.piiEntities')} suffix="+" />
      </div>

      {/* Module Cards */}
      <div className="grid grid-cols-3 gap-5">
        {modules.map((m) => (
          <Link key={m.to} to={m.to}
            className={`panel-sm group transition-all duration-300 ${m.accent} ${m.glow}`}>
            <h3 className="text-lg font-bold text-cyber-text mb-2">{m.name}</h3>
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
        <span className="badge-info">{t('home.modelsActive')}</span>
      </div>
      <div className="grid grid-cols-3 gap-5">
        <BenchmarkCard
          name="ProtectAI DeBERTa v3"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.815, color: 'bg-cyber-accent' },
            { label: t('home.benchmark.recall'), value: 0.997, color: 'bg-cyber-accent' },
            { label: t('home.benchmark.precision'), value: 0.952, color: 'bg-cyber-accent' },
          ]}
          meta="DeBERTa-v3-base · 184M params · English"
        />
        <BenchmarkCard
          name="HikmaAI mDeBERTa v3"
          metrics={[
            { label: t('home.benchmark.f1'), value: 0.854, color: 'bg-cyber-green' },
            { label: t('home.benchmark.recall'), value: 0.989, color: 'bg-cyber-green' },
            { label: t('home.benchmark.internalF1'), value: 0.990, color: 'bg-cyber-green' },
          ]}
          meta="mDeBERTa-v3-base · ONNX FP32 · 11 Languages"
        />
        <BenchmarkCard
          name="Meta Prompt-Guard-86M"
          metrics={[
            { label: t('home.benchmark.jailbreakTPR'), value: 0.999, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.injectionTPR'), value: 0.995, color: 'bg-cyber-purple' },
            { label: t('home.benchmark.auc'), value: 0.959, color: 'bg-cyber-purple' },
          ]}
          meta="mDeBERTa-v3-base · 86M params · 3-Class · 100+ Lang"
        />
      </div>
    </div>
  )
}

function TechStackSection({ t }: { t: (key: string) => string }) {
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
            <Row cells={[t('home.pipeline.promptEN'), 'ProtectAI DeBERTa v3', 'PyTorch', '1.5 GB']} />
            <Row cells={[t('home.pipeline.promptMulti'), 'HikmaAI mDeBERTa v3', 'ONNX', '350 MB']} />
            <Row cells={[t('home.pipeline.prompt3Class'), 'Meta Prompt-Guard-86M', 'PyTorch', '86 MB']} />
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
            <Row cells={[t('home.infra.mlRuntime'), 'PyTorch + ONNX Runtime', '2.2+']} />
            <Row cells={[t('home.infra.nlp'), 'Transformers + spaCy', '4.36+']} />
            <Row cells={[t('home.infra.frontend'), 'React + Vite + Tailwind', '19.x']} />
            <Row cells={[t('home.infra.orchestration'), 'Docker Compose', '2.x']} />
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AnimatedStat({ value, label, suffix, decimal }: { value: number; label: string; suffix: string; decimal?: boolean }) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    let start = 0
    const end = value
    const duration = 1200
    const steps = 40
    const increment = end / steps
    const timer = setInterval(() => {
      start += increment
      if (start >= end) {
        setDisplay(end)
        clearInterval(timer)
      } else {
        setDisplay(start)
      }
    }, duration / steps)
    return () => clearInterval(timer)
  }, [value])

  return (
    <div className="stat-card group">
      <div className="stat-value text-glow">
        {decimal ? display.toFixed(1) : Math.round(display)}{suffix}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function BenchmarkCard({ name, metrics, meta }: {
  name: string; metrics: { label: string; value: number; color: string }[]; meta: string
}) {
  return (
    <div className="panel-sm space-y-4">
      <div>
        <h4 className="text-base font-bold text-cyber-text">{name}</h4>
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
