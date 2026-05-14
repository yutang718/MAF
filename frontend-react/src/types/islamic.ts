export interface IslamicDetectionResult {
  is_compliant: boolean
  violations: string[]
  suggestions: string[]
  score: number
}

export interface IslamicRulesResponse {
  rules: Record<string, unknown>
  language: string
}
