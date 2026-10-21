import apiClient from './client'

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
  components: {
    guard_models: { status: 'up' | 'degraded'; loaded_models: string[]; models_count: number }
    pii_detector: { status: string; rules_count: number; rules_enabled: number }
  }
}

export async function getHealth(): Promise<HealthResponse> {
  // Short timeout: a health probe that hangs for 30s is itself the answer.
  const { data } = await apiClient.get<HealthResponse>('/health/', { timeout: 5000 })
  return data
}
