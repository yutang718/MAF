"""Frameworks, controls, check results, evidence, applicability and risk exceptions."""
import csv
import hashlib
import io
import secrets
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from govern.catalog.loader import frameworks, mappings
from govern.checks.base import load_all as load_checks
from govern.config import get_settings
from govern.db import get_db
from govern.engine.evaluate import ControlState, evaluate, summarise
from govern.models import (
    CheckResult, Connector, ControlApplicability, Evidence, RiskException, ScoreHistory, User,
)
from govern.security.auth import audit, require_role
from govern.timeutil import utcnow

router = APIRouter()


def _framework(fw_id: str):
    fw = frameworks().get(fw_id)
    if fw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such framework")
    return fw


def _control(fw, control_id: str):
    control = fw.controls.get(control_id)
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such control")
    return control


def check_meta(check_id: str) -> dict:
    ch = load_checks().get(check_id)
    if ch is None:
        return {"id": check_id, "title": {"en": check_id, "zh": check_id}}
    return {"id": ch.id, "kind": ch.kind, "title": ch.title, "severity": ch.severity, "remediation": ch.remediation}


def result_out(r: CheckResult, conn: Connector | None = None, status_override: str | None = None,
               items: bool = False) -> dict:
    ch = load_checks().get(r.check_id)
    params = (r.details or {}).get("params", {})
    out = {
        "id": r.id, "check": check_meta(r.check_id), "connector_id": r.connector_id,
        "connector_name": conn.name if conn else None, "status": status_override or r.status, "raw_status": r.status,
        "evaluated_at": r.evaluated_at.isoformat(), "params": params,
        "summary": {lang: ch.render_summary(lang, params) for lang in ("en", "zh")} if ch and r.status not in (
            "not_available", "error") else None,
        "item_count": len((r.details or {}).get("items", [])),
    }
    if items:
        out["items"] = (r.details or {}).get("items", [])
    return out


@router.get("/frameworks")
def list_frameworks(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": fw.id, "name": fw.name, "description": fw.description, **summarise(evaluate(db, fw.id))}
            for fw in frameworks().values()]


def _state_out(fw, st: ControlState) -> dict:
    c = fw.controls[st.control_id]
    return {"id": c.id, "group": c.group, "title": c.title, "status": st.status,
            "mapped_checks": len(st.mapped_checks),
            "check_counts": _count(s.status for s in st.checks),
            "evidence_current": st.evidence_current, "evidence_expired": st.evidence_expired,
            "not_applicable_reason": st.not_applicable_reason}


def _count(values) -> dict:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


@router.get("/frameworks/{fw_id}")
def get_framework(fw_id: str, _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    fw = _framework(fw_id)
    states = evaluate(db, fw_id)
    return {"id": fw.id, "name": fw.name, "description": fw.description,
            "groups": [{"id": gid, "name": name} for gid, name in fw.groups.items()],
            "summary": summarise(states), "controls": [_state_out(fw, st) for st in states]}


@router.get("/frameworks/{fw_id}/history")
def framework_history(fw_id: str, limit: int = 90, _: User = Depends(require_role("viewer")),
                      db: Session = Depends(get_db)) -> list[dict]:
    _framework(fw_id)
    rows = list(db.scalars(select(ScoreHistory).where(ScoreHistory.framework == fw_id)
                           .order_by(ScoreHistory.id.desc()).limit(min(limit, 1000))))
    return [{"at": r.at.isoformat(), "score": r.score, "counts": r.counts} for r in reversed(rows)]


@router.get("/frameworks/{fw_id}/controls/{control_id}")
def get_control(fw_id: str, control_id: str, _: User = Depends(require_role("viewer")),
                db: Session = Depends(get_db)) -> dict:
    fw = _framework(fw_id)
    _control(fw, control_id)
    st = next(s for s in evaluate(db, fw_id) if s.control_id == control_id)
    results = {r.id: r for r in db.scalars(select(CheckResult).where(CheckResult.id.in_([s.result_id for s in st.checks])))}
    conns = {c.id: c for c in db.scalars(select(Connector))}
    evidence = db.scalars(select(Evidence).where(Evidence.framework == fw_id, Evidence.control_id == control_id)
                          .order_by(Evidence.created_at.desc()))
    covered = {s.check_id for s in st.checks}
    return {
        **_state_out(fw, st),
        "group_name": fw.groups[fw.controls[control_id].group],
        "results": [result_out(results[s.result_id], conns.get(s.connector_id), s.status, items=True)
                    for s in st.checks],
        # Mapped checks with no result anywhere: their connector isn't set up yet.
        "uncovered_checks": [check_meta(cid) for cid in st.mapped_checks if cid not in covered],
        "evidence": [evidence_out(e) for e in evidence],
        "related": {other: list(ids) for other, ids in _related(fw_id, st.mapped_checks).items()},
    }


def _related(fw_id: str, check_ids) -> dict[str, set]:
    """Controls in other frameworks that the same checks provide evidence for."""
    out: dict[str, set] = {}
    m = mappings()
    for cid in check_ids:
        for other, controls in m.get(cid, {}).items():
            if other != fw_id:
                out.setdefault(other, set()).update(controls)
    return {k: sorted(v) for k, v in out.items()}


@router.get("/frameworks/{fw_id}/report.csv")
def framework_report(fw_id: str, request: Request, lang: str = "en", user: User = Depends(require_role("auditor")),
                     db: Session = Depends(get_db)) -> StreamingResponse:
    fw = _framework(fw_id)
    lang = "zh" if lang == "zh" else "en"
    states = evaluate(db, fw_id)
    buf = io.StringIO()
    buf.write("﻿")  # so Excel opens UTF-8 Chinese correctly
    w = csv.writer(buf)
    w.writerow(["control", "group", "title", "status", "automated_checks", "failing_checks", "evidence_current",
                "evidence_expired", "not_applicable_reason"])
    for st in states:
        c = fw.controls[st.control_id]
        w.writerow([c.id, fw.groups[c.group][lang], c.title[lang], st.status, len(st.checks),
                    sum(1 for s in st.checks if s.status in ("fail", "partial")), st.evidence_current,
                    st.evidence_expired, st.not_applicable_reason or ""])
    audit(db, request, user, "report.exported", "framework", fw_id)
    db.commit()
    buf.seek(0)
    name = f"{fw_id}-{date.today().isoformat()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ─── applicability ────────────────────────────────────────────────────────────

class ApplicabilityBody(BaseModel):
    reason: str


@router.put("/frameworks/{fw_id}/controls/{control_id}/applicability")
def mark_not_applicable(fw_id: str, control_id: str, body: ApplicabilityBody, request: Request,
                        user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    _control(_framework(fw_id), control_id)
    if len(body.reason.strip()) < 10:
        raise HTTPException(422, "Explain why, in at least 10 characters")
    row = db.scalar(select(ControlApplicability).where(ControlApplicability.framework == fw_id,
                                                       ControlApplicability.control_id == control_id))
    if row is None:
        row = ControlApplicability(framework=fw_id, control_id=control_id, reason=body.reason.strip(), set_by=user.id)
        db.add(row)
    else:
        row.reason, row.set_by, row.set_at = body.reason.strip(), user.id, utcnow()
    audit(db, request, user, "control.not_applicable", "control", f"{fw_id}:{control_id}", reason=body.reason.strip())
    db.commit()
    return {"ok": True}


@router.delete("/frameworks/{fw_id}/controls/{control_id}/applicability", status_code=204)
def mark_applicable(fw_id: str, control_id: str, request: Request, user: User = Depends(require_role("admin")),
                    db: Session = Depends(get_db)) -> None:
    row = db.scalar(select(ControlApplicability).where(ControlApplicability.framework == fw_id,
                                                       ControlApplicability.control_id == control_id))
    if row:
        db.delete(row)
        audit(db, request, user, "control.applicable", "control", f"{fw_id}:{control_id}")
        db.commit()


# ─── evidence ─────────────────────────────────────────────────────────────────

ALLOWED_EVIDENCE_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "text/plain", "text/csv", "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/msword", "application/vnd.ms-excel", "application/zip",
}


def evidence_out(e: Evidence) -> dict:
    return {"id": e.id, "framework": e.framework, "control_id": e.control_id, "title": e.title,
            "description": e.description, "file_name": e.file_name, "size": e.size, "sha256": e.sha256,
            "valid_until": e.valid_until.isoformat() if e.valid_until else None,
            "expired": bool(e.valid_until and e.valid_until < date.today()),
            "uploaded_by": e.uploader.email if e.uploader else None, "created_at": e.created_at.isoformat()}


@router.post("/evidence", status_code=201)
async def upload_evidence(request: Request, framework: str = Form(...), control_id: str = Form(...),
                          title: str = Form(...), description: str = Form(""), valid_until: str = Form(""),
                          file: UploadFile | None = File(None), user: User = Depends(require_role("auditor")),
                          db: Session = Depends(get_db)) -> dict:
    _control(_framework(framework), control_id)
    if not title.strip():
        raise HTTPException(422, "title is required")
    until = None
    if valid_until:
        try:
            until = date.fromisoformat(valid_until)
        except ValueError:
            raise HTTPException(422, "valid_until must be YYYY-MM-DD")
    e = Evidence(framework=framework, control_id=control_id, title=title.strip(), description=description.strip(),
                 valid_until=until, uploaded_by=user.id)
    if file is not None and file.filename:
        s = get_settings()
        content_type = (file.content_type or "").split(";")[0]
        if content_type not in ALLOWED_EVIDENCE_TYPES:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"File type {content_type or '?'} isn't accepted")
        data = await file.read(s.EVIDENCE_MAX_BYTES + 1)
        if len(data) > s.EVIDENCE_MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"Files are limited to {s.EVIDENCE_MAX_BYTES // (1024 * 1024)} MB")
        s.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        stored = secrets.token_hex(16)
        (s.EVIDENCE_DIR / stored).write_bytes(data)
        e.file_name = file.filename[:300]
        e.stored_name = stored
        e.content_type = content_type
        e.size = len(data)
        e.sha256 = hashlib.sha256(data).hexdigest()
    db.add(e)
    db.flush()
    audit(db, request, user, "evidence.uploaded", "evidence", e.id, control=f"{framework}:{control_id}",
          file=e.file_name, sha256=e.sha256)
    db.commit()
    db.refresh(e)
    return evidence_out(e)


@router.get("/evidence/{evidence_id}/file")
def download_evidence(evidence_id: int, request: Request, user: User = Depends(require_role("auditor")),
                      db: Session = Depends(get_db)) -> FileResponse:
    e = db.get(Evidence, evidence_id)
    if e is None or not e.stored_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file for this evidence")
    path = get_settings().EVIDENCE_DIR / e.stored_name
    if not path.is_file():
        raise HTTPException(status.HTTP_410_GONE, "The stored file is missing")
    audit(db, request, user, "evidence.downloaded", "evidence", e.id)
    db.commit()
    return FileResponse(path, media_type=e.content_type or "application/octet-stream", filename=e.file_name,
                        headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, request: Request, user: User = Depends(require_role("admin")),
                    db: Session = Depends(get_db)) -> None:
    e = db.get(Evidence, evidence_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such evidence")
    audit(db, request, user, "evidence.deleted", "evidence", e.id, title=e.title, sha256=e.sha256,
          control=f"{e.framework}:{e.control_id}")
    if e.stored_name:
        (get_settings().EVIDENCE_DIR / e.stored_name).unlink(missing_ok=True)
    db.delete(e)
    db.commit()


# ─── checks and their results ─────────────────────────────────────────────────

@router.get("/checks")
def list_checks(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> list[dict]:
    from govern.engine.evaluate import active_exceptions, latest_results
    m = mappings()
    exceptions = active_exceptions(db)
    latest: dict[str, list[dict]] = {}
    for r, conn in latest_results(db):
        accepted = r.status in ("fail", "partial") and any(
            x.check_id == r.check_id and x.connector_id in (None, conn.id) for x in exceptions)
        latest.setdefault(r.check_id, []).append(result_out(r, conn, "accepted" if accepted else None))
    return [{**check_meta(ch.id), "summary_template": ch.summary, "defaults": ch.defaults,
             "mappings": m.get(ch.id, {}), "results": latest.get(ch.id, [])} for ch in load_checks().values()]


@router.get("/check-results/{result_id}")
def get_result(result_id: int, _: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> dict:
    r = db.get(CheckResult, result_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such result")
    history = db.scalars(select(CheckResult).where(CheckResult.connector_id == r.connector_id,
                                                   CheckResult.check_id == r.check_id)
                         .order_by(CheckResult.id.desc()).limit(30))
    return {**result_out(r, db.get(Connector, r.connector_id), items=True),
            "history": [{"id": h.id, "status": h.status, "evaluated_at": h.evaluated_at.isoformat()} for h in history]}


# ─── risk exceptions ──────────────────────────────────────────────────────────

class ExceptionBody(BaseModel):
    check_id: str
    connector_id: int | None = None
    reason: str
    compensating_controls: str = ""
    expires_on: date


class DecisionBody(BaseModel):
    approve: bool


MAX_EXCEPTION_DAYS = 365


def exception_out(x: RiskException, users: dict[int, User]) -> dict:
    return {"id": x.id, "check": check_meta(x.check_id), "connector_id": x.connector_id, "reason": x.reason,
            "compensating_controls": x.compensating_controls, "expires_on": x.expires_on.isoformat(),
            "expired": x.expires_on < date.today(), "status": x.status,
            "requested_by": users[x.requested_by].email if x.requested_by in users else None,
            "decided_by": users[x.decided_by].email if x.decided_by in users else None,
            "decided_at": x.decided_at.isoformat() if x.decided_at else None, "created_at": x.created_at.isoformat()}


@router.get("/exceptions")
def list_exceptions(_: User = Depends(require_role("viewer")), db: Session = Depends(get_db)) -> list[dict]:
    users = {u.id: u for u in db.scalars(select(User))}
    return [exception_out(x, users) for x in db.scalars(select(RiskException).order_by(RiskException.id.desc()))]


@router.post("/exceptions", status_code=201)
def request_exception(body: ExceptionBody, request: Request, user: User = Depends(require_role("auditor")),
                      db: Session = Depends(get_db)) -> dict:
    if body.check_id not in load_checks():
        raise HTTPException(422, "Unknown check")
    if body.connector_id is not None and db.get(Connector, body.connector_id) is None:
        raise HTTPException(422, "Unknown connector")
    days = (body.expires_on - date.today()).days
    if days <= 0 or days > MAX_EXCEPTION_DAYS:
        raise HTTPException(422,
                            f"An exception must expire within {MAX_EXCEPTION_DAYS} days from today")
    if len(body.reason.strip()) < 20:
        raise HTTPException(422, "Explain the business reason in at least 20 characters")
    x = RiskException(check_id=body.check_id, connector_id=body.connector_id, reason=body.reason.strip(),
                      compensating_controls=body.compensating_controls.strip(), expires_on=body.expires_on,
                      requested_by=user.id)
    db.add(x)
    db.flush()
    audit(db, request, user, "exception.requested", "exception", x.id, check=x.check_id)
    db.commit()
    return exception_out(x, {user.id: user})


@router.post("/exceptions/{exception_id}/decision")
def decide_exception(exception_id: int, body: DecisionBody, request: Request,
                     user: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    x = db.get(RiskException, exception_id)
    if x is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such exception")
    if x.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already {x.status}")
    if x.requested_by == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Someone other than the requester must decide")
    x.status = "approved" if body.approve else "rejected"
    x.decided_by, x.decided_at = user.id, utcnow()
    audit(db, request, user, f"exception.{x.status}", "exception", x.id, check=x.check_id)
    db.commit()
    users = {u.id: u for u in db.scalars(select(User))}
    return exception_out(x, users)


@router.post("/exceptions/{exception_id}/revoke")
def revoke_exception(exception_id: int, request: Request, user: User = Depends(require_role("admin")),
                     db: Session = Depends(get_db)) -> dict:
    x = db.get(RiskException, exception_id)
    if x is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such exception")
    if x.status not in ("approved", "pending"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already {x.status}")
    x.status = "revoked"
    audit(db, request, user, "exception.revoked", "exception", x.id, check=x.check_id)
    db.commit()
    users = {u.id: u for u in db.scalars(select(User))}
    return exception_out(x, users)
