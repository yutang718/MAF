export interface ProventraResult {
  model: string
  text: string
  is_injection: boolean
  is_safe: boolean
  injection_score: number
  safe_score: number
  threshold: number
  label: string
  confidence: number
  latency_ms?: number
}

export interface MafGuardResult extends ProventraResult {
  threat_score: number
  scores: { BENIGN: number; INJECTION: number; HARMFUL_REQUEST: number }
}
