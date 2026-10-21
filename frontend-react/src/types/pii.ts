export interface PIIEntity {
  type: string
  /** The matched span of the input, as returned by POST /pii/detect */
  text: string
  start: number
  end: number
  score: number
  category?: string
  is_custom?: boolean
}

export type PIIRiskLevel = 'low' | 'medium' | 'high'

export interface PIIDetectionResult {
  is_safe: boolean
  masked_text: string
  entities: PIIEntity[]
  analysis?: {
    entity_types: string[]
    risk_level: PIIRiskLevel
    custom_entities_found: boolean
  }
}

export interface PIIRule {
  id: string
  name: string
  type: string
  pattern: string
  description: string
  category: string
  country: string
  language: string
  enabled: boolean
  masking_method: string
}
