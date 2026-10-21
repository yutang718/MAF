"""Security governance API: uvicorn govern.main:app"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from govern.api import auth, compliance, connectors, ingest, monitoring
from govern.api import posture as posture_api
from govern.catalog.loader import frameworks, mappings, posture
from govern.checks.base import load_all as load_checks
from govern.config import get_settings
from govern.db import Base, get_engine, session_scope
from govern.log import get_logger
from govern.rules.base import load_all as load_rules
from govern.security.crypto import MasterKeyError, _fernet

logger = get_logger("govern")
API = "/api/v1/governance"


def init_database() -> None:
    """Fail fast on missing secrets; create tables on SQLite (Postgres goes through Alembic)."""
    s = get_settings()
    _fernet()  # raises MasterKeyError if GOVERN_MASTER_KEY is missing or malformed
    if not s.JWT_SECRET or len(s.JWT_SECRET) < 32:
        raise RuntimeError("GOVERN_JWT_SECRET must be set to at least 32 random characters")
    # Load and cross-validate catalogs, checks and mappings now rather than on first request.
    frameworks()
    checks, rules = load_checks(), load_rules()
    unknown = set(mappings()) - set(checks)
    if unknown:
        raise RuntimeError(f"mappings.yaml names unknown checks: {sorted(unknown)}")
    for d in posture():
        for it in d.items:
            if (it.check and it.check not in checks) or (it.rule and it.rule not in rules):
                raise RuntimeError(f"posture.yaml {it.code} names an unknown check or rule")
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    with session_scope() as db:
        auth.ensure_bootstrap_admin(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    stop = None
    if get_settings().INLINE_WORKER:
        from govern.worker import start_background
        stop = start_background()
    yield
    if stop:
        stop.set()


app = FastAPI(title="EVYD Security Governance", version="0.1.0", lifespan=lifespan,
              openapi_url=f"{API}/openapi.json", docs_url=f"{API}/docs", redoc_url=None)

for module in (auth, connectors, compliance, monitoring, ingest, posture_api):
    app.include_router(module.router, prefix=API)


@app.exception_handler(MasterKeyError)
async def master_key_error(_: Request, exc: MasterKeyError):
    return JSONResponse({"detail": str(exc)}, status_code=500)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get(f"{API}/health")
def health() -> dict:
    return {"status": "ok", "frameworks": len(frameworks()), "checks": len(load_checks()), "rules": len(load_rules())}
