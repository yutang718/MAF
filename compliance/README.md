# Security governance service

Collects security configuration and activity from Microsoft 365, GitHub, GitLab
and Archery on a schedule, runs automated checks, and rolls the results up into
ISO/IEC 27001:2022, NIST CSF 2.0 and HIPAA Security Rule readiness. It also
raises risk alerts from audit logs: risky operations, bulk downloads, unusual
database access.

The UI is the **Governance** section of the MAF frontend. MAF forwards
`/api/v1/governance/*` to this service, so everything stays on one origin.

> Readiness is a gap analysis, not a certification. Automated checks cover
> technical controls. Organisational, people and physical controls rely on
> evidence that auditors attach in the UI.

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
cover is recorded as *unavailable*, and its checks show "Not available" rather
than "Fail".

| Source | Credentials | What needs a paid tier |
|---|---|---|
| Microsoft 365 | Entra app registration with application permissions (the form lists them); admin consent | Sign-in activity and Conditional Access need Entra ID P1; risky users need P2; Defender for Endpoint and Purview need their own licences |
| GitHub | Organisation owner's token, or a GitHub App with equivalent read access | Audit log API and git clone/fetch events need Enterprise Cloud; git events are kept only 7 days, so collect at least daily |
| GitLab | Group Owner's token with `read_api` | Audit events need Premium/Ultimate; per-user 2FA needs an instance-admin token (self-managed only) |
| Archery | Read-only MySQL account on Archery's own database | — |

**Archery sensitive-data discovery** connects to business databases only through
DSNs you list explicitly (use read-only accounts). It classifies columns by name
and comment (English, Chinese, Malay) and can confirm them by sampling values
through MAF's PII detector. Sampled values are never stored; only the entity
types found are kept. Archery's own encrypted instance passwords are never read.

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
ones, not against live tenants. Before relying on results:

- **GitLab** audit-event names differ between versions. The risky-operation and
  bulk-download rules match on event details. Check them against what your
  instance emits.
- **Archery** table and column names follow 1.9–1.11. A mismatch shows up as
  "unavailable" on the connector's run, not as a silent pass. Auto-approved
  tickets may have no approval record and would be flagged "no approval".
- **M365 Purview**: DLP policies and the unified audit log switch aren't
  exposed in Graph, so those remain evidence-based.
