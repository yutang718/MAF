from datetime import date, timedelta

from tests.conftest import login

API = "/api/v1/governance"


def make_user(client, email, role, password="a-long-enough-password"):
    r = client.post(f"{API}/users", json={"email": email, "role": role, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def switch(client, email, password="a-long-enough-password"):
    client.post(f"{API}/auth/logout")
    login(client, email, password)


def test_requires_sign_in(client):
    assert client.get(f"{API}/overview").status_code == 401
    assert client.get(f"{API}/health").status_code == 200


def test_login_lockout(client):
    for _ in range(5):
        assert client.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "nope"}).status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 429
    log_unknown = client.post(f"{API}/auth/login", json={"email": "who@example.com", "password": "x"})
    assert log_unknown.status_code == 401 and log_unknown.json()["detail"] == "Email or password is wrong"


def test_session_cookie_is_httponly_and_strict(client):
    r = login(client)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_roles_are_enforced(admin):
    make_user(admin, "viewer@example.com", "viewer")
    switch(admin, "viewer@example.com")
    assert admin.get(f"{API}/overview").status_code == 200
    assert admin.get(f"{API}/connectors").status_code == 200
    assert admin.post(f"{API}/connectors", json={"kind": "github", "name": "x"}).status_code == 403
    assert admin.get(f"{API}/audit-log").status_code == 403
    assert admin.get(f"{API}/users").status_code == 403


def test_last_admin_cannot_be_removed(admin):
    me = admin.get(f"{API}/auth/me").json()
    r = admin.patch(f"{API}/users/{me['id']}", json={"role": "viewer"})
    assert r.status_code == 400


def test_connector_secrets_are_write_only(admin):
    body = {"kind": "github", "name": "Acme GitHub", "config": {"org": "acme", "max_repos": "50",
                                                                 "public_repo_allowlist": "site, docs"},
            "secrets": {"token": "ghp_supersecret"}}
    r = admin.post(f"{API}/connectors", json=body)
    assert r.status_code == 201, r.text
    c = r.json()
    assert "ghp_supersecret" not in r.text
    assert c["secrets_set"] == ["token"]
    assert c["config"]["max_repos"] == 50 and c["config"]["public_repo_allowlist"] == ["site", "docs"]

    # Updating without the secret keeps it; listing never shows it.
    r = admin.patch(f"{API}/connectors/{c['id']}", json={"config": {"max_repos": 10}, "secrets": {"token": ""}})
    assert r.json()["secrets_set"] == ["token"] and r.json()["config"]["max_repos"] == 10
    assert "ghp_supersecret" not in admin.get(f"{API}/connectors").text
    log = admin.get(f"{API}/audit-log").text
    assert "ghp_supersecret" not in log and "connector.created" in log

    assert admin.post(f"{API}/connectors", json={"kind": "github", "name": "x", "config": {"org": "a"}}).status_code == 422
    assert admin.post(f"{API}/connectors/{c['id']}/run").status_code == 202
    assert admin.get(f"{API}/connectors/{c['id']}").json()["run_requested"] is True


def test_connector_schedule_floor(admin):
    r = admin.post(f"{API}/connectors", json={"kind": "github", "name": "x", "config": {"org": "a"},
                                               "secrets": {"token": "t"}, "schedule_minutes": 1})
    assert r.status_code == 422


def test_framework_endpoints(admin):
    fws = admin.get(f"{API}/frameworks").json()
    assert {f["id"] for f in fws} == {"iso27001", "nist_csf", "hipaa"}
    iso = admin.get(f"{API}/frameworks/iso27001").json()
    assert len(iso["controls"]) == 93 and iso["summary"]["counts"]["needs_evidence"] > 0
    ctl = admin.get(f"{API}/frameworks/iso27001/controls/A.8.5").json()
    assert ctl["uncovered_checks"] and "nist_csf" in ctl["related"]
    assert admin.get(f"{API}/frameworks/iso27001/controls/A.99").status_code == 404
    csv = admin.get(f"{API}/frameworks/hipaa/report.csv?lang=zh")
    assert csv.status_code == 200 and "164.312(d)" in csv.text


def test_not_applicable_needs_a_reason(admin):
    url = f"{API}/frameworks/iso27001/controls/A.7.12/applicability"
    assert admin.put(url, json={"reason": "no"}).status_code == 422
    assert admin.put(url, json={"reason": "Fully remote company; no office cabling"}).status_code == 200
    ctl = admin.get(f"{API}/frameworks/iso27001/controls/A.7.12").json()
    assert ctl["status"] == "not_applicable"
    assert admin.delete(url).status_code == 204


def test_evidence_upload_and_download(admin):
    r = admin.post(f"{API}/evidence", data={"framework": "iso27001", "control_id": "A.6.3", "title": "Training records",
                                            "valid_until": (date.today() + timedelta(days=200)).isoformat()},
                   files={"file": ("training.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["sha256"] and ev["size"] == 13
    assert admin.get(f"{API}/frameworks/iso27001/controls/A.6.3").json()["status"] == "evidenced"
    dl = admin.get(f"{API}/evidence/{ev['id']}/file")
    assert dl.status_code == 200 and dl.content == b"%PDF-1.4 test"
    assert "attachment" in dl.headers["content-disposition"]

    bad = admin.post(f"{API}/evidence", data={"framework": "iso27001", "control_id": "A.6.3", "title": "x"},
                     files={"file": ("x.html", b"<script>", "text/html")})
    assert bad.status_code == 415


def test_exceptions_need_a_second_person(admin):
    body = {"check_id": "github.org_2fa_required", "reason": "Vendor accounts migrate to SSO in Q1",
            "expires_on": (date.today() + timedelta(days=60)).isoformat()}
    x = admin.post(f"{API}/exceptions", json=body).json()
    assert admin.post(f"{API}/exceptions/{x['id']}/decision", json={"approve": True}).status_code == 403

    make_user(admin, "admin2@example.com", "admin")
    switch(admin, "admin2@example.com")
    r = admin.post(f"{API}/exceptions/{x['id']}/decision", json={"approve": True})
    assert r.status_code == 200 and r.json()["status"] == "approved"

    too_long = {**body, "expires_on": (date.today() + timedelta(days=500)).isoformat()}
    assert admin.post(f"{API}/exceptions", json=too_long).status_code == 422


def test_alert_triage(admin, db_url):
    from datetime import datetime, timezone
    from govern.db import session_scope
    from govern.models import Alert, Connector
    with session_scope() as s:
        c = Connector(kind="github", name="g", config={})
        s.add(c)
        s.flush()
        s.add(Alert(connector_id=c.id, rule_id="github.risky_operation", severity="high", title="Repository deleted",
                    occurred_at=datetime.now(timezone.utc), dedup_key="k1", detail={"title_zh": "仓库被删除"}))
    alerts = admin.get(f"{API}/alerts?status=open").json()
    assert alerts["total"] == 1
    a = alerts["items"][0]
    assert a["title"]["zh"] == "仓库被删除" and a["rule"]["en"] == "Risky GitHub operation"
    assert admin.patch(f"{API}/alerts/{a['id']}", json={"status": "resolved"}).status_code == 422
    r = admin.patch(f"{API}/alerts/{a['id']}", json={"status": "resolved", "note": "Planned clean-up, ticket OPS-12"})
    assert r.status_code == 200 and r.json()["notes"][0]["by"] == "admin@example.com"
    ov = admin.get(f"{API}/overview").json()
    assert ov["open_alerts"]["high"] == 0 and len(ov["frameworks"]) == 3
