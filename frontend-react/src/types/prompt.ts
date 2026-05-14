export interface DetectionResult {
  score: number
  is_safe: boolean
  analysis?: {
    explanation?: string
    patterns?: string[]
    suggestions?: string[]
  }
}

export interface HikmaResult {
  model: string
  text: string
  is_injection: boolean
  is_safe: boolean
  injection_score: number
  benign_score: number
  threshold: number
  label: string
  confidence: number
}

export interface PromptGuardResult {
  model: string
  text: string
  is_injection: boolean
  is_safe: boolean
  injection_score: number
  jailbreak_score: number
  benign_score: number
  threat_score: number
  threshold: number
  label: string
  confidence: number
  scores: {
    BENIGN: number
    INJECTION: number
    JAILBREAK: number
  }
}

export interface ModelInfo {
  id: string
  name: string
  description: string
}

export interface ModelsResponse {
  models: ModelInfo[]
  current_model: string
}
