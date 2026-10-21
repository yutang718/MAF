/** Shapes returned by the security governance service under /api/v1/governance. */

export type L10n = { en: string; zh: string }
export type Role = 'admin' | 'auditor' | 'viewer'

export interface GovUser {
  id: number
  email: string
  name: string
  role: Role
  active: boolean
  last_login_at: string | null
}

export type ControlStatus =
  | 'fail' | 'partial' | 'needs_evidence' | 'evidence_expired' | 'no_data' | 'pass' | 'evidenced' | 'not_applicable'

export type CheckStatus = 'pass' | 'partial' | 'fail' | 'not_available' | 'error' | 'accepted'
export type Severity = 'low' | 'medium' | 'high' | 'critical'

export interface FrameworkSummary {
  id: string
  name: L10n
  description: L10n
  score: number
  counts: Record<ControlStatus, number>
  applicable: number
  total: number
  automated: number
  trend?: { at: string; score: number }[]
}

export interface ControlRow {
  id: string
  group: string
  title: L10n
  status: ControlStatus
  mapped_checks: number
  check_counts: Partial<Record<CheckStatus, number>>
  evidence_current: number
  evidence_expired: number
  not_applicable_reason: string | null
}

export interface FrameworkDetail {
  id: string
  name: L10n
  description: L10n
  groups: { id: string; name: L10n }[]
  summary: Omit<FrameworkSummary, 'id' | 'name' | 'description'>
  controls: ControlRow[]
}

export interface CheckMeta {
  id: string
  kind?: string
  title: L10n
  severity?: Severity
  remediation?: L10n
}

export interface CheckResult {
  id: number
  check: CheckMeta
  connector_id: number
  connector_name: string | null
  status: CheckStatus
  raw_status: CheckStatus
  evaluated_at: string
  params: Record<string, unknown>
  summary: L10n | null
  item_count: number
  items?: Record<string, unknown>[]
}

export interface EvidenceItem {
  id: number
  framework: string
  control_id: string
  title: string
  description: string
  file_name: string
  size: number
  sha256: string
  valid_until: string | null
  expired: boolean
  uploaded_by: string | null
  created_at: string
}

export interface ControlDetail extends ControlRow {
  group_name: L10n
  results: CheckResult[]
  uncovered_checks: CheckMeta[]
  evidence: EvidenceItem[]
  related: Record<string, string[]>
}

export interface CheckCatalogEntry extends CheckMeta {
  summary_template: L10n
  defaults: Record<string, unknown>
  mappings: Record<string, string[]>
  results: CheckResult[]
}

export interface ConnectorField {
  name: string
  label: L10n
  type: 'string' | 'int' | 'bool' | 'list' | 'secret'
  required: boolean
  default: unknown
  help: L10n | null
}

export interface ConnectorType {
  kind: string
  title: L10n
  permissions_help: L10n
  fields: ConnectorField[]
  checks: string[]
  rules: { id: string; title: L10n; description: L10n; defaults: Record<string, unknown> }[]
}

export interface ConnectorRun {
  id: number
  started_at: string
  finished_at: string | null
  status: 'running' | 'ok' | 'partial' | 'error'
  stats: Record<string, number>
  unavailable: Record<string, string>
  error: string
}

export interface ConnectorInfo {
  id: number
  kind: string
  name: string
  config: Record<string, unknown>
  enabled: boolean
  schedule_minutes: number
  run_requested: boolean
  running: boolean
  last_run_at: string | null
  last_status: 'never' | 'ok' | 'partial' | 'error'
  last_error: string
  secrets_set: string[]
  runs?: ConnectorRun[]
}

export type AlertStatus = 'open' | 'acknowledged' | 'resolved' | 'false_positive'

export interface AlertItem {
  id: number
  rule_id: string
  rule: L10n
  connector_id: number
  connector_name: string | null
  connector_kind: string | null
  severity: Severity
  title: L10n
  actor: string
  detail: Record<string, unknown>
  occurred_at: string
  status: AlertStatus
  assignee: string | null
  assignee_id: number | null
  notes: { at: string; by: string; text: string; status: AlertStatus }[]
  created_at: string
  updated_at: string
}

export interface RiskExceptionItem {
  id: number
  check: CheckMeta
  connector_id: number | null
  reason: string
  compensating_controls: string
  expires_on: string
  expired: boolean
  status: 'pending' | 'approved' | 'rejected' | 'revoked'
  requested_by: string | null
  decided_by: string | null
  decided_at: string | null
  created_at: string
}

export interface AuditLogEntry {
  id: number
  at: string
  user: string
  action: string
  target_type: string
  target_id: string
  detail: Record<string, unknown>
  ip: string
}

export interface Overview {
  frameworks: FrameworkSummary[]
  open_alerts: Record<Severity, number>
  recent_alerts: AlertItem[]
  connectors: Pick<ConnectorInfo, 'id' | 'kind' | 'name' | 'enabled' | 'last_status' | 'last_run_at' | 'running'>[]
}

// ─── Security posture ─────────────────────────────────────────────────────────

export type PostureStatus = CheckStatus | 'no_source'

export interface PostureItem {
  code: string
  type: 'check' | 'rule'
  id: string
  title: L10n
  severity: Severity
  status: PostureStatus
  sla: boolean
  summary: L10n | null
  result_ids: number[]
  open: number
  overdue: number
  open_by_severity: Partial<Record<Severity, number>>
  new: number
  resolved: number
  oldest_days: number | null
}

export interface PostureDomain {
  id: string
  source: string
  name: L10n
  items: PostureItem[]
  failing: number
  open: number
  overdue: number
}

export interface PostureSummary {
  period_days: number
  domains: PostureDomain[]
  totals: Partial<Record<PostureStatus | 'open' | 'overdue' | 'new' | 'resolved', number>>
  sla: Record<string, number>
}

export interface FindingItem {
  id: number
  key: string
  label: string
  severity: Severity
  exploited: boolean
  data: Record<string, unknown>
  first_seen: string
  last_seen: string
  resolved_at: string | null
  due_at: string
  overdue: boolean
  age_days: number
  reopened: number
}

export interface SlaRow {
  sla_days: number
  resolved: number
  within_sla_pct: number | null
  mttr_days: number | null
  open: number
  open_overdue: number
}

export interface SlaMetrics {
  window_days: number
  by_severity: Record<'exploited' | Severity, SlaRow>
  trend: { at: string; open: number | null }[]
}

export interface NotifySettings {
  enabled: boolean
  weekday: number
  hour: number
  timezone: string
  base_url: string
  realtime_critical: boolean
  webhook_set: boolean
  state: { last_sent_at: string | null; last_error: string }
}
