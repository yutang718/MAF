export interface PIIEntity {
  type: string
  value: string
  start: number
  end: number
  score: number
}

export interface PIIDetectionResult {
  original_text: string
  masked_text: string
  entities: PIIEntity[]
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
