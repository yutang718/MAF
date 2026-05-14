import apiClient from './client'
import type { PIIDetectionResult, PIIRule } from '../types/pii'

export async function detectPII(text: string): Promise<PIIDetectionResult> {
  const { data } = await apiClient.post('/pii/detect', { text })
  return data
}

export async function getRules(): Promise<{ rules: PIIRule[] }> {
  const { data } = await apiClient.get('/pii/rules')
  return data
}
