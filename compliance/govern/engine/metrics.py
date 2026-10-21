"""Posture numbers shared by the API and the weekly report."""
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from govern.catalog.loader import posture
from govern.checks.base import load_all as load_checks
from govern.engine.evaluate import latest_results
from govern.engine.findings import due_at, is_overdue
from govern.models import Alert, CheckResult, Connector, Finding
from govern.rules.base import load_all as load_rules
from govern.settings_store import get as get_setting
from govern.timeutil import utcnow

SEVERITIES = ("critical", "high", "medium", "low")
OPEN_ALERT = ("open", "acknowledged")
STATUS_RANK = {"fail": 0, "error": 1, "partial": 2, "accepted": 3, "not_available": 4, "pass": 5}


def posture_summary(db: Session, days: int = 7) -> dict:
    now = utcnow()
    since = now - timedelta(days=days)
    sla = get_setting(db, "sla")
    checks, rules = load_checks(), load_rules()
    enabled = {c.id for c in db.scalars(select(Connector).where(Connector.enabled.is_(True)))}

    results: dict[str, list[CheckResult]] = defaultdict(list)
    for r, conn in latest_results(db):
        results[r.check_id].append(r)
    findings: dict[str, list[Finding]] = defaultdict(list)
    for f in db.scalars(select(Finding).where(Finding.connector_id.in_(enabled),
                                              (Finding.resolved_at.is_(None)) | (Finding.resolved_at >= since))):
        findings[f.check_id].append(f)
    alerts: dict[str, list[Alert]] = defaultdict(list)
    for a in db.scalars(select(Alert).where(Alert.connector_id.in_(enabled),
                                            (Alert.status.in_(OPEN_ALERT)) | (Alert.created_at >= since))):
        alerts[a.rule_id].append(a)

    domains, totals = [], Counter()
    for d in posture():
        items = []
        for it in d.items:
            if it.check:
                ch = checks[it.check]
                rs = results.get(it.check, [])
                fs = findings.get(it.check, [])
                open_ = [f for f in fs if f.resolved_at is None]
                overdue = [f for f in open_ if is_overdue(f, sla, now)]
                status = min((r.status for r in rs), key=lambda s: STATUS_RANK.get(s, 9)) if rs else "no_source"
                entry = {
                    "code": it.code, "type": "check", "id": it.check, "title": ch.title, "severity": ch.severity,
                    "status": status, "sla": it.sla,
                    "summary": {lang: ch.render_summary(lang, rs[0].details.get("params", {})) for lang in ("en", "zh")}
                    if len(rs) == 1 and status not in ("not_available", "error") else None,
                    "result_ids": [r.id for r in rs],
                    "open": len(open_), "overdue": len(overdue),
                    "open_by_severity": dict(Counter(f.severity for f in open_)),
                    "new": sum(1 for f in fs if f.first_seen >= since),
                    "resolved": sum(1 for f in fs if f.resolved_at and f.resolved_at >= since),
                    "oldest_days": max(((now - f.first_seen).days for f in open_), default=None),
                }
            else:
                rule = rules[it.rule]
                al = alerts.get(it.rule, [])
                open_a = [a for a in al if a.status in OPEN_ALERT]
                entry = {
                    "code": it.code, "type": "rule", "id": it.rule, "title": rule.title,
                    "severity": max((a.severity for a in open_a), key=SEVERITIES[::-1].index, default="low"),
                    "status": "fail" if open_a else "pass", "sla": False, "summary": None, "result_ids": [],
                    "open": len(open_a), "overdue": 0,
                    "open_by_severity": dict(Counter(a.severity for a in open_a)),
                    "new": sum(1 for a in al if a.created_at >= since), "resolved": 0, "oldest_days": None,
                }
            items.append(entry)
            totals[entry["status"]] += 1
            totals["open"] += entry["open"]
            totals["overdue"] += entry["overdue"]
            totals["new"] += entry["new"]
            totals["resolved"] += entry["resolved"]
        domains.append({"id": d.id, "source": d.source, "name": d.name, "items": items,
                        "failing": sum(1 for i in items if i["status"] == "fail"),
                        "open": sum(i["open"] for i in items), "overdue": sum(i["overdue"] for i in items)})
    return {"period_days": days, "domains": domains, "totals": dict(totals), "sla": sla}


def check_findings(db: Session, check_id: str, *, include_resolved: bool = False, limit: int = 500,
                   offset: int = 0, overdue_only: bool = False) -> dict:
    sla = get_setting(db, "sla")
    now = utcnow()
    q = select(Finding).where(Finding.check_id == check_id)
    if not include_resolved:
        q = q.where(Finding.resolved_at.is_(None))
    rows = list(db.scalars(q.order_by(Finding.first_seen)))
    if overdue_only:
        rows = [f for f in rows if is_overdue(f, sla, now)]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    rows.sort(key=lambda f: (not is_overdue(f, sla, now), order.get(f.severity, 9), f.first_seen))
    page = rows[offset:offset + limit]
    return {"total": len(rows), "items": [{
        "id": f.id, "key": f.key, "label": f.label, "severity": f.severity, "exploited": f.exploited,
        "data": {k: v for k, v in (f.data or {}).items() if not k.startswith("_")},
        "first_seen": f.first_seen.isoformat(), "last_seen": f.last_seen.isoformat(),
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "due_at": due_at(f, sla).isoformat(), "overdue": is_overdue(f, sla, now),
        "age_days": ((f.resolved_at or now) - f.first_seen).days, "reopened": f.reopened,
    } for f in page]}


def sla_metrics(db: Session, check_ids: tuple[str, ...] = ("m365.vuln_sla",), days: int = 90) -> dict:
    """SLA compliance and mean time to remediate, by severity, for findings resolved in the window."""
    sla = get_setting(db, "sla")
    since = utcnow() - timedelta(days=days)
    resolved = list(db.scalars(select(Finding).where(Finding.check_id.in_(check_ids),
                                                     Finding.resolved_at >= since)))
    open_ = list(db.scalars(select(Finding).where(Finding.check_id.in_(check_ids), Finding.resolved_at.is_(None))))
    out = {}
    for sev in ("exploited",) + SEVERITIES:
        def pick(rows):
            return [f for f in rows if (f.exploited if sev == "exploited" else (f.severity == sev and not f.exploited))]
        done, still = pick(resolved), pick(open_)
        within = [f for f in done if not is_overdue(f, sla)]
        out[sev] = {
            "sla_days": sla.get(sev),
            "resolved": len(done),
            "within_sla_pct": round(len(within) / len(done) * 100, 1) if done else None,
            "mttr_days": round(mean((f.resolved_at - f.first_seen).total_seconds() / 86400 for f in done), 1)
            if done else None,
            "open": len(still),
            "open_overdue": sum(1 for f in still if is_overdue(f, sla)),
        }
    trend = [{"at": r.evaluated_at.isoformat(), "open": (r.details or {}).get("params", {}).get("open")}
             for r in db.scalars(select(CheckResult).where(CheckResult.check_id == check_ids[0],
                                                           CheckResult.evaluated_at >= since)
                                 .order_by(CheckResult.id))]
    return {"window_days": days, "by_severity": out, "trend": trend}
