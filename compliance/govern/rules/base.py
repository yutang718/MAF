"""Alert rules: turn newly ingested events into risk alerts.

A rule sees the events this run added plus a context for looking back at
history (baselines) and at the connector's latest facts. Alerts are keyed by a
dedup key, so re-running over the same events, or more activity in the same
window, updates one alert instead of raising another.
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from govern.models import CollectionRun, Connector, Event, Snapshot

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class AlertDraft:
    rule_id: str
    severity: str
    title: str
    title_zh: str
    occurred_at: datetime
    dedup_key: str
    actor: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str  # connector kind
    title: dict[str, str]
    description: dict[str, str]
    defaults: dict[str, Any]
    fn: Callable[["RuleContext", list[Event]], Iterable[AlertDraft]]


RULES: dict[str, Rule] = {}


def rule(id: str, kind: str, *, title: dict, description: dict, defaults: dict | None = None):
    def register(fn):
        assert id not in RULES, f"duplicate rule {id}"
        RULES[id] = Rule(id, kind, title, description, defaults or {}, fn)
        return fn
    return register


class RuleContext:
    def __init__(self, db: Session, connector: Connector, params: dict[str, Any]):
        self.db = db
        self.connector = connector
        self.params = params

    def count(self, *, kind: str, actor: str | None, start: datetime, end: datetime,
              actions: Iterable[str] | None = None) -> int:
        q = select(func.count(Event.id)).where(
            Event.connector_id == self.connector.id, Event.kind == kind,
            Event.occurred_at >= start, Event.occurred_at < end)
        if actor is not None:
            q = q.where(Event.actor == actor)
        if actions is not None:
            q = q.where(Event.action.in_(list(actions)))
        return self.db.scalar(q) or 0

    def events(self, *, kind: str, actor: str, start: datetime, end: datetime,
               actions: Iterable[str] | None = None) -> list[Event]:
        q = select(Event).where(
            Event.connector_id == self.connector.id, Event.kind == kind, Event.actor == actor,
            Event.occurred_at >= start, Event.occurred_at < end)
        if actions is not None:
            q = q.where(Event.action.in_(list(actions)))
        return list(self.db.scalars(q))

    def baseline_daily(self, *, kind: str, actor: str, before: datetime, days: int = 30,
                       actions: Iterable[str] | None = None) -> float:
        """Mean events per day for this actor over the `days` before `before`."""
        return self.count(kind=kind, actor=actor, start=before - timedelta(days=days), end=before,
                          actions=actions) / days

    def latest_fact(self, key: str) -> Any:
        row = self.db.execute(
            select(Snapshot.data).join(CollectionRun, Snapshot.run_id == CollectionRun.id)
            .where(CollectionRun.connector_id == self.connector.id, Snapshot.key == key)
            .order_by(CollectionRun.id.desc()).limit(1)).first()
        return row[0] if row else None


def day_bounds(moment: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(moment.astimezone(timezone.utc).date(), time(), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


class WorkHours:
    """Working-hours test in the source's own time zone, e.g. "08:00-19:00" on days 1–5."""

    def __init__(self, tz: str, hours: str, days: Iterable[int]):
        self.tz = ZoneInfo(tz or "UTC")
        start, _, end = (hours or "00:00-24:00").partition("-")
        self.start = _minutes(start)
        self.end = _minutes(end)
        self.days = {int(d) for d in days}

    def contains(self, moment: datetime) -> bool:
        local = moment.astimezone(self.tz)
        if local.isoweekday() not in self.days:
            return False
        minute = local.hour * 60 + local.minute
        return self.start <= minute < self.end


def _minutes(hhmm: str) -> int:
    h, _, m = hhmm.strip().partition(":")
    return int(h) * 60 + int(m or 0)


def load_all() -> dict[str, Rule]:
    from govern.rules import archery, codehost, m365  # noqa: F401
    return RULES
