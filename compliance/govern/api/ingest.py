"""Machine endpoint for log shippers: POST GitLab JSON log lines, get download events and alerts."""
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from govern.connectors.base import Collected
from govern.db import get_db
from govern.engine.collector import _insert_events, notify_new_alerts, raise_alerts
from govern.ingest import gitlab_logs
from govern.models import Connector
from govern.security.crypto import decrypt_secrets

router = APIRouter()
MAX_BODY = 10 * 1024 * 1024


@router.post("/ingest/gitlab/{connector_id}")
async def ingest_gitlab(connector_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    row = db.get(Connector, connector_id)
    expected = decrypt_secrets(row.secrets_enc).get("log_ingest_token", "") if row and row.kind == "gitlab" else ""
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    # Same answer for an unknown connector and a wrong token.
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingestion token")
    if not row.enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connector is disabled")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Send at most 10 MB per request")
    return await run_in_threadpool(_process, db, row, _lines(body))


def _process(db: Session, row: Connector, lines: list) -> dict:
    events = [ev for ev in (gitlab_logs.parse(x) for x in lines) if ev is not None]
    fresh = _insert_events(db, row, Collected(events=events))
    alerts = raise_alerts(db, row, fresh)
    db.commit()
    notify_new_alerts(db)
    return {"lines": len(lines), "downloads": len(events), "new": len(fresh), "alerts": alerts}


def _lines(body: bytes) -> list:
    text = body.decode("utf-8", errors="replace").strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except ValueError:
            pass
    return [line for line in text.splitlines() if line.strip()]
