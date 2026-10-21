import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export default apiClient

type Translate = (key: string, vars?: Record<string, string | number>) => string

/**
 * Turn a failed request into a sentence an operator can act on: the cause and
 * what to do next. FastAPI puts the useful message in `detail`; axios' own
 * `err.message` is just "Request failed with status code 400", which tells the
 * user nothing, and a down backend surfaces as a bare 502 from the dev proxy.
 */
export function errorMessage(err: unknown, t: Translate): string {
  if (axios.isAxiosError(err)) {
    if (err.code === 'ECONNABORTED') {
      return t('error.timeout', { seconds: Math.round((err.config?.timeout ?? 30000) / 1000) })
    }
    const status = err.response?.status
    if (!err.response) return t('error.unreachable')
    // Gateway errors mean nothing answered behind the proxy; any body is the proxy's, not ours.
    if (status === 502 || status === 503 || status === 504) return t('error.unavailable', { status })
    const detail = err.response.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(d => d?.msg ?? String(d)).join('; ')
    if (status && status >= 500) return t('error.server', { status })
  }
  return err instanceof Error ? err.message : String(err)
}
