"""Alerts, the platform audit trail and the overview dashboard."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from govern.catalog.loader import frameworks
from govern.db import get_db
from govern.engine.evaluate import evaluate, summarise
from govern.models import ALERT_STATUSES, Alert, AuditEntry, Connector, ScoreHistory, User
from govern.rules.base import load_all as load_rules
from govern.security.auth import audit, require_role
from govern.timeutil import utcnow

router = APIRouter()
SEVERITY_ORDER = ("critical", "high", "medium", "low")


def alert_out(a: Alert, users: dict[int, User] | None = None, conn: Connector | None = None) -> dict:
    rule = load_rules().get(a.rule_id)
    detail = dict(a.detail or {})
    title_zh = detail.pop("title_zh", a.title)
    return {"id": a.id, "rule_id": a.rule_id, "rule": rule.title if rule else {"en": a.rule_id, "zh": a.rule_id},
            "connector_id": a.connector_id, "connector_name": conn.name if conn else None,
            "connector_kind": conn.kind if conn else None, "severity": a.severity,
            "title": {"en": a.title, "zh": title_zh}, "actor": a.actor, "detail": detail,
            "occurred_at": a.occurred_at.isoformat(), "status": a.status,
            "assignee": users[a.assignee_id].email if users and a.assignee_id in users else None,
            "assignee_id": a.assignee_id, "notes": a.notes, "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat()}


@router.get("/alerts")
def list_alerts(status_: list[str] = Query(default=[], alias="status"), severity: list[str] = Query(default=[]),
                connector_id: int | None = None, rule_id: str | None = None, q: str | None = None,
                days: int = 30, limit: int = 200, offset: int = 0,
                _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    cond = [Alert.occurred_at >= utcnow() - timedelta(days=max(1, min(days, 400)))]
    if status_:
        cond.append(Alert.status.in_(status_))
    if severity:
        cond.append(Alert.severity.in_(severity))
    if connector_id is not None:
        cond.append(Alert.connector_id == connector_id)
    if rule_id:
        cond.append(Alert.rule_id == rule_id)
    if q:
        like = f"%{q.strip()}%"
        cond.append(or_(Alert.title.ilike(like), Alert.actor.ilike(like)))
    total = db.scalar(select(func.count(Alert.id)).where(*cond)) or 0
    rows = db.scalars(select(Alert).where(*cond).order_by(Alert.occurred_at.desc())
                      .offset(max(offset, 0)).limit(min(limit, 500)))
    users = {u.id: u for u in db.scalars(select(User))}
    conns = {c.id: c for c in db.scalars(select(Connector))}
    return {"total": total, "items": [alert_out(a, users, conns.get(a.connector_id)) for a in rows]}


class AlertUpdate(BaseModel):
    status: str | None = None
    assignee_id: int | None = None
    note: str | None = None


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate, request: Request, user: User = Depends(require_role("auditor")),
                 db: Session = Depends(get_db)) -> dict:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such alert")
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes:
        if body.status not in ALERT_STATUSES:
            raise HTTPException(422, f"status must be one of {', '.join(ALERT_STATUSES)}")
        if body.status in ("resolved", "false_positive") and not (body.note or "").strip():
            raise HTTPException(422, "Closing an alert needs a note saying why")
        a.status = body.status
    if "assignee_id" in changes:
        if body.assignee_id is not None and db.get(User, body.assignee_id) is None:
            raise HTTPException(422, "Unknown assignee")
        a.assignee_id = body.assignee_id
    if (body.note or "").strip():
        a.notes = [*(a.notes or []), {"at": utcnow().isoformat(), "by": user.email, "text": body.note.strip()[:4000],
                                      "status": a.status}]
    a.updated_at = utcnow()
    audit(db, request, user, "alert.updated", "alert", a.id, fields=sorted(changes))
    db.commit()
    users = {u.id: u for u in db.scalars(select(User))}
    return alert_out(a, users, db.get(Connector, a.connector_id))


@router.get("/rules")
def list_rules(_: User = Depends(require_role("viewer"))) -> list[dict]:
    return [{"id": r.id, "kind": r.kind, "title": r.title, "description": r.description, "defaults": r.defaults}
            for r in load_rules().values()]


@router.get("/audit-log")
def audit_log(limit: int = 200, offset: int = 0, action: str | None = None,
              _: User = Depends(require_role("auditor")), db: Session = Depends(get_db)) -> dict:
    cond = [AuditEntry.action.like(f"{action}%")] if action else []
    total = db.scalar(select(func.count(AuditEntry.id)).where(*cond)) or 0
    rows = db.scalars(select(AuditEntry).where(*cond).order_by(AuditEntry.id.desc())
                      .offset(max(offset, 0)).limit(min(limit, 1000)))
    return {"total": total, "items": [{
        "id": e.id, "at": e.at.isoformat(), "user": e.user_email, "action": e.action, "target_type": e.target_type,
        "target_id": e.target_id, "detail": e.detail, "ip": e.ip} for e in rows]}


@router.get("/overview")
def overview(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    fws = []
    for fw in frameworks().values():
        history = list(db.scalars(select(ScoreHistory).where(ScoreHistory.framework == fw.id)
                                  .order_by(ScoreHistory.id.desc()).limit(30)))
        fws.append({"id": fw.id, "name": fw.name, **summarise(evaluate(db, fw.id)),
                    "trend": [{"at": h.at.isoformat(), "score": h.score} for h in reversed(history)]})
    open_alerts = dict(db.execute(select(Alert.severity, func.count(Alert.id))
                                  .where(Alert.status.in_(("open", "acknowledged"))).group_by(Alert.severity)).all())
    recent = db.scalars(select(Alert).where(Alert.status == "open").order_by(Alert.occurred_at.desc()).limit(8))
    conns = {c.id: c for c in db.scalars(select(Connector))}
    return {
        "frameworks": fws,
        "open_alerts": {s: open_alerts.get(s, 0) for s in SEVERITY_ORDER},
        "recent_alerts": [alert_out(a, None, conns.get(a.connector_id)) for a in recent],
        "connectors": [{"id": c.id, "kind": c.kind, "name": c.name, "enabled": c.enabled, "last_status": c.last_status,
                        "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
                        "running": c.running_since is not None} for c in conns.values()],
    }
