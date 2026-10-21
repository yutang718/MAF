"""Security posture: self-managed GitLab, Entra cross-checks, M365 security collection, findings and SLA."""
import json
from datetime import timedelta

import httpx
from sqlalchemy import select

from govern.checks.identity import EntraIndex, classify
from govern.connectors.base import Collected
from govern.connectors.gitlab import GitLabConnector, parse_version, ssh_key_strength
from govern.connectors.m365 import M365Connector
from govern.engine.collector import evaluate_checks, run_connector
from govern.models import Alert, CheckResult, Connector, Finding
from tests import fixtures_security as fs
from tests.test_connectors import m365_routes, router

ENTRA_FACTS = {"m365": {"entra.users": fs.ENTRA_USERS, "entra.domains": fs.ENTRA_DOMAINS}}


def gitlab_collect():
    transport, calls = router(fs.gitlab_routes())
    conn = GitLabConnector({"base_url": "https://gitlab.evyd.com"}, {"token": "t"}, transport=transport,
                           sleep=lambda s: None)
    return conn.collect(), calls


def grade(kind, facts, cross=None, config=None):
    row = Connector(id=1, kind=kind, name="t", config=config or {})
    return evaluate_checks(row, facts, {}, {}, cross or {})


# ─── GitLab collection ─────────────────────────────────────────────────────────

def test_gitlab_admin_collection():
    c, calls = gitlab_collect()
    assert not c.errors, c.errors
    assert {"gitlab.users", "gitlab.tokens", "gitlab.ssh_keys", "gitlab.mirrors", "gitlab.ci_variables",
            "gitlab.group_members", "gitlab.project_members", "gitlab.upstream"} <= set(c.facts)
    # Only selected settings are kept, and CI variable values never are.
    assert "some_secret_setting" not in c.facts["gitlab.settings"]
    assert "SHOULD-NOT-BE-STORED" not in json.dumps(c.facts)
    # Mirror credentials are dropped: host and path only.
    assert all("*" not in m["host"] for m in c.facts["gitlab.mirrors"])
    # SSH keys are fetched only for active humans (not the bot or the blocked user).
    assert not any("/users/6/keys" in str(x.url) or "/users/7/keys" in str(x.url) for x in calls)
    assert c.events[0].kind == "gitlab.audit"


def test_ssh_key_and_version_parsing():
    assert ssh_key_strength(fs.WEAK_RSA) == ("ssh-rsa", 1024)
    assert ssh_key_strength(fs.STRONG)[0] == "ssh-ed25519"
    assert ssh_key_strength("garbage") == ("unknown", None)
    assert parse_version("v17.3.2-ee") == (17, 3, 2) and parse_version("17.3") is None


def test_identity_matching():
    index = EntraIndex(fs.ENTRA_USERS)
    u = lambda **kw: {"username": "x", "email": "", "identities": [], "bot": False, **kw}  # noqa: E731
    assert classify(u(identities=[{"provider": "saml", "extern_uid": "alice@evyd.com"}]), index, {"evyd.com"}, set()).status == "active"
    assert classify(u(email="bob@evyd.com"), index, {"evyd.com"}, set()).status == "disabled"
    assert classify(u(email="carol@evyd.com"), index, {"evyd.com"}, set()).status == "missing"
    assert classify(u(email="x@gmail.com"), index, {"evyd.com"}, set()).status == "non_corporate"
    assert classify(u(username="svc-ci", email="x@gmail.com"), index, set(), {"svc-ci"}).status == "service"


def test_gitlab_checks_with_entra():
    c, _ = gitlab_collect()
    r = grade("gitlab", c.facts, ENTRA_FACTS, {"base_url": "https://gitlab.evyd.com"})
    status = {k: v.status for k, v in r.items()}

    leavers = {i["username"]: i["reason"] for i in r["gitlab.leavers"].items}
    assert leavers == {"bob": "disabled", "carol": "missing"}
    creds = {(i["username"], i["credential"]) for i in r["gitlab.leaver_credentials"].items}
    assert creds == {("bob", "token"), ("bob", "ssh_key")}
    assert [i["username"] for i in r["gitlab.leaver_activity"].items] == ["bob"]  # carol idle 120 days
    assert {i["username"] for i in r["gitlab.non_corporate_users"].items} == {"vendor-x"}
    assert {i["username"] for i in r["gitlab.dormant_users"].items} == {"carol"}
    admins = {i["username"]: i["identity"] for i in r["gitlab.instance_admins"].items}
    assert admins == {"carol": "missing"}

    assert status["gitlab.password_login"] == "fail"
    assert status["gitlab.signup"] == "fail"
    assert status["gitlab.user_2fa"] == "fail"
    assert {i["group"] for i in r["gitlab.maintainer_sprawl"].items} == {"evyd"}
    assert [i["username"] for i in r["gitlab.direct_project_members"].items] == ["vendor-x"]
    assert {i["where"] for i in r["gitlab.external_member_expiry"].items} == {"evyd", "evyd/platform/api"}
    tokens = {i["name"]: i["_severity"] for i in r["gitlab.risky_tokens"].items}
    assert tokens == {"laptop": "high", "automation": "critical"}
    assert [i["name"] for i in r["gitlab.idle_tokens"].items] == ["old-script"]
    assert [i["username"] for i in r["gitlab.weak_ssh_keys"].items] == ["bob"]
    assert [i["key"] for i in r["gitlab.ci_secret_variables"].items] == ["AWS_SECRET_ACCESS_KEY"]
    assert [i["host"] for i in r["gitlab.external_mirrors"].items] == ["github.com"]  # git.evyd.com is internal
    assert [i["project"] for i in r["gitlab.personal_forks"].items] == ["bob/api"]
    assert [i["project"] for i in r["gitlab.project_visibility"].items] == ["evyd/platform/api"]
    assert status["gitlab.writable_deploy_keys"] == "partial"
    assert status["gitlab.version_patch"] == "fail"  # 17.3.2, oldest missing patch 60 days old
    assert "17.3.7" in r["gitlab.version_patch"].params["result"]


def test_gitlab_cross_checks_need_m365():
    c, _ = gitlab_collect()
    r = grade("gitlab", c.facts, {"m365": None})
    assert r["gitlab.leavers"].status == "not_available"
    assert "needs a m365 data source" in json.dumps(r["gitlab.leavers"].params)
    assert r["gitlab.dormant_users"].status != "not_available"  # doesn't need Entra


def test_unsupported_gitlab_version():
    c, _ = gitlab_collect()
    c.facts["gitlab.upstream"]["installed"] = "16.11.0-ee"
    r = grade("gitlab", c.facts, ENTRA_FACTS)
    assert r["gitlab.version_patch"].status == "fail"
    assert "no longer gets security fixes" in r["gitlab.version_patch"].params["result"]


# ─── M365 security collection ──────────────────────────────────────────────────

def m365_security_collect(cursor=None, **overrides):
    routes = {**m365_routes(), **fs.m365_security_routes(), "/v1.0/users": {"value": fs.ENTRA_USERS}, **overrides}
    transport, calls = router(routes)
    conn = M365Connector({"tenant_id": "tenant-1", "client_id": "app", "break_glass_accounts": ["breakglass@evyd.com"]},
                         {"client_secret": "s"}, cursor, transport=transport, sleep=lambda s: None)
    return conn.collect(), calls


def test_m365_security_collection_and_checks():
    c, _ = m365_security_collect()
    assert {"defender.vulnerabilities", "defender.secure_config", "defender.eos_software", "threat.kev",
            "sharepoint.settings", "entra.pim_active", "entra.app_registrations", "m365.download_history"} <= set(c.facts)
    assert c.facts["m365.download_history"]["bob@evyd.com"]
    assert any(e.kind == "m365.download_summary" and e.data["files"] == 150 for e in c.events)
    assert "download_query" not in c.cursor and c.cursor["downloads_until"]

    r = grade("m365", c.facts, config={"break_glass_accounts": ["breakglass@evyd.com"]})
    vulns = {i["cve"]: (i["_severity"], i["_exploited"]) for i in r["m365.vuln_sla"].items}
    assert vulns == {"CVE-2024-0001": ("high", False), "CVE-2023-4863": ("critical", True),  # KEV
                     "CVE-2024-0003": ("critical", True)}  # public exploit
    assert {i["cve"] for i in r["m365.exploited_vulns"].items} == {"CVE-2023-4863", "CVE-2024-0003"}
    assert r["m365.tamper_protection"].items[0]["device"] == "pc-bob"
    assert r["m365.av_health"].items[0]["device"] == "pc-bob"
    assert r["m365.asr_rules"].items[0]["device"] == "pc-alice"
    assert r["m365.end_of_support"].status == "fail"
    assert r["m365.external_sharing"].status == "fail"
    # Principals resolved from the user list first, then getByIds; break-glass excluded.
    assert sorted(i["principal"] for i in r["m365.permanent_privileged_roles"].items) == \
        ["Legacy automation", "dave@evyd.com"]
    apps = {i["app"]: i["reason"] for i in r["m365.risky_app_registrations"].items}
    assert list(apps) == ["Mail sync tool"] and "Mail.ReadWrite" in apps["Mail sync tool"]
    assert r["m365.risky_app_registrations"].status == "fail"


def test_leaver_downloads_and_onboarding_gap():
    facts = {"m365.download_history": {"bob@evyd.com": {fs.day(3): 120, fs.day(1): 30}},
             "entra.users": fs.ENTRA_USERS,
             "intune.devices": [{"id": "i1", "deviceName": "PC-1", "operatingSystem": "Windows", "azureADDeviceId": "x"},
                                {"id": "i2", "deviceName": "PC-2", "operatingSystem": "Windows", "azureADDeviceId": "y"},
                                {"id": "i3", "deviceName": "phone", "operatingSystem": "iOS"}],
             "defender.machines": [{"computerDnsName": "pc-1.evyd.local", "aadDeviceId": None}]}
    r = grade("m365", facts)
    assert r["m365.leaver_downloads"].items[0]["files_30d"] == 150
    assert [i["device"] for i in r["m365.mde_onboarding_gap"].items] == ["PC-2"]


def test_audit_query_still_running_is_picked_up_next_run():
    routes = {"/beta/security/auditLog/queries/q1": {"id": "q1", "status": "running"}}
    c, _ = m365_security_collect(**routes)
    assert c.cursor["download_query"]["id"] == "q1" and not any(e.kind == "m365.download_summary" for e in c.events)
    # Next run: finished.
    c2, _ = m365_security_collect(cursor=c.cursor)
    assert any(e.kind == "m365.download_summary" for e in c2.events) and "download_query" not in c2.cursor


def test_hunting_unavailable_without_licence():
    c, _ = m365_security_collect(**{"/v1.0/security/runHuntingQuery": (403, {"error": {"message": "no MDE"}})})
    assert "defender.vulnerabilities" in c.unavailable
    assert grade("m365", c.facts)["m365.vuln_sla"].status == "not_available"


# ─── Findings, SLA and cross re-evaluation ─────────────────────────────────────

class Fake:
    def __init__(self, collected):
        self.collected = collected

    def collect(self):
        return self.collected

    def close(self):
        pass


def vuln_facts(rows):
    return {"defender.vulnerabilities": rows, "threat.kev": []}


def vrow(dev, cve, sev="High", exploit=False):
    return {"DeviceId": dev, "DeviceName": dev, "CveId": cve, "SoftwareName": "s", "SoftwareVersion": "1",
            "VulnerabilitySeverityLevel": sev, "IsExploitAvailable": exploit}


def test_findings_lifecycle_and_sla(db):
    c = Connector(kind="m365", name="m", config={})
    db.add(c)
    db.commit()
    run_connector(db, c.id, lambda row: Fake(Collected(facts=vuln_facts([vrow("d1", "CVE-1"), vrow("d2", "CVE-2")]))))
    fnd = {f.key: f for f in db.scalars(select(Finding).where(Finding.check_id == "m365.vuln_sla"))}
    assert set(fnd) == {"d1|CVE-1", "d2|CVE-2"}
    latest = db.scalar(select(CheckResult).where(CheckResult.check_id == "m365.vuln_sla").order_by(CheckResult.id.desc()))
    assert latest.status == "partial"  # open but within the 30-day high SLA

    # Age one finding past its SLA: the SLA-graded check now fails.
    fnd["d1|CVE-1"].first_seen -= timedelta(days=31)
    db.commit()
    run_connector(db, c.id, lambda row: Fake(Collected(facts=vuln_facts([vrow("d1", "CVE-1")]))))
    latest = db.scalar(select(CheckResult).where(CheckResult.check_id == "m365.vuln_sla").order_by(CheckResult.id.desc()))
    assert latest.status == "fail"
    db.expire_all()
    fnd = {f.key: f for f in db.scalars(select(Finding).where(Finding.check_id == "m365.vuln_sla"))}
    assert fnd["d2|CVE-2"].resolved_at is not None and fnd["d1|CVE-1"].resolved_at is None

    # Missing data resolves nothing.
    run_connector(db, c.id, lambda row: Fake(Collected(facts={}, unavailable={"defender.vulnerabilities": "403"})))
    db.expire_all()
    assert db.get(Finding, fnd["d1|CVE-1"].id).resolved_at is None

    # Fixed, then back: reopened with a fresh clock.
    run_connector(db, c.id, lambda row: Fake(Collected(facts=vuln_facts([]))))
    run_connector(db, c.id, lambda row: Fake(Collected(facts=vuln_facts([vrow("d1", "CVE-1")]))))
    db.expire_all()
    f = db.get(Finding, fnd["d1|CVE-1"].id)
    assert f.resolved_at is None and f.reopened == 1


def test_entra_run_reevaluates_gitlab_leavers(db):
    m365 = Connector(kind="m365", name="m", config={})
    gitlab = Connector(kind="gitlab", name="g", config={})
    db.add_all([m365, gitlab])
    db.commit()
    entra_all_active = [{**u, "accountEnabled": True} for u in fs.ENTRA_USERS]
    run_connector(db, m365.id, lambda row: Fake(Collected(facts={"entra.users": entra_all_active,
                                                                 "entra.domains": fs.ENTRA_DOMAINS})))
    c, _ = gitlab_collect()
    run_connector(db, gitlab.id, lambda row: Fake(c))
    open_leavers = lambda: {f.key for f in db.scalars(select(Finding).where(  # noqa: E731
        Finding.check_id == "gitlab.leavers", Finding.resolved_at.is_(None)))}
    assert open_leavers() == {"carol"}
    # Bob is disabled in Entra: the M365 run alone must flag him in GitLab.
    run_connector(db, m365.id, lambda row: Fake(Collected(facts={"entra.users": fs.ENTRA_USERS,
                                                                 "entra.domains": fs.ENTRA_DOMAINS})))
    db.expire_all()
    assert open_leavers() == {"bob", "carol"}


# ─── Log ingestion ─────────────────────────────────────────────────────────────

def _log_lines(user="eve", repos=25):
    now = fs.ago(0.01)
    lines = [{"time": now, "controller": "Repositories::GitHttpController", "action": "git_upload_pack",
              "status": 200, "username": user, "meta.project": f"evyd/r{i}", "remote_ip": "10.0.0.5"}
             for i in range(repos)]
    lines.append({"time": now, "command": "git-upload-pack", "msg": "executing git command", "username": user,
                  "gl_project_path": "evyd/ssh-repo"})
    lines.append({"log": json.dumps({"time": now, "route": "/api/:version/projects/:id/export/download",
                                     "status": 200, "username": user, "meta.project": "evyd/secret"})})
    lines.append({"time": now, "controller": "Repositories::GitHttpController", "action": "info_refs",
                  "status": 200, "username": user})  # not a download
    lines.append({"time": now, "controller": "Repositories::GitHttpController", "action": "git_upload_pack",
                  "status": 200, "username": "gitlab-ci-token", "meta.project": "evyd/r1"})
    return "\n".join(json.dumps(x) for x in lines)


def test_log_ingestion(admin):
    API = "/api/v1/governance"
    r = admin.post(f"{API}/connectors", json={
        "kind": "gitlab", "name": "GitLab", "config": {"base_url": "https://gitlab.evyd.com"},
        "secrets": {"token": "t", "log_ingest_token": "ingest-secret-0123456789"}})
    cid = r.json()["id"]
    url = f"{API}/ingest/gitlab/{cid}"
    assert admin.post(url, content="{}", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert admin.post(f"{API}/ingest/gitlab/999", content="{}",
                      headers={"Authorization": "Bearer ingest-secret-0123456789"}).status_code == 401
    r = admin.post(url, content=_log_lines(), headers={"Authorization": "Bearer ingest-secret-0123456789"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["downloads"] == 28 and body["alerts"] == 2  # bulk download + project export; CI excluded from bulk
    again = admin.post(url, content=_log_lines(), headers={"Authorization": "Bearer ingest-secret-0123456789"}).json()
    assert again["new"] == 0  # same lines are not counted twice
    alerts = admin.get(f"{API}/alerts").json()["items"]
    assert {a["rule_id"] for a in alerts} == {"gitlab.bulk_download", "gitlab.project_export"}


# ─── Posture API, settings, Teams ──────────────────────────────────────────────

def test_posture_api_and_settings(admin, db_url):
    API = "/api/v1/governance"
    p = admin.get(f"{API}/posture").json()
    codes = [i["code"] for d in p["domains"] for i in d["items"]]
    assert codes[0] == "GL-ID-01" and "VM-01" in codes and "DP-04" in codes
    assert all(i["status"] == "no_source" for d in p["domains"] for i in d["items"] if i["type"] == "check")
    assert admin.get(f"{API}/posture/checks/nope/findings").status_code == 404
    assert admin.get(f"{API}/posture/sla").json()["by_severity"]["exploited"]["sla_days"] == 7

    assert admin.put(f"{API}/settings/sla", json={"exploited": 7, "critical": 15, "high": 30, "medium": 90,
                                                   "low": 400}).status_code == 422
    assert admin.put(f"{API}/settings/notify", json={"teams_webhook": "http://insecure"}).status_code == 422
    r = admin.put(f"{API}/settings/notify", json={"enabled": True, "weekday": 1, "hour": 9, "timezone": "Asia/Brunei",
                                                  "teams_webhook": "https://example.logic.azure.com/workflows/abc"})
    assert r.status_code == 200 and r.json()["webhook_set"] is True
    assert "workflows/abc" not in admin.get(f"{API}/settings/notify").text


def test_weekly_report_schedule_and_card(db):
    from govern import notify
    from govern.settings_store import put, put_secret
    put(db, "report", {"enabled": True, "weekday": 1, "hour": 9, "timezone": "Asia/Brunei",
                       "base_url": "https://maf.evyd.com"})
    put_secret(db, notify.SECRET_KEY, {"teams_webhook": "https://example.logic.azure.com/x"})
    db.commit()
    sent = []
    transport = httpx.MockTransport(lambda req: sent.append(json.loads(req.content)) or httpx.Response(202))
    # Monday 2026-10-19 09:00 Brunei = 01:00 UTC. At 02:00 UTC it's due; sending twice doesn't repeat.
    from datetime import datetime, timezone
    monday = datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc)
    assert notify.last_slot({"weekday": 1, "hour": 9, "timezone": "Asia/Brunei"}, monday) == \
        datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc)
    assert notify.send_weekly_if_due(db, monday, transport) is True
    assert notify.send_weekly_if_due(db, monday + timedelta(hours=3), transport) is False
    assert notify.send_weekly_if_due(db, monday + timedelta(days=7), transport) is True
    card = sent[0]["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard" and card["actions"][0]["url"] == "https://maf.evyd.com/governance"


def test_critical_alerts_are_pushed(db):
    from govern import notify
    from govern.settings_store import put_secret
    put_secret(db, notify.SECRET_KEY, {"teams_webhook": "https://example.logic.azure.com/x"})
    c = Connector(kind="github", name="g", config={})
    db.add(c)
    db.flush()
    from datetime import datetime, timezone
    hi = Alert(connector_id=c.id, rule_id="r", severity="high", title="t", occurred_at=datetime.now(timezone.utc),
               dedup_key="a")
    crit = Alert(connector_id=c.id, rule_id="r", severity="critical", title="Leaver cloned 300 repos",
                 occurred_at=datetime.now(timezone.utc), dedup_key="b", detail={"title_zh": "离职人员克隆了 300 个仓库"})
    db.add_all([hi, crit])
    db.commit()
    sent = []
    transport = httpx.MockTransport(lambda req: sent.append(json.loads(req.content)) or httpx.Response(202))
    assert notify.push_new_critical(db, [hi.id, crit.id], transport) == 1
    assert "离职人员" in json.dumps(sent[0], ensure_ascii=False)


def test_retention_labels_server_error_is_unavailable():
    c, _ = m365_security_collect(**{"/v1.0/security/labels/retentionLabels": (500, {"error": {"message": "boom"}})})
    assert "purview.retention_labels" in c.unavailable and "purview.retention_labels" not in c.errors


def test_alert_findings_start_the_clock_when_the_alert_was_raised(db):
    c = Connector(kind="m365", name="m", config={})
    db.add(c)
    db.commit()
    old = {"id": "al1", "title": "DLP", "severity": "high", "serviceSource": "dataLossPrevention",
           "createdDateTime": fs.ago(10)}
    run_connector(db, c.id, lambda row: Fake(Collected(facts={"defender.alerts_open": [old]})))
    f = db.scalar(select(Finding).where(Finding.check_id == "m365.dlp_alert_sla"))
    assert (fs.NOW - f.first_seen).days == 10
    latest = db.scalar(select(CheckResult).where(CheckResult.check_id == "m365.dlp_alert_sla")
                       .order_by(CheckResult.id.desc()))
    assert latest.status == "fail"  # high DLP alerts must be triaged within 1 day
    keys = {x.key for x in db.scalars(select(Finding).where(Finding.check_id == "m365.data_loss_alerts"))}
    assert keys == {"al1"}


def test_missing_licence_reported_as_400_is_unavailable():
    no_p2 = (400, {"error": {"code": "AadPremiumLicenseRequired",
                             "message": "The tenant needs to have Microsoft Entra ID P2 or Microsoft Entra ID Governance license."}})
    c, _ = m365_security_collect(**{"/v1.0/roleManagement/directory/roleAssignmentScheduleInstances": no_p2})
    assert "entra.pim_active" in c.unavailable and "entra.pim_active" not in c.errors
    r = grade("m365", c.facts)["m365.permanent_privileged_roles"]
    assert r.status in ("pass", "fail") and "PIM not available" in r.params["pim_note"]
