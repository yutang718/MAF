import apiClient from './client'
import type { DetectionResult, HikmaResult, PromptGuardResult, ProventraResult, ModelsResponse } from '../types/prompt'

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

export async function detectProventra(text: string, threshold: number = 0.5): Promise<ProventraResult> {
  const { data } = await apiClient.post('/proventra/detect', { text, threshold })
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

// Benchmark API
export async function getBenchmarkDatasets() {
  const { data } = await apiClient.get('/benchmark/datasets')
  return data
}

export async function startBenchmark(datasetId: string, models: string[], maxSamples: number = 200, thresholds?: Record<string, number>) {
  const { data } = await apiClient.post('/benchmark/run', { dataset_id: datasetId, models, max_samples: maxSamples, thresholds })
  return data
}

export async function getBenchmarkRun(runId: string) {
  const { data } = await apiClient.get(`/benchmark/runs/${runId}`)
  return data
}

export async function listBenchmarkRuns() {
  const { data } = await apiClient.get('/benchmark/runs')
  return data
}

export async function deleteBenchmarkRun(runId: string) {
  const { data } = await apiClient.delete(`/benchmark/runs/${runId}`)
  return data
}
