import { useState, useEffect } from 'react'
import { detectIslamic, getRules } from '../api/islamic'
import type { IslamicDetectionResult, IslamicRulesResponse } from '../types/islamic'

const tabs = ['Compliance Check', 'Rule Configuration'] as const
type Tab = (typeof tabs)[number]

const samples = [
  'What is the best approach to Islamic finance and investment?',
  'Can you recommend some alcoholic beverages for a celebration?',
  'Explain the concept of Riba and why it is prohibited in Islam.',
  'Suggest pork-based recipes for dinner tonight.',
]

export default function IslamicCompliancePage() {
  const [activeTab, setActiveTab] = useState<Tab>('Compliance Check')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-cyber-text">Compliance Engine</h1>
        <p className="text-sm text-cyber-muted mt-0.5">
          Verify LLM outputs against Islamic principles, Halal requirements, and regional regulatory guidelines
        </p>
      </div>

      <div className="flex items-center gap-1 p-1 bg-cyber-surface/40 rounded-lg w-fit border border-cyber-border/40">
        {tabs.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'tab-btn-active' : ''}`}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'Compliance Check' && <ComplianceCheck />}
      {activeTab === 'Rule Configuration' && <RuleConfig />}
    </div>
  )
}

function ComplianceCheck() {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IslamicDetectionResult | null>(null)
  const [error, setError] = useState('')

  const run = async () => {
    if (!text.trim()) return
    setLoading(true); setError(''); setResult(null)
    try { setResult(await detectIslamic(text)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    setLoading(false)
  }

  return (
    <div className="grid grid-cols-5 gap-5">
      <div className="col-span-3 space-y-3">
        <textarea value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Enter text to verify compliance..."
          className="input-field h-40 resize-none" />
        <button onClick={run} disabled={loading || !text.trim()} className="btn-primary w-full">
          {loading ? 'Verifying...' : 'Check Compliance'}
        </button>
        <div className="space-y-1.5">
          <span className="text-xs text-cyber-muted uppercase tracking-wider">Sample Inputs</span>
          {samples.map((s, i) => (
            <button key={i} onClick={() => setText(s)}
              className="block w-full text-left text-sm text-cyber-muted/70 bg-cyber-surface-light border border-cyber-border/40 rounded-lg px-3 py-2 hover:border-cyber-accent/30 hover:text-cyber-text transition-all truncate">
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="col-span-2">
        {error && <div className="panel border-cyber-danger/20 text-sm text-cyber-danger">{error}</div>}
        {result ? <ComplianceResult result={result} /> : !error && (
          <div className="panel h-full flex items-center justify-center text-sm text-cyber-muted">Awaiting input</div>
        )}
      </div>
    </div>
  )
}

function ComplianceResult({ result }: { result: IslamicDetectionResult }) {
  return (
    <div className={`panel ${result.is_compliant ? 'border-cyber-green/20 shadow-glow-green' : 'border-cyber-danger/20 shadow-glow-red'}`}>
      <div className="mb-4">
        <span className={result.is_compliant ? 'badge-safe' : 'badge-danger'}>
          {result.is_compliant ? 'Compliant' : 'Non-Compliant'}
        </span>
      </div>

      {result.violations && result.violations.length > 0 && (
        <div className="mb-3">
          <span className="text-xs text-cyber-muted uppercase tracking-wider">Violations</span>
          <ul className="mt-1.5 space-y-1">
            {result.violations.map((v, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-cyber-danger/90">
                <span className="mt-1 w-1 h-1 rounded-full bg-cyber-danger flex-shrink-0" />
                {v}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.suggestions && result.suggestions.length > 0 && (
        <div>
          <span className="text-xs text-cyber-muted uppercase tracking-wider">Recommendations</span>
          <ul className="mt-1.5 space-y-1">
            {result.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-cyber-muted">
                <span className="mt-1 w-1 h-1 rounded-full bg-cyber-accent flex-shrink-0" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function RuleConfig() {
  const [rules, setRules] = useState<IslamicRulesResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getRules('en').then(setRules).catch(() => setRules(null)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="panel text-sm text-cyber-muted">Loading rule sets...</div>
  if (!rules) return <div className="panel text-sm text-cyber-danger">Failed to load rules</div>

  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-cyber-text">Active Rule Set</h3>
        <span className="badge-info">Language: {rules.language}</span>
      </div>
      <pre className="text-sm text-cyber-muted font-mono bg-cyber-bg rounded-lg p-4 overflow-auto max-h-[400px] border border-cyber-border/40">
        {JSON.stringify(rules.rules, null, 2)}
      </pre>
    </div>
  )
}
