import { useState } from 'react'
import { detectPII } from '../api/pii'
import type { PIIDetectionResult } from '../types/pii'

const samples = [
  'My name is Ahmad bin Abdullah and my IC is 00-123456. Email: ahmad@gmail.com',
  'Contact John at +673 823 4567 or john.doe@company.com for the NDA.',
  'Wire $5,000 to account 1234-5678-9012 (Sarah Haji Mohd, BIBD).',
]

export default function PIIDetectionPage() {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PIIDetectionResult | null>(null)
  const [error, setError] = useState('')

  const run = async () => {
    if (!text.trim()) return
    setLoading(true); setError(''); setResult(null)
    try { setResult(await detectPII(text)) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    setLoading(false)
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-cyber-text">PII Scanner</h1>
        <p className="text-sm text-cyber-muted mt-0.5">
          Detect and mask personally identifiable information using Microsoft Presidio with region-specific recognizers (SEA)
        </p>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* Input */}
        <div className="col-span-3 space-y-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Enter text containing personal data..."
            className="input-field h-40 resize-none" />
          <button onClick={run} disabled={loading || !text.trim()} className="btn-primary w-full">
            {loading ? 'Scanning...' : 'Scan for PII'}
          </button>

          {/* Samples */}
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

        {/* Result */}
        <div className="col-span-2">
          {error && <div className="panel border-cyber-danger/20 text-sm text-cyber-danger">{error}</div>}
          {result ? <PIIResult result={result} /> : !error && (
            <div className="panel h-full flex items-center justify-center text-sm text-cyber-muted">Awaiting input</div>
          )}
        </div>
      </div>
    </div>
  )
}

function PIIResult({ result }: { result: PIIDetectionResult }) {
  return (
    <div className="space-y-3">
      <div className="panel border-cyber-accent/15">
        <span className="text-xs text-cyber-muted uppercase tracking-wider">Masked Output</span>
        <p className="text-sm font-mono text-cyber-text leading-relaxed mt-2">{result.masked_text}</p>
      </div>

      {result.entities && result.entities.length > 0 && (
        <div className="panel">
          <span className="text-xs text-cyber-muted uppercase tracking-wider">
            Entities Found ({result.entities.length})
          </span>
          <div className="mt-2 space-y-1.5">
            {result.entities.map((e, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-cyber-border/30 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="badge-warn">{e.type}</span>
                  <span className="text-sm font-mono text-cyber-text">{e.value}</span>
                </div>
                <span className="text-xs text-cyber-muted font-mono">{(e.score * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
