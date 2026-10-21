from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from govern.checks.base import load_all as load_checks
from govern.connectors.base import validate_config
from govern.connectors.registry import CONNECTOR_TYPES
from govern.db import get_db
from govern.models import CollectionRun, Connector, User
from govern.rules.base import load_all as load_rules
from govern.security.auth import audit, require_role
from govern.security.crypto import decrypt_secrets, encrypt_secrets

router = APIRouter()
MIN_SCHEDULE_MINUTES = 15


def _coerce(cls, config: dict[str, Any]) -> dict[str, Any]:
    """Keep known non-secret fields, typed as the connector declares them."""
    out: dict[str, Any] = {}
    for f in cls.fields:
        if f.secret or f.name not in config:
            continue
        value = config[f.name]
        try:
            if f.type == "int":
                value = int(value)
            elif f.type == "bool":
                value = value if isinstance(value, bool) else str(value).lower() in ("true", "1", "yes", "on")
            elif f.type == "list":
                if isinstance(value, str):
                    value = [v.strip() for v in value.replace("\n", ",").split(",") if v.strip()]
                value = list(value)
            else:
                value = str(value).strip()
        except (TypeError, ValueError):
            raise HTTPException(422, f"{f.name} must be of type {f.type}")
        out[f.name] = value
    # Per-check thresholds and per-rule tuning ride along untyped.
    for extra in ("thresholds", "rules"):
        if isinstance(config.get(extra), dict):
            out[extra] = config[extra]
    return out


def connector_out(c: Connector) -> dict:
    cls = CONNECTOR_TYPES[c.kind]
    try:
        secret_names = sorted(decrypt_secrets(c.secrets_enc))
    except Exception:
        secret_names = []
    return {
        "id": c.id, "kind": c.kind, "name": c.name, "config": c.config, "enabled": c.enabled,
        "schedule_minutes": c.schedule_minutes, "run_requested": c.run_requested,
        "running": c.running_since is not None, "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
        "last_status": c.last_status, "last_error": c.last_error,
        # Never the values: only which secrets are set, so the form can say "unchanged".
        "secrets_set": [n for n in secret_names if any(f.name == n for f in cls.fields)],
    }


@router.get("/connector-types")
def connector_types(_: User = Depends(require_role("viewer"))) -> list[dict]:
    checks = load_checks()
    rules = load_rules()
    return [{
        "kind": kind, "title": cls.title, "permissions_help": cls.permissions_help,
        "fields": [{"name": f.name, "label": f.label, "type": f.type, "required": f.required, "default": f.default,
                    "help": f.help} for f in cls.fields],
        "checks": sorted(cid for cid, ch in checks.items() if ch.kind == kind),
        "rules": [{"id": r.id, "title": r.title, "description": r.description, "defaults": r.defaults}
                  for r in rules.values() if r.kind == kind],
    } for kind, cls in CONNECTOR_TYPES.items()]


@router.get("/connectors")
def list_connectors(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> list[dict]:
    return [connector_out(c) for c in db.scalars(select(Connector).order_by(Connector.kind, Connector.name))]


class ConnectorBody(BaseModel):
    kind: str | None = None
    name: str | None = None
    config: dict[str, Any] = {}
    secrets: dict[str, str] = {}
    enabled: bool | None = None
    schedule_minutes: int | None = None


def _schedule(minutes: int | None) -> int | None:
    if minutes is not None and minutes < MIN_SCHEDULE_MINUTES:
        raise HTTPException(422,
                            f"Schedule must be at least {MIN_SCHEDULE_MINUTES} minutes")
    return minutes


@router.post("/connectors", status_code=201)
def create_connector(body: ConnectorBody, request: Request, admin: User = Depends(require_role("admin")),
                     db: Session = Depends(get_db)) -> dict:
    cls = CONNECTOR_TYPES.get(body.kind or "")
    if cls is None:
        raise HTTPException(422, f"kind must be one of {', '.join(CONNECTOR_TYPES)}")
    if not (body.name or "").strip():
        raise HTTPException(422, "name is required")
    config = _coerce(cls, body.config)
    secrets = {k: v for k, v in body.secrets.items() if v and any(f.name == k and f.secret for f in cls.fields)}
    try:
        validate_config(cls, config, secrets)
    except ValueError as e:
        raise HTTPException(422, str(e))
    c = Connector(kind=cls.kind, name=body.name.strip(), config=config, secrets_enc=encrypt_secrets(secrets),
                  enabled=body.enabled if body.enabled is not None else True,
                  schedule_minutes=_schedule(body.schedule_minutes) or 360)
    db.add(c)
    db.flush()
    audit(db, request, admin, "connector.created", "connector", c.id, kind=c.kind, name=c.name,
          secrets=sorted(secrets))
    db.commit()
    return connector_out(c)


def _get(db: Session, connector_id: int) -> Connector:
    c = db.get(Connector, connector_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
    return c


@router.get("/connectors/{connector_id}")
def get_connector(connector_id: int, _: User = Depends(require_role("viewer")),
                  db: Session = Depends(get_db)) -> dict:
    c = _get(db, connector_id)
    runs = db.scalars(select(CollectionRun).where(CollectionRun.connector_id == c.id)
                      .order_by(CollectionRun.id.desc()).limit(20))
    return {**connector_out(c), "runs": [{
        "id": r.id, "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "status": r.status, "stats": r.stats, "unavailable": r.unavailable, "error": r.error} for r in runs]}


@router.patch("/connectors/{connector_id}")
def update_connector(connector_id: int, body: ConnectorBody, request: Request,
                     admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    c = _get(db, connector_id)
    cls = CONNECTOR_TYPES[c.kind]
    config = {**c.config, **_coerce(cls, body.config)} if body.config else c.config
    existing = decrypt_secrets(c.secrets_enc)
    # An empty value means "leave as is"; there is no way to read a secret back, only replace it.
    changed_secrets = {k: v for k, v in body.secrets.items() if v and any(f.name == k and f.secret for f in cls.fields)}
    try:
        validate_config(cls, config, changed_secrets, existing)
    except ValueError as e:
        raise HTTPException(422, str(e))
    c.config = config
    if changed_secrets:
        c.secrets_enc = encrypt_secrets({**existing, **changed_secrets})
    if body.name is not None and body.name.strip():
        c.name = body.name.strip()
    if body.enabled is not None:
        c.enabled = body.enabled
    if body.schedule_minutes is not None:
        c.schedule_minutes = _schedule(body.schedule_minutes)
    audit(db, request, admin, "connector.updated", "connector", c.id,
          fields=sorted(body.model_dump(exclude_unset=True, exclude={"secrets"})), secrets=sorted(changed_secrets))
    db.commit()
    return connector_out(c)


@router.delete("/connectors/{connector_id}", status_code=204)
def delete_connector(connector_id: int, request: Request, admin: User = Depends(require_role("admin")),
                     db: Session = Depends(get_db)) -> None:
    c = _get(db, connector_id)
    audit(db, request, admin, "connector.deleted", "connector", c.id, kind=c.kind, name=c.name)
    db.delete(c)
    db.commit()


@router.post("/connectors/{connector_id}/test")
async def test_connector(connector_id: int, request: Request, admin: User = Depends(require_role("admin")),
                         db: Session = Depends(get_db)) -> dict:
    c = _get(db, connector_id)
    source = CONNECTOR_TYPES[c.kind](c.config, decrypt_secrets(c.secrets_enc), c.cursor)
    try:
        message = await run_in_threadpool(source.test)
        ok = True
    except Exception as e:
        message, ok = f"{type(e).__name__}: {e}", False
    finally:
        source.close()
    audit(db, request, admin, "connector.tested", "connector", c.id, ok=ok)
    db.commit()
    return {"ok": ok, "message": message[:1000]}


@router.post("/connectors/{connector_id}/run", status_code=202)
def request_run(connector_id: int, request: Request, user: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)) -> dict:
    c = _get(db, connector_id)
    c.run_requested = True
    audit(db, request, user, "connector.run_requested", "connector", c.id)
    db.commit()
    return connector_out(c)
