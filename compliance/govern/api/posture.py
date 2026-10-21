"""Security posture (findings-centric view) and the notification / SLA settings."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from govern.checks.base import load_all as load_checks
from govern.db import get_db
from govern.engine.metrics import check_findings, posture_summary, sla_metrics
from govern.models import User
from govern.notify import NotifyError, SECRET_KEY, post, validate_webhook, webhook, weekly_card
from govern.security.auth import audit, require_role
from govern.settings_store import get as get_setting, put as put_setting, put_secret

router = APIRouter()


@router.get("/posture")
def posture(days: int = 7, _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    return posture_summary(db, days=max(1, min(days, 90)))


@router.get("/posture/checks/{check_id}/findings")
def findings(check_id: str, resolved: bool = False, overdue: bool = False, offset: int = 0, limit: int = 200,
             _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    if check_id not in load_checks():
        raise HTTPException(404, "No such check")
    return check_findings(db, check_id, include_resolved=resolved, overdue_only=overdue,
                          offset=max(offset, 0), limit=max(1, min(limit, 1000)))


@router.get("/posture/sla")
def sla(days: int = 90, _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    return sla_metrics(db, days=max(7, min(days, 365)))


# ─── settings ─────────────────────────────────────────────────────────────────

class NotifyBody(BaseModel):
    enabled: bool | None = None
    weekday: int | None = None
    hour: int | None = None
    timezone: str | None = None
    base_url: str | None = None
    realtime_critical: bool | None = None
    teams_webhook: str | None = None  # empty or omitted keeps the stored one


def _notify_out(db: Session) -> dict:
    return {**get_setting(db, "report"), "webhook_set": bool(webhook(db)), "state": get_setting(db, "report_state")}


@router.get("/settings/notify")
def get_notify(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    return _notify_out(db)


@router.put("/settings/notify")
def put_notify(body: NotifyBody, request: Request, user: User = Depends(require_role("admin")),
               db: Session = Depends(get_db)) -> dict:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    changes = body.model_dump(exclude_none=True, exclude={"teams_webhook"})
    if "weekday" in changes and not 1 <= changes["weekday"] <= 7:
        raise HTTPException(422, "weekday is 1 (Monday) to 7 (Sunday)")
    if "hour" in changes and not 0 <= changes["hour"] <= 23:
        raise HTTPException(422, "hour is 0 to 23")
    if "timezone" in changes:
        try:
            ZoneInfo(changes["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, "Unknown time zone")
    if changes.get("base_url") and not changes["base_url"].startswith(("http://", "https://")):
        raise HTTPException(422, "base_url must start with http:// or https://")
    if body.teams_webhook:
        try:
            validate_webhook(body.teams_webhook)
        except ValueError as e:
            raise HTTPException(422, str(e))
        put_secret(db, SECRET_KEY, {"teams_webhook": body.teams_webhook})
    put_setting(db, "report", changes)
    audit(db, request, user, "settings.notify", "settings", "notify", fields=sorted(changes),
          webhook_changed=bool(body.teams_webhook))
    db.commit()
    return _notify_out(db)


@router.post("/settings/notify/test")
async def test_notify(request: Request, user: User = Depends(require_role("admin")),
                      db: Session = Depends(get_db)) -> dict:
    url = webhook(db)
    if not url:
        raise HTTPException(409, "Save a Teams webhook first")
    card = weekly_card(db, get_setting(db, "report").get("base_url", ""))
    try:
        await run_in_threadpool(post, url, card)
        ok, message = True, "Sent"
    except NotifyError as e:
        ok, message = False, str(e)
    audit(db, request, user, "settings.notify_test", "settings", "notify", ok=ok)
    db.commit()
    return {"ok": ok, "message": message}


class SlaBody(BaseModel):
    exploited: int
    critical: int
    high: int
    medium: int
    low: int


@router.get("/settings/sla")
def get_sla(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    return get_setting(db, "sla")


@router.put("/settings/sla")
def put_sla(body: SlaBody, request: Request, user: User = Depends(require_role("admin")),
            db: Session = Depends(get_db)) -> dict:
    values = body.model_dump()
    if any(not 1 <= v <= 365 for v in values.values()):
        raise HTTPException(422, "Each SLA is 1 to 365 days")
    put_setting(db, "sla", values)
    audit(db, request, user, "settings.sla", "settings", "sla", **values)
    db.commit()
    return get_setting(db, "sla")
