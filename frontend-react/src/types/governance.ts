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
