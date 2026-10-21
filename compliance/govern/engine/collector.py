"""One collection run: pull from a connector, store, evaluate checks, raise alerts."""
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from govern.checks.base import MAX_ITEMS, Outcome, load_all as load_checks
from govern.config import get_settings
from govern.connectors.base import Collected, Connector as SourceConnector
from govern.connectors.registry import CONNECTOR_TYPES
from govern.engine.evaluate import record_scores
from govern.log import get_logger
from govern.models import Alert, CheckResult, CollectionRun, Connector, Event, Snapshot
from govern.rules.base import SEVERITY_RANK, RuleContext, load_all as load_rules
from govern.security.crypto import decrypt_secrets
from govern.timeutil import utcnow

logger = get_logger(__name__)

# A run older than this is presumed dead (worker crashed) and may be retried.
STALE_RUN = timedelta(hours=2)

SourceFactory = Callable[[Connector], SourceConnector]


def default_factory(row: Connector) -> SourceConnector:
    return CONNECTOR_TYPES[row.kind](row.config, decrypt_secrets(row.secrets_enc), row.cursor)


def claim(db: Session, connector_id: int) -> bool:
    """Mark a connector as running unless another worker already has it. Atomic."""
    now = utcnow()
    res = db.execute(
        update(Connector)
        .where(Connector.id == connector_id,
               (Connector.running_since.is_(None)) | (Connector.running_since < now - STALE_RUN))
        .values(running_since=now, run_requested=False))
    db.commit()
    return res.rowcount == 1


def run_connector(db: Session, connector_id: int, factory: SourceFactory = default_factory) -> CollectionRun | None:
    if not claim(db, connector_id):
        logger.info(f"connector {connector_id} is already running; skipped")
        return None
    row = db.get(Connector, connector_id)
    run = CollectionRun(connector_id=row.id)
    db.add(run)
    db.commit()
    source = None
    try:
        source = factory(row)
        collected = source.collect()
        _store(db, row, run, collected)
        run.status = "partial" if (collected.errors or _event_feed_failed(collected)) else "ok"
        run.error = "; ".join(f"{k}: {v}" for k, v in collected.errors.items())[:4000]
        row.cursor = collected.cursor
        row.last_error = run.error
    except Exception as e:
        logger.exception(f"collection for connector {row.id} failed")
        db.rollback()
        run = db.get(CollectionRun, run.id)
        row = db.get(Connector, connector_id)
        run.status = "error"
        run.error = f"{type(e).__name__}: {e}"[:4000]
        row.last_error = run.error
    finally:
        if source is not None:
            source.close()
    run.finished_at = utcnow()
    row.last_run_at = run.finished_at
    row.last_status = run.status
    row.running_since = None
    db.commit()
    if run.status != "error":
        _prune(db, row.id)
        record_scores(db)
        db.commit()
    notify_new_alerts(db)
    return run


def notify_new_alerts(db: Session) -> None:
    """Post alerts raised in this session to Teams, after they are committed."""
    from govern.notify import push_new_critical
    ids = db.info.pop("new_alert_ids", [])
    push_new_critical(db, ids)


def _event_feed_failed(c: Collected) -> bool:
    return any(k.startswith("events.") or k == "audit.events" for k in c.errors)


def _store(db: Session, row: Connector, run: CollectionRun, c: Collected) -> None:
    facts = dict(c.facts)
    for key in c.carry_forward:
        previous = _previous_fact(db, row.id, key)
        if previous is not None:
            facts[key] = previous
    for key, value in facts.items():
        db.add(Snapshot(run_id=run.id, key=key, data=value))
    run.unavailable = c.unavailable

    new_events = _insert_events(db, row, c)
    results = evaluate_checks(row, facts, c.unavailable, c.errors, cross_facts(db, row))
    findings = record_results(db, row, run.id, results)
    alerts = raise_alerts(db, row, new_events)
    run.stats = {"facts": len(facts), "unavailable": len(c.unavailable), "events": len(c.events),
                 "new_events": len(new_events), "checks": len(results), "alerts": alerts, **findings}
    db.flush()
    reevaluate_dependents(db, row)


def record_results(db: Session, row: Connector, run_id: int, results: dict[str, Outcome]) -> dict[str, int]:
    """Store check results and reconcile their findings; SLA-driven checks take their status from the findings."""
    from govern.catalog.loader import sla_graded
    from govern.engine import findings as fnd
    from govern.settings_store import get as get_setting
    sla = get_setting(db, "sla")
    checks = load_checks()
    totals = {"new_findings": 0, "resolved_findings": 0}
    for check_id, outcome in results.items():
        synced = fnd.sync(db, row.id, checks[check_id], outcome)
        totals["new_findings"] += synced.new + synced.reopened
        totals["resolved_findings"] += synced.resolved
        status = outcome.status
        if check_id in sla_graded() and status in fnd.GRADED:
            status = fnd.sla_graded_status(db, row.id, check_id, sla)
        db.add(CheckResult(run_id=run_id, connector_id=row.id, check_id=check_id, status=status,
                           details={"params": outcome.params, "items": outcome.items[:MAX_ITEMS],
                                    "item_count": len(outcome.items)}))
    return totals


def latest_facts(db: Session, connector_id: int) -> dict:
    """Each fact as of the most recent run that collected it."""
    rows = db.execute(
        select(Snapshot.key, Snapshot.data).join(CollectionRun, Snapshot.run_id == CollectionRun.id)
        .where(CollectionRun.connector_id == connector_id).order_by(CollectionRun.id.desc()))
    out: dict = {}
    for key, data in rows:
        out.setdefault(key, data)
    return out


def cross_facts(db: Session, row: Connector) -> dict[str, dict | None]:
    """Latest facts of every other source kind this connector's checks read from."""
    kinds = {k for ch in load_checks().values() if ch.kind == row.kind for k in ch.cross}
    out: dict[str, dict | None] = {}
    for kind in kinds:
        other = db.scalar(select(Connector).where(Connector.kind == kind, Connector.enabled.is_(True))
                          .order_by(Connector.id).limit(1))
        out[kind] = latest_facts(db, other.id) if other else None
    return out


def reevaluate_dependents(db: Session, row: Connector) -> None:
    """Fresh data from this source changes the verdict of other sources' cross checks (e.g. Entra → GitLab leavers)."""
    dependent = {ch.id for ch in load_checks().values() if row.kind in ch.cross and ch.kind != row.kind}
    if not dependent:
        return
    kinds = {load_checks()[cid].kind for cid in dependent}
    for other in db.scalars(select(Connector).where(Connector.kind.in_(kinds), Connector.enabled.is_(True))):
        last_run = db.scalar(select(CollectionRun.id).where(CollectionRun.connector_id == other.id,
                                                            CollectionRun.status != "error")
                             .order_by(CollectionRun.id.desc()).limit(1))
        if last_run is None:
            continue
        results = evaluate_checks(other, latest_facts(db, other.id), {}, {}, cross_facts(db, other), only=dependent)
        record_results(db, other, last_run, results)
    db.flush()


def _previous_fact(db: Session, connector_id: int, key: str):
    found = db.execute(
        select(Snapshot.data).join(CollectionRun, Snapshot.run_id == CollectionRun.id)
        .where(CollectionRun.connector_id == connector_id, Snapshot.key == key)
        .order_by(CollectionRun.id.desc()).limit(1)).first()
    return found[0] if found else None


def _insert_events(db: Session, row: Connector, c: Collected) -> list[Event]:
    if not c.events:
        return []
    seen: set[str] = set()
    ids = [e.external_id for e in c.events]
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        seen.update(db.scalars(select(Event.external_id).where(
            Event.connector_id == row.id, Event.external_id.in_(chunk))))
    fresh = []
    for e in c.events:
        if e.external_id in seen:
            continue
        seen.add(e.external_id)
        ev = Event(connector_id=row.id, kind=e.kind, external_id=e.external_id, occurred_at=e.occurred_at,
                   actor=e.actor[:200], action=e.action[:120], target=e.target[:300], data=e.data)
        db.add(ev)
        fresh.append(ev)
    db.flush()
    return fresh


def evaluate_checks(row: Connector, facts: dict, unavailable: dict, errors: dict,
                    cross: dict[str, dict | None] | None = None, only: set[str] | None = None) -> dict[str, Outcome]:
    out: dict[str, Outcome] = {}
    thresholds = (row.config or {}).get("thresholds") or {}
    cross = cross or {}
    for check in load_checks().values():
        if check.kind != row.kind or (only is not None and check.id not in only):
            continue
        missing = [k for k in check.requires if k not in facts]
        reasons = {k: unavailable.get(k) or errors.get(k) or "not collected" for k in missing}
        merged = dict(facts)
        for kind, keys in check.cross.items():
            other = cross.get(kind)
            for k in keys:
                if other is None:
                    reasons[k] = f"needs a {kind} data source"
                elif k not in other:
                    reasons[k] = f"not yet collected by the {kind} data source"
                else:
                    merged[k] = other[k]
        if reasons:
            status = "error" if any(k in errors for k in missing) else "not_available"
            out[check.id] = Outcome(status, {"missing": reasons})
            continue
        params = {**check.defaults, **(row.config or {}), **thresholds.get(check.id, {})}
        try:
            out[check.id] = check.fn(merged, params)
        except Exception as e:
            logger.exception(f"check {check.id} failed")
            out[check.id] = Outcome("error", {"error": f"{type(e).__name__}: {e}"})
    return out


def raise_alerts(db: Session, row: Connector, events: list[Event]) -> int:
    if not events:
        return 0
    tuning = (row.config or {}).get("rules") or {}
    raised = 0
    for r in load_rules().values():
        if r.kind != row.kind or tuning.get(r.id, {}).get("enabled") is False:
            continue
        ctx = RuleContext(db, row, {**r.defaults, **tuning.get(r.id, {})})
        try:
            drafts = list(r.fn(ctx, events))
        except Exception:
            logger.exception(f"rule {r.id} failed")
            continue
        for d in drafts:
            raised += _upsert_alert(db, row, d)
    return raised


def _upsert_alert(db: Session, row: Connector, d) -> int:
    existing = db.scalar(select(Alert).where(Alert.dedup_key == d.dedup_key))
    detail = {**d.detail, "title_zh": d.title_zh}
    if existing is None:
        alert = Alert(connector_id=row.id, rule_id=d.rule_id, severity=d.severity, title=d.title[:300],
                      actor=d.actor[:200], detail=detail, occurred_at=d.occurred_at, dedup_key=d.dedup_key)
        db.add(alert)
        db.flush()
        db.info.setdefault("new_alert_ids", []).append(alert.id)
        return 1
    # Same window, more activity: refresh the numbers, never downgrade, keep the triage state.
    existing.detail = detail
    existing.title = d.title[:300]
    existing.occurred_at = max(existing.occurred_at, d.occurred_at)
    if SEVERITY_RANK[d.severity] > SEVERITY_RANK[existing.severity]:
        existing.severity = d.severity
        if existing.status in ("resolved", "false_positive"):
            existing.status = "open"
    existing.updated_at = utcnow()
    return 0


def _prune(db: Session, connector_id: int) -> None:
    s = get_settings()
    keep = list(db.scalars(select(CollectionRun.id).where(CollectionRun.connector_id == connector_id)
                           .order_by(CollectionRun.id.desc()).limit(s.SNAPSHOT_RETENTION_PER_CONNECTOR)))
    if keep:
        old_runs = select(CollectionRun.id).where(CollectionRun.connector_id == connector_id,
                                                  CollectionRun.id < min(keep))
        # Check results stay (they're the history); only the bulky raw snapshots go.
        db.execute(delete(Snapshot).where(Snapshot.run_id.in_(old_runs)))
    db.execute(delete(Event).where(Event.connector_id == connector_id,
                                   Event.occurred_at < utcnow() - timedelta(days=s.EVENT_RETENTION_DAYS)))
