"""Roll check results, evidence and decisions up into control and framework status.

Status of one control, in order of precedence:
  not_applicable    marked out of scope, with a reason
  fail / partial    an automated check says so (evidence never overrides a failing check)
  pass              every automated check with data passes (risk-accepted failures count here)
  evidenced         no automated data, but current evidence is attached
  evidence_expired  only expired evidence
  no_data           checks exist but none could run (licence, permission, connector missing)
  needs_evidence    nothing automated covers it and nothing is attached
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from govern.catalog.loader import Framework, checks_by_control, frameworks
from govern.models import (
    CheckResult, Connector, ControlApplicability, Evidence, RiskException, ScoreHistory,
)

SCORED = {"pass": 1.0, "evidenced": 1.0, "partial": 0.5}
STATUS_ORDER = ("fail", "partial", "needs_evidence", "evidence_expired", "no_data", "pass", "evidenced",
                "not_applicable")


@dataclass
class CheckState:
    check_id: str
    connector_id: int
    connector_name: str
    status: str  # as evaluated, or "accepted" when an approved exception covers a failure
    raw_status: str
    evaluated_at: str
    result_id: int


@dataclass
class ControlState:
    framework: str
    control_id: str
    status: str
    checks: list[CheckState] = field(default_factory=list)
    mapped_checks: tuple[str, ...] = ()
    evidence_current: int = 0
    evidence_expired: int = 0
    not_applicable_reason: str | None = None


def latest_results(db: Session) -> list[tuple[CheckResult, Connector]]:
    """The most recent result of every check on every enabled connector."""
    newest = (select(CheckResult.connector_id, CheckResult.check_id, func.max(CheckResult.id).label("id"))
              .group_by(CheckResult.connector_id, CheckResult.check_id).subquery())
    rows = db.execute(
        select(CheckResult, Connector).join(newest, CheckResult.id == newest.c.id)
        .join(Connector, Connector.id == CheckResult.connector_id).where(Connector.enabled.is_(True)))
    return [(r, c) for r, c in rows]


def active_exceptions(db: Session, today: date | None = None) -> list[RiskException]:
    today = today or date.today()
    return list(db.scalars(select(RiskException).where(
        RiskException.status == "approved", RiskException.expires_on >= today)))


def evaluate(db: Session, framework_id: str, today: date | None = None) -> list[ControlState]:
    fw: Framework = frameworks()[framework_id]
    today = today or date.today()
    index = checks_by_control()

    results: dict[str, list[CheckState]] = {}
    exceptions = active_exceptions(db, today)
    for result, conn in latest_results(db):
        status = result.status
        if status == "fail" or status == "partial":
            if any(x.check_id == result.check_id and x.connector_id in (None, conn.id) for x in exceptions):
                status = "accepted"
        results.setdefault(result.check_id, []).append(CheckState(
            result.check_id, conn.id, conn.name, status, result.status, result.evaluated_at.isoformat(), result.id))

    na = {a.control_id: a.reason for a in db.scalars(
        select(ControlApplicability).where(ControlApplicability.framework == framework_id))}
    evidence: dict[str, tuple[int, int]] = {}
    for control_id, valid_until in db.execute(
            select(Evidence.control_id, Evidence.valid_until).where(Evidence.framework == framework_id)):
        cur, exp = evidence.get(control_id, (0, 0))
        if valid_until is None or valid_until >= today:
            cur += 1
        else:
            exp += 1
        evidence[control_id] = (cur, exp)

    out = []
    for cid in fw.controls:
        mapped = index.get((framework_id, cid), ())
        states = [s for check_id in mapped for s in results.get(check_id, [])]
        cur, exp = evidence.get(cid, (0, 0))
        st = ControlState(framework_id, cid, "", states, mapped, cur, exp, na.get(cid))
        st.status = _status(st)
        out.append(st)
    return out


def _status(st: ControlState) -> str:
    if st.not_applicable_reason is not None:
        return "not_applicable"
    graded = [s.status for s in st.checks if s.status in ("pass", "partial", "fail", "accepted")]
    if "fail" in graded:
        return "fail"
    if "partial" in graded:
        return "partial"
    if graded:
        return "pass"
    if st.evidence_current:
        return "evidenced"
    if st.evidence_expired:
        return "evidence_expired"
    if st.mapped_checks:
        return "no_data"
    return "needs_evidence"


def summarise(states: list[ControlState]) -> dict:
    counts = {s: 0 for s in STATUS_ORDER}
    for st in states:
        counts[st.status] += 1
    applicable = len(states) - counts["not_applicable"]
    earned = sum(SCORED.get(st.status, 0.0) for st in states)
    automated = sum(1 for st in states if st.status != "not_applicable" and
                    any(c.status in ("pass", "partial", "fail", "accepted") for c in st.checks))
    return {
        "score": round(earned / applicable * 100, 1) if applicable else 0.0,
        "counts": counts,
        "applicable": applicable,
        "total": len(states),
        "automated": automated,  # controls with at least one automated verdict
    }


def record_scores(db: Session) -> None:
    for fw_id in frameworks():
        s = summarise(evaluate(db, fw_id))
        db.add(ScoreHistory(framework=fw_id, score=s["score"], counts=s["counts"]))
