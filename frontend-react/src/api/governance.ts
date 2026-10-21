import apiClient from './client'
import type {
  AlertItem, AlertStatus, AuditLogEntry, CheckCatalogEntry, CheckResult, ConnectorInfo, ConnectorType, ControlDetail,
  EvidenceItem, FindingItem, FrameworkDetail, FrameworkSummary, GovUser, NotifySettings, Overview, PostureSummary,
  RiskExceptionItem, Role, SlaMetrics,
} from '../types/governance'

const base = '/governance'
// The session is an httpOnly cookie set by the governance service; axios sends it on same-origin requests.
const get = async <T,>(path: string, params?: object) => (await apiClient.get<T>(base + path, { params })).data
const send = async <T,>(method: 'post' | 'put' | 'patch' | 'delete', path: string, body?: unknown) =>
  (await apiClient.request<T>({ method, url: base + path, data: body })).data

export const govApi = {
  me: () => get<GovUser>('/auth/me'),
  login: (email: string, password: string) => send<GovUser>('post', '/auth/login', { email, password }),
  logout: () => send<void>('post', '/auth/logout'),
  changePassword: (current: string, next: string) => send<void>('post', '/auth/password', { current, new: next }),

  overview: () => get<Overview>('/overview'),
  frameworks: () => get<FrameworkSummary[]>('/frameworks'),
  framework: (id: string) => get<FrameworkDetail>(`/frameworks/${id}`),
  history: (id: string) => get<{ at: string; score: number }[]>(`/frameworks/${id}/history`),
  control: (fw: string, id: string) => get<ControlDetail>(`/frameworks/${fw}/controls/${encodeURIComponent(id)}`),
  reportUrl: (fw: string, lang: string) => `${apiClient.defaults.baseURL}${base}/frameworks/${fw}/report.csv?lang=${lang}`,
  setNotApplicable: (fw: string, id: string, reason: string) =>
    send('put', `/frameworks/${fw}/controls/${encodeURIComponent(id)}/applicability`, { reason }),
  setApplicable: (fw: string, id: string) =>
    send('delete', `/frameworks/${fw}/controls/${encodeURIComponent(id)}/applicability`),

  uploadEvidence: async (form: FormData) =>
    (await apiClient.post<EvidenceItem>(`${base}/evidence`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000,
    })).data,
  evidenceFileUrl: (id: number) => `${apiClient.defaults.baseURL}${base}/evidence/${id}/file`,
  deleteEvidence: (id: number) => send('delete', `/evidence/${id}`),

  checks: () => get<CheckCatalogEntry[]>('/checks'),
  checkResult: (id: number) => get<CheckResult & { history: { id: number; status: string; evaluated_at: string }[] }>(
    `/check-results/${id}`),

  exceptions: () => get<RiskExceptionItem[]>('/exceptions'),
  requestException: (body: { check_id: string; connector_id: number | null; reason: string;
    compensating_controls: string; expires_on: string }) => send<RiskExceptionItem>('post', '/exceptions', body),
  decideException: (id: number, approve: boolean) => send<RiskExceptionItem>('post', `/exceptions/${id}/decision`, { approve }),
  revokeException: (id: number) => send<RiskExceptionItem>('post', `/exceptions/${id}/revoke`),

  alerts: (params: { status?: AlertStatus[]; severity?: string[]; connector_id?: number; rule_id?: string; q?: string;
    days?: number; offset?: number; limit?: number }) =>
    get<{ total: number; items: AlertItem[] }>('/alerts', params),
  updateAlert: (id: number, body: { status?: AlertStatus; assignee_id?: number | null; note?: string }) =>
    send<AlertItem>('patch', `/alerts/${id}`, body),

  connectorTypes: () => get<ConnectorType[]>('/connector-types'),
  connectors: () => get<ConnectorInfo[]>('/connectors'),
  connector: (id: number) => get<ConnectorInfo>(`/connectors/${id}`),
  createConnector: (body: object) => send<ConnectorInfo>('post', '/connectors', body),
  updateConnector: (id: number, body: object) => send<ConnectorInfo>('patch', `/connectors/${id}`, body),
  deleteConnector: (id: number) => send('delete', `/connectors/${id}`),
  testConnector: (id: number) => send<{ ok: boolean; message: string }>('post', `/connectors/${id}/test`),
  runConnector: (id: number) => send<ConnectorInfo>('post', `/connectors/${id}/run`),

  posture: () => get<PostureSummary>('/posture'),
  findings: (checkId: string, params: { resolved?: boolean; overdue?: boolean; offset?: number; limit?: number }) =>
    get<{ total: number; items: FindingItem[] }>(`/posture/checks/${encodeURIComponent(checkId)}/findings`, params),
  slaMetrics: () => get<SlaMetrics>('/posture/sla'),
  notifySettings: () => get<NotifySettings>('/settings/notify'),
  saveNotify: (body: Partial<NotifySettings> & { teams_webhook?: string }) => send<NotifySettings>('put', '/settings/notify', body),
  testNotify: () => send<{ ok: boolean; message: string }>('post', '/settings/notify/test'),
  slaSettings: () => get<Record<string, number>>('/settings/sla'),
  saveSla: (body: Record<string, number>) => send<Record<string, number>>('put', '/settings/sla', body),

  users: () => get<GovUser[]>('/users'),
  createUser: (body: { email: string; name: string; role: Role; password: string }) => send<GovUser>('post', '/users', body),
  updateUser: (id: number, body: Partial<{ name: string; role: Role; active: boolean; password: string }>) =>
    send<GovUser>('patch', `/users/${id}`, body),
  auditLog: (params: { offset?: number; limit?: number; action?: string }) =>
    get<{ total: number; items: AuditLogEntry[] }>('/audit-log', params),
}
