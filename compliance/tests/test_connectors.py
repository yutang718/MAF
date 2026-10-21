"""Connectors against recorded-shape API responses (no network)."""
import json
from datetime import date, datetime, timedelta, timezone

import httpx

from govern.connectors.archery import ArcheryConnector
from govern.connectors.github import GitHubConnector
from govern.connectors.gitlab import GitLabConnector
from govern.connectors.m365 import M365Connector
from govern.engine.collector import evaluate_checks
from govern.models import Connector

NOW = datetime.now(timezone.utc)
OLD = (NOW - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
RECENT = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def router(routes: dict):
    """MockTransport handler: longest matching path prefix wins; value is JSON or (status, JSON)."""
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        for prefix in sorted(routes, key=len, reverse=True):
            if path == prefix or path.startswith(prefix + "?") or path == prefix.rstrip("/"):
                value = routes[prefix]
                value = value(request) if callable(value) else value
                if isinstance(value, tuple):
                    return httpx.Response(value[0], json=value[1])
                return httpx.Response(200, json=value)
        return httpx.Response(404, json={"message": f"no route {path}"})
    return httpx.MockTransport(handle), calls


def results(kind, facts, unavailable=None, config=None):
    row = Connector(kind=kind, name="t", config=config or {})
    return {k: v.status for k, v in evaluate_checks(row, facts, unavailable or {}, {}).items()}


# ─── Microsoft 365 ─────────────────────────────────────────────────────────────

def m365_routes(**overrides):
    routes = {
        "/tenant-1/oauth2/v2.0/token": {"access_token": "tok", "expires_in": 3600},
        "/v1.0/organization": {"value": [{"id": "o", "displayName": "EVYD"}]},
        "/v1.0/users": {"value": [
            {"id": "1", "displayName": "Ana", "userPrincipalName": "ana@x", "accountEnabled": True,
             "userType": "Member", "createdDateTime": OLD, "signInActivity": {"lastSignInDateTime": RECENT}},
            {"id": "2", "displayName": "Bob", "userPrincipalName": "bob@x", "accountEnabled": True,
             "userType": "Member", "createdDateTime": OLD, "signInActivity": {"lastSignInDateTime": OLD}},
        ]},
        "/v1.0/reports/authenticationMethods/userRegistrationDetails": {"value": [
            {"id": "1", "userPrincipalName": "ana@x", "isAdmin": True, "isMfaRegistered": True, "userType": "member"},
            {"id": "2", "userPrincipalName": "bob@x", "isAdmin": False, "isMfaRegistered": False, "userType": "member"},
        ]},
        "/v1.0/identity/conditionalAccess/policies": {"value": [{
            "displayName": "MFA all", "state": "enabled",
            "conditions": {"users": {"includeUsers": ["All"], "excludeUsers": ["bg"]},
                           "applications": {"includeApplications": ["All"]}},
            "grantControls": {"builtInControls": ["mfa"]}}]},
        "/v1.0/policies/identitySecurityDefaultsEnforcementPolicy": {"isEnabled": False},
        "/v1.0/directoryRoles": {"value": [{
            "displayName": "Global Administrator", "roleTemplateId": "62e90394-69f5-4237-9190-012177145e10",
            "members": [{"id": "1", "displayName": "Ana", "@odata.type": "#microsoft.graph.user"}]}]},
        "/v1.0/identityProtection/riskyUsers": (403, {"error": {"code": "Forbidden", "message": "needs P2"}}),
        "/v1.0/security/secureScores": {"value": [{"currentScore": 60, "maxScore": 100}]},
        "/v1.0/security/incidents": {"value": []},
        "/v1.0/security/alerts_v2": lambda req: {"value": [
            {"id": "a1", "title": "DLP hit", "severity": "high", "status": "new",
             "serviceSource": "dataLossPrevention", "createdDateTime": RECENT}]},
        "/api/machines": {"value": [
            {"id": "m1", "computerDnsName": "pc1", "healthStatus": "Active", "onboardingStatus": "Onboarded",
             "exposureLevel": "Low"}]},
        "/v1.0/deviceManagement/managedDevices": {"value": [
            {"id": "d1", "deviceName": "pc1", "operatingSystem": "Windows", "complianceState": "compliant",
             "isEncrypted": True, "jailBroken": "False", "lastSyncDateTime": RECENT},
            {"id": "d2", "deviceName": "ip1", "operatingSystem": "iOS", "complianceState": "noncompliant",
             "isEncrypted": False, "jailBroken": "True", "lastSyncDateTime": RECENT}]},
        "/v1.0/deviceManagement/deviceCompliancePolicies": {"value": [
            {"id": "p", "displayName": "Win", "@odata.type": "#microsoft.graph.windows10CompliancePolicy",
             "assignments": [{"id": "x"}]}]},
        "/beta/security/informationProtection/sensitivityLabels": {"value": [{"id": "l", "name": "Confidential"}]},
        "/v1.0/security/labels/retentionLabels": (403, {"error": {"message": "denied"}}),
    }
    routes.update(overrides)
    return routes


def test_m365_collects_and_grades():
    transport, calls = router(m365_routes())
    conn = M365Connector({"tenant_id": "tenant-1", "client_id": "app"}, {"client_secret": "s"},
                         transport=transport, sleep=lambda s: None)
    assert conn.test() == "Connected to tenant EVYD"
    c = conn.collect()
    assert "entra.risky_users" in c.unavailable and "purview.retention_labels" in c.unavailable
    assert c.facts["entra.sign_in_activity"] is True
    assert [e.external_id for e in c.events] == ["a1"]
    assert c.cursor["alerts_since"] == RECENT

    r = results("m365", c.facts, c.unavailable)
    assert r["m365.admin_mfa"] == "pass"
    assert r["m365.mfa_registered"] == "fail"  # 1 of 2
    assert r["m365.ca_require_mfa"] == "pass"
    assert r["m365.legacy_auth_blocked"] == "fail"
    assert r["m365.global_admin_count"] == "partial"  # only one
    assert r["m365.stale_accounts"] == "fail"  # bob
    assert r["m365.risky_users"] == "not_available"
    assert r["m365.retention_labels"] == "not_available"
    assert r["m365.secure_score"] == "partial"
    assert r["m365.data_loss_alerts"] == "fail"
    assert r["m365.device_encryption"] == "fail"
    assert r["m365.jailbroken_devices"] == "fail"
    assert r["m365.compliance_policy_coverage"] == "fail"  # iOS has no policy
    assert r["m365.defender_sensor_health"] == "pass"
    # Token fetched once per scope, not per request.
    assert sum(1 for x in calls if x.url.path.endswith("/token")) == 2


def test_m365_without_sign_in_activity_falls_back():
    def users(req):
        if "signInActivity" in req.url.params.get("$select", ""):
            return 403, {"error": {"message": "requires premium"}}
        return {"value": [{"id": "1", "userPrincipalName": "a@x", "accountEnabled": True, "userType": "Member"}]}
    transport, _ = router(m365_routes(**{"/v1.0/users": users}))
    c = M365Connector({"tenant_id": "tenant-1", "client_id": "app"}, {"client_secret": "s"},
                      transport=transport, sleep=lambda s: None).collect()
    assert "entra.users" in c.facts and "entra.sign_in_activity" in c.unavailable
    assert results("m365", c.facts, c.unavailable)["m365.stale_accounts"] == "not_available"


def test_m365_pagination_and_throttling():
    pages = {"n": 0}

    def devices(req):
        pages["n"] += 1
        if pages["n"] == 1:
            return 429, {"error": {"message": "slow down"}}
        if "skip" not in str(req.url):
            return {"value": [{"id": "d1"}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?skip=1"}
        return {"value": [{"id": "d2"}]}
    transport, _ = router(m365_routes(**{"/v1.0/deviceManagement/managedDevices": devices}))
    c = M365Connector({"tenant_id": "tenant-1", "client_id": "app"}, {"client_secret": "s"},
                      transport=transport, sleep=lambda s: None).collect()
    assert [d["id"] for d in c.facts["intune.devices"]] == ["d1", "d2"]


def test_m365_bad_secret_is_reported():
    transport, _ = router({"/tenant-1/oauth2/v2.0/token": (401, {"error_description": "AADSTS7000215: Invalid client secret"})})
    conn = M365Connector({"tenant_id": "tenant-1", "client_id": "app"}, {"client_secret": "bad"},
                         transport=transport, sleep=lambda s: None)
    try:
        conn.test()
        raise AssertionError("expected failure")
    except PermissionError as e:
        assert "Invalid client secret" in str(e)


# ─── GitHub ────────────────────────────────────────────────────────────────────

def github_routes():
    return {
        "/orgs/acme": {"login": "acme", "two_factor_requirement_enabled": False, "default_repository_permission": "write",
                       "plan": {"name": "enterprise"}},
        "/orgs/acme/members": lambda req: (
            [{"login": "eve"}] if req.url.params.get("filter") == "2fa_disabled" else
            [{"login": "own1"}] if req.url.params.get("role") == "admin" else [{"login": "dev1"}, {"login": "eve"}]),
        "/orgs/acme/outside_collaborators": [{"login": "contractor"}],
        "/orgs/acme/repos": [
            {"name": "api", "visibility": "private", "default_branch": "main",
             "security_and_analysis": {"secret_scanning": {"status": "enabled"},
                                       "secret_scanning_push_protection": {"status": "enabled"}}},
            {"name": "site", "visibility": "public", "default_branch": "main"},
            {"name": "old", "visibility": "private", "archived": True, "default_branch": "main"}],
        "/repos/acme/api/rules/branches/main": [{"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
                                                {"type": "non_fast_forward"}, {"type": "deletion"}],
        "/repos/acme/site/rules/branches/main": [],
        "/repos/acme/api/branches/main/protection": (404, {"message": "Branch not protected"}),
        "/repos/acme/site/branches/main/protection": (404, {"message": "Branch not protected"}),
        "/repos/acme/api/keys": [{"title": "ci", "read_only": False}],
        "/repos/acme/site/keys": [],
        "/orgs/acme/secret-scanning/alerts": [{"repository": {"full_name": "acme/api"}, "created_at": OLD}],
        "/orgs/acme/dependabot/alerts": [{"repository": {"full_name": "acme/api"}, "created_at": RECENT,
                                          "security_advisory": {"severity": "high"}}],
        "/orgs/acme/code-scanning/alerts": (403, {"message": "Advanced Security must be enabled"}),
        "/orgs/acme/installations": {"installations": [{"app_slug": "deployer", "permissions": {"administration": "write"}}]},
        "/orgs/acme/hooks": [{"id": 1, "config": {"url": "http://hooks.example.com", "insecure_ssl": "0"}}],
        "/orgs/acme/credential-authorizations": (404, {"message": "Not Found"}),
        "/orgs/acme/audit-log": [
            {"_document_id": "d1", "@timestamp": int((NOW - timedelta(hours=1)).timestamp() * 1000),
             "action": "repo.access", "actor": "own1", "repo": "acme/site", "visibility": "public"},
            *[{"_document_id": f"c{i}", "@timestamp": int((NOW - timedelta(minutes=30)).timestamp() * 1000),
               "action": "git.clone", "actor": "eve", "repo": f"acme/r{i}"} for i in range(25)],
        ],
    }


def test_github_collects_and_grades():
    transport, _ = router(github_routes())
    conn = GitHubConnector({"org": "acme"}, {"token": "t"}, transport=transport, sleep=lambda s: None)
    c = conn.collect()
    assert len(c.facts["github.branch_protection"]) == 2  # archived repo skipped
    assert "github.code_scanning_alerts" in c.unavailable
    assert len(c.events) == 26 and c.facts["audit.events"]["count"] == 26

    r = results("github", c.facts, c.unavailable)
    assert r["github.org_2fa_required"] == "fail"
    assert r["github.members_without_2fa"] == "fail"
    assert r["github.owner_count"] == "partial"
    assert r["github.default_permission"] == "fail"
    assert r["github.public_repos"] == "fail"
    assert r["github.branch_protection"] == "fail"  # api ok, site unprotected: 50% < 80%
    assert r["github.writable_deploy_keys"] == "partial"
    assert r["github.open_secret_alerts"] == "fail"
    assert r["github.dependabot_sla"] == "partial"  # open but within SLA
    assert r["github.code_scanning_sla"] == "not_available"
    assert r["github.webhooks_secure"] == "fail"
    assert r["github.app_permissions"] == "partial"
    assert r["github.audit_log"] == "pass"
    assert r["github.secret_scanning"] == "fail"  # 1 of 2 active repos
    # Allow lists come from connector config.
    assert results("github", c.facts, c.unavailable, {"public_repo_allowlist": ["site"]})["github.public_repos"] == "pass"


def test_github_without_enterprise_audit_log():
    routes = github_routes()
    routes["/orgs/acme/audit-log"] = (404, {"message": "Not Found"})
    transport, _ = router(routes)
    c = GitHubConnector({"org": "acme"}, {"token": "t"}, transport=transport, sleep=lambda s: None).collect()
    assert "audit.events" in c.unavailable and not c.events
    assert results("github", c.facts, c.unavailable)["github.audit_log"] == "not_available"


# ─── GitLab ────────────────────────────────────────────────────────────────────

def test_gitlab_collects_and_grades():
    routes = {
        "/api/v4/groups/acme": {"full_path": "acme", "require_two_factor_authentication": True,
                                "two_factor_grace_period": 48, "prevent_forking_outside_group": None},
        "/api/v4/groups/acme/members/all": [{"username": "o1", "access_level": 50}, {"username": "d1", "access_level": 30}],
        "/api/v4/groups/acme/projects": [{"id": 7, "path_with_namespace": "acme/api", "visibility": "internal",
                                          "default_branch": "main"}],
        "/api/v4/projects/7/protected_branches/main": {"push_access_levels": [{"access_level": 40}],
                                                       "allow_force_push": False},
        "/api/v4/projects/7/approval_rules": (403, {"message": "Premium"}),
        "/api/v4/projects/7/deploy_keys": [{"title": "k", "can_push": False}],
        "/api/v4/groups/acme/access_tokens": [{"name": "ci", "active": True, "expires_at": None, "scopes": ["api"]}],
        "/api/v4/groups/acme/audit_events": [{"id": 1, "created_at": RECENT, "entity_type": "Project",
                                              "details": {"author_name": "o1", "change": "visibility",
                                                          "from": "Private", "to": "Public", "entity_path": "acme/api"}}],
    }
    transport, _ = router(routes)
    c = GitLabConnector({"group": "acme"}, {"token": "t"}, transport=transport, sleep=lambda s: None).collect()
    r = results("gitlab", c.facts, c.unavailable)
    assert r["gitlab.group_2fa_required"] == "pass"
    assert r["gitlab.members_without_2fa"] == "not_available"
    assert r["gitlab.owner_count"] == "partial"
    assert r["gitlab.public_projects"] == "fail"  # internal
    assert r["gitlab.branch_protection"] == "fail"  # maintainers can push directly
    assert r["gitlab.writable_deploy_keys"] == "pass"
    assert r["gitlab.token_expiry"] == "fail"
    assert r["gitlab.forking_outside_group"] == "not_available"
    assert c.events[0].action == "change:visibility" and c.events[0].actor == "o1"


# ─── Archery ───────────────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self.rows = []

    def execute(self, sql, args=()):
        for marker, rows in self.tables.items():
            if marker in sql:
                self.rows = rows(sql, args) if callable(rows) else rows
                return
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, tables):
        self.tables = tables

    def cursor(self):
        return FakeCursor(self.tables)

    def close(self):
        pass


def archery_tables():
    local_now = NOW.replace(tzinfo=None)  # Archery stores naive times; the connector reads them as UTC here
    return {
        "FROM sql_config": [{"item": "data_masking", "value": "true"}, {"item": "query_check", "value": "false"}],
        "FROM sql_users": [
            {"username": "dba", "display": "DBA", "is_superuser": 1, "is_active": 1, "last_login": local_now,
             "date_joined": local_now},
            {"username": "ghost", "display": "Ghost", "is_superuser": 0, "is_active": 1,
             "last_login": local_now - timedelta(days=200), "date_joined": local_now - timedelta(days=400)}],
        "FROM sql_instance": [{"id": 1, "instance_name": "prod-his", "type": "master", "db_type": "mysql"}],
        "FROM query_privileges": [
            {"user_name": "ghost", "instance_id": 1, "db_name": "his", "table_name": "", "priv_type": 1,
             "valid_date": date.today() + timedelta(days=3650), "limit_num": 100, "create_time": local_now}],
        "FROM data_masking_columns": [{"instance_id": 1, "table_schema": "his", "table_name": "patient",
                                       "column_name": "ic_no", "rule_type": 1, "active": 1}],
        "FROM sql_workflow w": [
            {"id": 10, "workflow_name": "fix data", "engineer": "dba", "instance_id": 1, "db_name": "his",
             "syntax_type": 2, "status": "workflow_finish", "is_manual": 0, "create_time": local_now,
             "finish_time": local_now, "sql_content": "DELETE FROM visit"}],
        "FROM workflow_audit a JOIN workflow_log": [{"workflow_id": 10, "operator": "dba"}],
        "COUNT(*) AS queries": [{"queries": 3, "latest": local_now}],
        "FROM query_log WHERE": [
            {"id": 1, "instance_name": "prod-his", "db_name": "his", "sqllog": "select name, phone from patient",
             "effect_row": 50000, "cost_time": "1.2", "username": "ghost", "user_display": "Ghost", "priv_check": 1,
             "hit_rule": 1, "masking": 0, "create_time": local_now}],
    }


def scan_stub(conn, dialect, instance, sampler=None):
    from govern.engine.discovery import ColumnFinding
    return [ColumnFinding(instance, "his", "patient", "ic_no", ["national_id"], ["name"]),
            ColumnFinding(instance, "his", "patient", "phone", ["phone"], ["name"]),
            ColumnFinding(instance, "his", "users", "password", ["credential"], ["name"])]


def test_archery_collects_and_grades(monkeypatch):
    from govern.engine import discovery
    monkeypatch.setattr(discovery, "connect", lambda dsn: (FakeConn({}), "mysql"))
    conn = ArcheryConnector(
        {"host": "h", "user": "u", "timezone": time_zone()},
        {"password": "p", "discovery_dsns": json.dumps([{"instance": "prod-his", "dsn": "mysql://ro:x@db/his"}])},
        connect=lambda: FakeConn(archery_tables()), scan=scan_stub)
    c = conn.collect()
    assert c.cursor["query_log_id"] == 1 and "discovered_at" in c.cursor
    kinds = sorted(e.kind for e in c.events)
    assert kinds == ["archery.query", "archery.workflow"]
    wf = next(e for e in c.events if e.kind == "archery.workflow").data
    assert wf["self_approved"] and wf["worst"] == "critical" and wf["instance"] == "prod-his"

    r = results("archery", c.facts, c.unavailable)
    assert r["archery.masking_enabled"] == "pass"
    assert r["archery.masking_enforced"] == "fail"
    assert r["archery.select_star_disabled"] == "fail"  # not configured
    assert r["archery.unmasked_sensitive_columns"] == "fail"  # phone has no rule
    assert r["archery.queryable_credentials"] == "partial"
    assert r["archery.dormant_users"] == "fail"
    assert r["archery.long_privileges"] == "fail"
    assert r["archery.database_wide_privileges"] == "fail"
    assert r["archery.change_segregation"] == "fail"
    assert r["archery.high_risk_changes"] == "fail"
    assert r["archery.query_audit"] == "pass"

    # Within the re-scan interval discovery is skipped and its last result reused.
    again = ArcheryConnector({"host": "h", "user": "u", "timezone": time_zone()},
                             {"password": "p", "discovery_dsns": "[]"}, c.cursor,
                             connect=lambda: FakeConn(archery_tables()), scan=scan_stub).collect()
    assert "archery.sensitive_columns" in again.carry_forward


def test_archery_schema_mismatch_is_unavailable():
    def broken(sql, args):
        raise type("ProgrammingError", (Exception,), {})(1146, "Table 'archery.data_masking_columns' doesn't exist")
    tables = archery_tables()
    tables["FROM data_masking_columns"] = broken
    c = ArcheryConnector({"host": "h", "user": "u"}, {"password": "p"}, connect=lambda: FakeConn(tables)).collect()
    assert "archery.masking_columns" in c.unavailable
    assert "archery.sensitive_columns" in c.unavailable  # no discovery configured


def time_zone():
    return "UTC"
