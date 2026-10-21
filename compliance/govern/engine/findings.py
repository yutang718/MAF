"""Turn check outcomes into findings tracked from first sighting to fix, with remediation SLAs."""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from govern.checks.base import Check, Outcome
from govern.models import Finding
from govern.timeutil import utcnow

GRADED = ("pass", "partial", "fail")
MAX_FINDINGS_PER_CHECK = 100_000
# Fields that identify an item when the check doesn't give an explicit _key, in order of preference.
IDENTITY_FIELDS = ("upn", "login", "username", "user", "repo", "project", "device", "name", "column", "url", "id")
DEFAULT_SLA_DAYS = {"exploited": 7, "critical": 15, "high": 30, "medium": 90, "low": 180}


def item_key(item: dict) -> str:
    if item.get("_key"):
        return str(item["_key"])[:300]
    for field in IDENTITY_FIELDS:
        if item.get(field) not in (None, ""):
            return f"{field}={item[field]}"[:300]
    blob = json.dumps(item, sort_keys=True, default=str)
    return "sha1=" + hashlib.sha1(blob.encode()).hexdigest()


def item_label(item: dict) -> str:
    if item.get("_label"):
        return str(item["_label"])[:500]
    parts = [str(v) for k, v in item.items() if not k.startswith("_") and v not in (None, "", [], {})][:4]
    return " · ".join(parts)[:500]


def public(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


@dataclass
class SyncResult:
    new: int = 0
    resolved: int = 0
    reopened: int = 0
    open: int = 0


def sync(db: Session, connector_id: int, check: Check, outcome: Outcome, now: datetime | None = None) -> SyncResult:
    """Reconcile one check's latest items with its findings. Ungraded outcomes change nothing."""
    res = SyncResult()
    if outcome.status not in GRADED:
        return res
    now = now or utcnow()
    current: dict[str, dict] = {}
    items = outcome.items if outcome.status != "pass" else []
    for item in items[:MAX_FINDINGS_PER_CHECK]:
        current.setdefault(item_key(item), item)
    existing = {f.key: f for f in db.scalars(
        select(Finding).where(Finding.connector_id == connector_id, Finding.check_id == check.id))}

    for key, item in current.items():
        f = existing.get(key)
        severity = item.get("_severity") or check.severity
        if f is None:
            db.add(Finding(connector_id=connector_id, check_id=check.id, key=key, label=item_label(item),
                           severity=severity, exploited=bool(item.get("_exploited")), data=_data(item),
                           first_seen=now, last_seen=now))
            res.new += 1
            continue
        if f.resolved_at is not None:
            # A regression starts a new remediation clock.
            f.resolved_at = None
            f.first_seen = now
            f.reopened += 1
            res.reopened += 1
        f.last_seen = now
        f.label = item_label(item)
        f.severity = severity
        f.exploited = bool(item.get("_exploited"))
        f.data = _data(item)
    for key, f in existing.items():
        if key not in current and f.resolved_at is None:
            f.resolved_at = now
            res.resolved += 1
    res.open = len(current)
    db.flush()
    return res


def _data(item: dict) -> dict:
    out = public(item)
    if item.get("_due_days") is not None:
        out["_due_days"] = item["_due_days"]
    return out


def sla_days(f: Finding, table: dict[str, int]) -> int:
    if f.data and f.data.get("_due_days") is not None:
        return int(f.data["_due_days"])
    if f.exploited:
        return int(table.get("exploited", DEFAULT_SLA_DAYS["exploited"]))
    return int(table.get(f.severity, DEFAULT_SLA_DAYS.get(f.severity, 90)))


def due_at(f: Finding, table: dict[str, int]) -> datetime:
    return f.first_seen + timedelta(days=sla_days(f, table))


def is_overdue(f: Finding, table: dict[str, int], now: datetime | None = None) -> bool:
    now = now or utcnow()
    end = f.resolved_at or now
    return end > due_at(f, table)


def sla_graded_status(db: Session, connector_id: int, check_id: str, table: dict[str, int]) -> str:
    """For SLA-driven checks: fail when anything is past due, partial while open within SLA."""
    open_ = list(db.scalars(select(Finding).where(
        Finding.connector_id == connector_id, Finding.check_id == check_id, Finding.resolved_at.is_(None))))
    if any(is_overdue(f, table) for f in open_):
        return "fail"
    return "partial" if open_ else "pass"
