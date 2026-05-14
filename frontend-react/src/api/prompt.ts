import apiClient from './client'
import type { DetectionResult, HikmaResult, PromptGuardResult, ModelsResponse } from '../types/prompt'

export async function detectPrompt(text: string, mode: string = 'detailed'): Promise<DetectionResult> {
  const { data } = await apiClient.post('/prompt/detect', { text, mode })
  return data
}

export async function detectHikma(text: string, threshold: number = 0.5): Promise<HikmaResult> {
  const { data } = await apiClient.post('/hikma/detect', { text, threshold })
  return data
}

export async function detectPromptGuard(text: string, threshold: number = 0.5): Promise<PromptGuardResult> {
  const { data } = await apiClient.post('/promptguard/detect', { text, threshold })
  return data
}

export async function getModels(): Promise<ModelsResponse> {
  const { data } = await apiClient.get('/prompt/models')
  return data
}

export async function setModel(modelId: string) {
  const { data } = await apiClient.post('/prompt/set-model', { model_id: modelId })
  return data
}
