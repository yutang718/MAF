"""Collector → checks → alerts → control status, with a fake source."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from govern.connectors.base import Collected, EventRecord
from govern.engine.collector import run_connector
from govern.engine.evaluate import evaluate, summarise
from govern.models import Alert, CheckResult, Connector, Evidence, RiskException, User

NOW = datetime.now(timezone.utc)


class FakeSource:
    def __init__(self, collected):
        self.collected = collected

    def collect(self):
        return self.collected

    def close(self):
        pass


def github_collected(events=(), **facts):
    base = {
        "github.org": {"two_factor_requirement_enabled": False, "default_repository_permission": "read"},
        "github.members": [{"login": "a", "role": "admin"}, {"login": "b", "role": "admin"}],
        "github.repos": [{"name": "api", "visibility": "private", "archived": False,
                          "secret_scanning": "enabled", "push_protection": "enabled"}],
        "audit.events": {"count": len(events), "since": None},
    }
    base.update(facts)
    return Collected(facts=base, events=list(events), cursor={"audit_since": "x"})


def clones(actor, n, start=0):
    return [EventRecord("github.audit", f"{actor}-{start + i}", NOW - timedelta(minutes=5), actor, "git.clone",
                        f"acme/repo{start + i}") for i in range(n)]


def make_connector(db, kind="github"):
    c = Connector(kind=kind, name=f"{kind} test", config={})
    db.add(c)
    db.commit()
    return c


def test_run_stores_results_and_raises_alerts(db):
    c = make_connector(db)
    events = clones("eve", 25) + [EventRecord("github.audit", "vis", NOW, "own1", "repo.access", "acme/site",
                                              {"visibility": "public"})]
    run = run_connector(db, c.id, lambda row: FakeSource(github_collected(events)))
    assert run.status == "ok" and run.stats["new_events"] == 26
    db.refresh(c)
    assert c.cursor == {"audit_since": "x"} and c.last_status == "ok" and c.running_since is None

    alerts = {a.rule_id: a for a in db.scalars(select(Alert))}
    assert alerts["github.bulk_download"].severity == "high"
    assert alerts["github.bulk_download"].detail["repositories"] == 25
    assert alerts["github.risky_operation"].severity == "critical"

    statuses = {r.check_id: r.status for r in db.scalars(select(CheckResult))}
    assert statuses["github.org_2fa_required"] == "fail"
    assert statuses["github.owner_count"] == "pass"
    assert statuses["github.webhooks_secure"] == "not_available"


def test_rerun_dedups_events_and_updates_alerts(db):
    c = make_connector(db)
    run_connector(db, c.id, lambda row: FakeSource(github_collected(clones("eve", 25))))
    # Same events again plus more activity the same day: one alert, refreshed counts.
    run = run_connector(db, c.id, lambda row: FakeSource(github_collected(clones("eve", 30))))
    assert run.stats["new_events"] == 5
    bulk = list(db.scalars(select(Alert).where(Alert.rule_id == "github.bulk_download")))
    assert len(bulk) == 1 and bulk[0].detail["repositories"] == 30


def test_allowlisted_actor_is_not_alerted(db):
    c = make_connector(db)
    c.config = {"rules": {"github.bulk_download": {"actor_allowlist": ["ci-bot"]}}}
    db.commit()
    run_connector(db, c.id, lambda row: FakeSource(github_collected(clones("ci-bot", 40))))
    assert not list(db.scalars(select(Alert)))


def test_failed_collection_keeps_cursor_and_records_error(db):
    c = make_connector(db)
    c.cursor = {"audit_since": "before"}
    db.commit()

    class Broken:
        def collect(self):
            raise PermissionError("token revoked")

        def close(self):
            pass
    run = run_connector(db, c.id, lambda row: Broken())
    db.refresh(c)
    assert run.status == "error" and "token revoked" in run.error
    assert c.cursor == {"audit_since": "before"} and c.running_since is None


def test_a_running_connector_is_not_claimed_twice(db):
    c = make_connector(db)
    c.running_since = NOW
    db.commit()
    assert run_connector(db, c.id, lambda row: FakeSource(github_collected())) is None


def test_control_status_rolls_up_checks_evidence_and_exceptions(db):
    c = make_connector(db)
    admin = db.scalar(select(User))
    run_connector(db, c.id, lambda row: FakeSource(github_collected()))

    def status(fw, cid):
        return next(s for s in evaluate(db, fw) if s.control_id == cid).status

    # A.8.5 secure authentication: github.org_2fa_required fails.
    assert status("iso27001", "A.8.5") == "fail"
    # A.6.1 screening: nothing automated.
    assert status("iso27001", "A.6.1") == "needs_evidence"
    db.add(Evidence(framework="iso27001", control_id="A.6.1", title="Screening procedure", uploaded_by=admin.id))
    db.add(Evidence(framework="iso27001", control_id="A.6.2", title="Old contract template", uploaded_by=admin.id,
                    valid_until=date.today() - timedelta(days=1)))
    db.commit()
    assert status("iso27001", "A.6.1") == "evidenced"
    assert status("iso27001", "A.6.2") == "evidence_expired"
    # Mapped only to M365 checks, and no M365 connector: no data.
    assert status("iso27001", "A.8.7") == "no_data"

    # An approved exception turns the failure into an accepted risk; the control then passes...
    for check in ("github.org_2fa_required", "github.members_without_2fa"):
        db.add(RiskException(check_id=check, reason="r" * 20, expires_on=date.today() + timedelta(days=30),
                             status="approved", requested_by=admin.id, decided_by=admin.id))
    db.commit()
    assert status("hipaa", "164.312(d)") == "pass"
    st = next(s for s in evaluate(db, "iso27001") if s.control_id == "A.8.5")
    assert {x.check_id: x.status for x in st.checks}["github.org_2fa_required"] == "accepted"
    summary = summarise(evaluate(db, "iso27001"))
    assert summary["total"] == 93 and 0 <= summary["score"] <= 100
