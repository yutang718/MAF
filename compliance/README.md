# Security governance service

A security expert's checklist for the company's **self-managed GitLab** and
**Microsoft 365 (Entra ID, Defender, Purview)**, run automatically on every
collection. Every problem (a leaver's GitLab account, a CVE on a laptop, a DLP
alert) is tracked as a **finding** from first sighting to fix, against a
remediation deadline. A weekly report goes to Teams.

The UI is the **Governance → Security checks** page of the MAF frontend. MAF
forwards `/api/v1/governance/*` to this service, so everything stays on one
origin. ISO 27001 / NIST CSF / HIPAA views are still there (Frameworks), built
from the same checks.

## What it checks

The catalogue is `govern/catalog/posture.yaml`. Codes as they appear in the UI and reports:

| Area | Codes | Highlights |
|---|---|---|
| GitLab · accounts | GL-ID-01…07 | **Leavers**: active GitLab account, but the Entra account is disabled or deleted (matched by SSO identity, then email); their live tokens and SSH keys; dormant (90 d), non-corporate accounts; password sign-in, 2FA, open sign-up |
| GitLab · privileges | GL-PR-01…06 | Instance admins (≤3, each with a valid Entra identity); Maintainer/Owner sprawl; direct project grants; contractors without expiry; accounts writing to >100 projects; privilege-grant alerts |
| GitLab · secrets | GL-TK-01…05 | Tokens with admin scopes or no expiry; idle tokens; weak SSH keys; unmasked/unprotected CI secrets (names only, values never read); write deploy keys |
| GitLab · exfiltration | GL-DX-01…06 | **Bulk clone/download** per person vs fixed limit and own 30-day baseline (from shipped logs); project exports; push mirrors to outside hosts; personal forks; leaver activity; public/internal projects |
| GitLab · platform | GL-PL-01…03 | Supported, patched release (vs gitlab.com); audit events; branch protection |
| Defender · vulnerabilities | VM-01…05 | Every device×CVE on a deadline: **exploited/KEV 7 d, critical 15, high 30, medium 90, low 180**; on-time rate and MTTR; end-of-support software |
| Defender · endpoints | EP-01…10 | Intune devices not in Defender; sensor health; AV real-time/signatures; tamper protection; ASR in block; high-risk devices; incidents; encryption |
| Purview · data loss | DP-01…08 | DLP triage SLA (1/3/7 days); repeat offenders; insider risk; **bulk SharePoint/OneDrive download** (stricter for disabled accounts); leavers' downloads in their last 30 days; Anyone-links; forwarding alerts |
| Entra ID | ID-01…10 | MFA and CA; permanent privileged roles (PIM); app registrations with mailbox/file/directory-wide permissions or long-lived secrets; dormant accounts, guests, risky users |

A finding resolves only when its check runs again **with data** and no longer
sees it. A missing licence or a failed collection leaves findings open. A fixed
finding that comes back is reopened with a new clock. Deadlines are edited in
**Settings** and apply to open findings at once.

## Run it

```bash
cp compliance/.env.example compliance/.env   # fill in the keys; commands are in the file
# GOVERN_DB_PASSWORD also has to be in the root .env (compose reads it for Postgres)
docker compose --profile governance up -d --build
```

Without `--profile governance`, `docker compose up` starts MAF alone, exactly as
before.

| Container | Role |
|---|---|
| `governance-api` | FastAPI on :8100 (not published; MAF proxies to it). Runs Alembic migrations on start. |
| `governance-worker` | `python -m govern.worker`. Runs connectors when they're due or someone presses "Run now". |
| `governance-db` | PostgreSQL 16 |

On first start, `GOVERN_BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` creates the first
admin. After that, manage users under **Governance → Administration**.

### Local development

```bash
cd compliance
uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q
# API with SQLite and the worker in-process:
GOVERN_DATABASE_URL=sqlite:///./govern.db GOVERN_INLINE_WORKER=true GOVERN_COOKIE_SECURE=false \
GOVERN_MASTER_KEY=... GOVERN_JWT_SECRET=... GOVERN_BOOTSTRAP_ADMIN_EMAIL=... GOVERN_BOOTSTRAP_ADMIN_PASSWORD=... \
  .venv/bin/uvicorn govern.main:app --port 8100
# Optional: demo data from the test fixtures (dev databases only)
.venv/bin/python scripts/seed_demo.py
# Frontend: the Vite dev server proxies /api/v1/governance to :8100
cd ../frontend-react && npm run dev
```

## Data sources

All connectors are **read-only**. Anything a licence, plan or permission doesn't
cover is recorded as *unavailable* and its checks show "Not available", never "Pass".

### GitLab (self-managed, Premium)

- A dedicated **administrator** account with a personal access token: `read_api`
  (plus `admin_mode` if Admin Mode is on). Instance-wide users, tokens, SSH keys,
  memberships, mirrors, CI variable names and audit events need admin.
- **Leaver detection needs the Microsoft 365 source too.** GitLab accounts are
  matched to Entra users by SAML/OIDC `extern_uid`, then by email. List service
  accounts in the connector so they aren't reported as leavers.
- **Bulk downloads**: Premium audit events don't record clones, so ship GitLab's
  own logs to `POST /api/v1/governance/ingest/gitlab/<connector id>` with the
  connector's *log ingestion token*. See `deploy/fluent-bit-gitlab.conf`.
  `gitlab-ci-token` (CI jobs) is excluded by default.
- Version currency is compared with gitlab.com release tags (needs outbound
  HTTPS; can be turned off).

### Microsoft 365

Entra app registration, **application** permissions, admin consent:
`User.Read.All, AuditLog.Read.All, Policy.Read.All, RoleManagement.Read.Directory,
RoleAssignmentSchedule.Read.Directory, Application.Read.All, IdentityRiskyUser.Read.All,
SecurityEvents.Read.All, SecurityAlert.Read.All, SecurityIncident.Read.All,
ThreatHunting.Read.All, AuditLogsQuery.Read.All, SharePointTenantSettings.Read.All,
DeviceManagementManagedDevices.Read.All, DeviceManagementConfiguration.Read.All,
InformationProtectionPolicy.Read.All, RecordsManagement.Read.All`, and on
WindowsDefenderATP `Machine.Read.All`.

- Vulnerabilities, AV/tamper/ASR state and end-of-support software come from
  **Advanced Hunting** (Defender for Endpoint P2 / Defender Vulnerability
  Management). At most 100,000 rows per query; a truncated result is reported.
- KEV: the CISA Known Exploited Vulnerabilities feed (outbound HTTPS to cisa.gov).
- File downloads: the asynchronous **audit log query** API (unified audit
  logging must be on). A query that hasn't finished is collected on the next run.
- PIM needs Entra ID P2; without it every privileged role member is reported as permanent.

### GitHub, Archery

Unchanged; see the connector forms in the UI.

## Teams

In the channel, add the Workflows template *"Post to a channel when a webhook
request is received"* and paste its URL into **Governance → Settings**. The
weekly report (default Monday 09:00 Asia/Brunei) lists failing checks, open and
overdue findings, what's new and fixed, and vulnerability SLA figures. New
critical alerts can also be posted as they're raised.

## How it fits together

```
connector.collect() ─→ facts (snapshots) ─→ checks ─→ check_results ─┐
                   └─→ events ─→ alert rules ─→ alerts               ├─→ control status per framework
                                 evidence / N/A decisions / exceptions ┘
```

- **Checks** (`govern/checks/`) read facts and return pass / partial / fail.
  They know nothing about frameworks.
- **Mappings** (`govern/catalog/mappings.yaml`) say which controls each check is
  evidence for. One check can serve all three frameworks. Startup fails if a
  check has no mapping or a mapping names an unknown control.
- **Catalogs** (`govern/catalog/*.yaml`): ISO 27001 Annex A (93), NIST CSF 2.0
  (106), HIPAA Security Rule implementation specifications (48). If HHS
  finalises the January 2025 HIPAA amendments, revise `hipaa.yaml`.
- **Control status**, in order of precedence: not applicable → fail/partial
  (evidence never overrides a failing check) → pass (approved risk exceptions
  count here) → evidenced → evidence expired → no data → needs evidence.
- **Alert rules** (`govern/rules/`) see each run's new events. They are
  deduplicated per rule, subject and day. Thresholds, allow lists and on/off
  switches are per connector under "Advanced".

## Security model

- Separate accounts from MAF. Roles: viewer < auditor < admin. bcrypt
  passwords, at least 12 characters; lockout after 5 failures; session in an
  httpOnly, SameSite=Strict cookie.
- Connector credentials are encrypted with `GOVERN_MASTER_KEY` (Fernet). They
  can be replaced but never read back through the API. Losing the key means
  re-entering every credential.
- Risk exceptions need an admin other than the requester, and expire within 365
  days. Closing an alert needs a note.
- An append-only platform audit log records sign-ins, configuration changes,
  evidence uploads, downloads and deletions, decisions, and report exports.
- Evidence files are stored under random names with a SHA-256 fingerprint and
  served only as downloads. Only allow-listed file types are accepted.

## Not verified yet

The connectors are tested against API responses shaped like the documented
ones, not against your tenant or GitLab instance. Before relying on results:

- **GitLab audit events**: event names and detail fields differ between
  versions. The privilege-grant rule matches on details (`add`/`as`, `change`/`to`);
  check against what your instance emits.
- **GitLab logs**: the parser expects the default JSON log format
  (`production_json.log`, `api_json.log`, `gitlab-shell.log`). Send a sample
  and check that the response's `downloads` count is non-zero.
- **Entra matching**: if GitLab's SAML `extern_uid` is the Entra object ID,
  matching is exact; if it's a NameID that is neither UPN nor mail, matching
  falls back to email.
- **Advanced Hunting tables** (`DeviceTvm*`) need Defender Vulnerability
  Management; their schema is Microsoft's and has changed before.
- **Audit-log query API** (`/beta/security/auditLog/queries`) is a beta Graph API.
- **Archery** schema assumptions follow 1.9–1.11; a mismatch shows as "unavailable".
- **Purview**: DLP policy definitions and the unified audit log switch aren't in
  Graph, so they aren't checked directly.
