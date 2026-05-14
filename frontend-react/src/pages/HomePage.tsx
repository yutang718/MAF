import { Link } from 'react-router-dom'

const modules = [
  {
    name: 'Prompt Analysis',
    desc: 'Adversarial input detection via 3-model ensemble (ProtectAI + HikmaAI + Meta Prompt-Guard)',
    to: '/prompt-injection',
    metrics: ['3 Models', '100+ Languages', '3-Class Detection'],
    accent: 'border-cyber-accent/20 hover:border-cyber-accent/40',
    dot: 'bg-cyber-accent',
  },
  {
    name: 'PII Scanner',
    desc: 'Entity recognition and data masking powered by Microsoft Presidio',
    to: '/pii-detection',
    metrics: ['8+ Entity Types', 'SEA Region', 'Real-time'],
    accent: 'border-cyber-green/20 hover:border-cyber-green/40',
    dot: 'bg-cyber-green',
  },
  {
    name: 'Compliance Engine',
    desc: 'Islamic principles and Halal requirement verification for LLM outputs',
    to: '/islamic-compliance',
    metrics: ['EN / AR', 'Rule-based', 'Configurable'],
    accent: 'border-cyber-purple/20 hover:border-cyber-purple/40',
    dot: 'bg-cyber-purple',
  },
]

export default function HomePage() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="panel">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-cyber-text">AI Security Platform</h1>
            <p className="text-base text-cyber-muted mt-2 max-w-2xl leading-relaxed">
              Multi-layered security framework for LLM applications — combining prompt injection detection,
              PII masking, and compliance verification in a unified API.
            </p>
          </div>
          <span className="text-xs text-cyber-muted bg-cyber-surface-light px-2.5 py-1 rounded-md font-mono">v1.0.0</span>
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid grid-cols-3 gap-5">
        {modules.map((m) => (
          <Link key={m.to} to={m.to}
            className={`panel-sm group transition-all duration-200 ${m.accent}`}>
            <div className="flex items-center gap-2.5 mb-3">
              <span className={`w-2 h-2 rounded-full ${m.dot}`} />
              <h3 className="text-base font-semibold text-cyber-text">{m.name}</h3>
            </div>
            <p className="text-sm text-cyber-muted leading-relaxed mb-4">{m.desc}</p>
            <div className="flex flex-wrap gap-2">
              {m.metrics.map((metric) => (
                <span key={metric} className="text-xs font-medium text-cyber-muted bg-cyber-bg px-2 py-0.5 rounded">
                  {metric}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard value="3" label="Detection Models" />
        <StatCard value="100+" label="Languages" />
        <StatCard value="3" label="Threat Classes" />
        <StatCard value="8+" label="PII Entity Types" />
        <StatCard value="<50ms" label="Avg Latency" />
      </div>

      {/* Architecture Tables */}
      <div className="grid grid-cols-2 gap-5">
        <div className="panel-sm">
          <h3 className="text-sm font-semibold text-cyber-muted uppercase tracking-wider mb-4">Detection Pipeline</h3>
          <table className="w-full">
            <thead><tr>
              <th className="table-header">Module</th>
              <th className="table-header">Model</th>
              <th className="table-header">Runtime</th>
            </tr></thead>
            <tbody>
              <Row cells={['Prompt (EN)', 'ProtectAI DeBERTa v3', 'PyTorch']} />
              <Row cells={['Prompt (Multilingual)', 'HikmaAI mDeBERTa v3', 'ONNX']} />
              <Row cells={['Prompt (3-Class)', 'Meta Prompt-Guard-86M', 'PyTorch']} />
              <Row cells={['PII', 'Presidio + spaCy', 'CPU']} />
              <Row cells={['Compliance', 'Rule Engine', 'CPU']} />
            </tbody>
          </table>
        </div>
        <div className="panel-sm">
          <h3 className="text-sm font-semibold text-cyber-muted uppercase tracking-wider mb-4">Infrastructure</h3>
          <table className="w-full">
            <thead><tr>
              <th className="table-header">Layer</th>
              <th className="table-header">Technology</th>
            </tr></thead>
            <tbody>
              <Row cells={['API Gateway', 'FastAPI + Uvicorn']} />
              <Row cells={['ML Inference', 'PyTorch + ONNX Runtime']} />
              <Row cells={['NLP Pipeline', 'Transformers + spaCy']} />
              <Row cells={['Frontend', 'React + TailwindCSS']} />
              <Row cells={['Orchestration', 'Docker Compose']} />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
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
