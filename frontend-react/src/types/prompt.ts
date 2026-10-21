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

export interface MafGuardResult {
  model: string
  text: string
  is_injection: boolean
  is_harmful_request: boolean
  injection_score: number
  harmful_score: number
  injection_threshold: number
  harmful_threshold: number
  label: 'BENIGN' | 'INJECTION' | 'HARMFUL_REQUEST'
  scores: { BENIGN: number; INJECTION: number; HARMFUL_REQUEST: number }
  latency_ms?: number
}

export interface MafGuardInfo {
  model_id: string
  version: string | null   // release tag resolved from the Hub, e.g. "v5"
  revision: string | null  // Hub commit of the loaded weights
  initialized: boolean
}
