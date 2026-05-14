import apiClient from './client'
import type { IslamicDetectionResult, IslamicRulesResponse } from '../types/islamic'

export async function detectIslamic(text: string, mode: string = 'normal'): Promise<IslamicDetectionResult> {
  const { data } = await apiClient.post('/islamic/detect', { text, mode })
  return data
}

export async function getRules(language: string = 'en'): Promise<IslamicRulesResponse> {
  const { data } = await apiClient.get(`/islamic/rules?language=${language}`)
  return data
}
