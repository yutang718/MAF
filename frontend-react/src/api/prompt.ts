import apiClient from './client'
import type { ProventraResult, MafGuardResult } from '../types/prompt'

export async function detectProventra(text: string, threshold: number = 0.5): Promise<ProventraResult> {
  const { data } = await apiClient.post('/proventra/detect', { text, threshold })
  return data
}

export async function detectModernGuard(text: string, threshold: number = 0.5): Promise<ProventraResult> {
  const { data } = await apiClient.post('/modernguard/detect', { text, threshold })
  return data
}

export async function detectWolfDefender(text: string, threshold: number = 0.5): Promise<ProventraResult> {
  const { data } = await apiClient.post('/wolfdefender/detect', { text, threshold })
  return data
}

export async function detectMafGuard(text: string, threshold: number = 0.5): Promise<MafGuardResult> {
  const { data } = await apiClient.post('/mafguard/detect', { text, threshold })
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

export async function uploadAndRunBenchmark(file: File, models: string[], thresholds: Record<string, number>) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('models', models.join(','))
  formData.append('thresholds', JSON.stringify(thresholds))
  const { data } = await apiClient.post('/benchmark/upload-and-run', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
