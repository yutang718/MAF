import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export default apiClient

/**
 * FastAPI puts the useful message in `detail`; axios' own `err.message` is just
 * "Request failed with status code 400", which tells the user nothing.
 */
export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(d => d?.msg ?? String(d)).join('; ')
    if (err.code === 'ECONNABORTED') return 'Request timed out'
  }
  return err instanceof Error ? err.message : String(err)
}
