"""Settings edited in the UI, with defaults. Secrets (the Teams webhook) are encrypted like connector credentials."""
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from govern.engine.findings import DEFAULT_SLA_DAYS
from govern.models import AppSetting
from govern.security.crypto import decrypt_secrets, encrypt_secrets
from govern.timeutil import utcnow

DEFAULTS: dict[str, dict[str, Any]] = {
    "sla": dict(DEFAULT_SLA_DAYS),
    "report": {
        "enabled": False,
        "weekday": 1,  # ISO weekday, 1 = Monday
        "hour": 9,
        "timezone": "Asia/Brunei",
        "base_url": "",  # link target in Teams messages, e.g. https://maf.internal
        "realtime_critical": True,  # post each new critical alert as it's raised
    },
    "report_state": {"last_sent_at": None, "last_error": ""},
}


def get(db: Session, key: str) -> dict[str, Any]:
    row = db.get(AppSetting, key)
    value = deepcopy(DEFAULTS.get(key, {}))
    if row is not None:
        value.update(row.value or {})
    return value


def put(db: Session, key: str, value: dict[str, Any]) -> dict[str, Any]:
    row = db.get(AppSetting, key)
    merged = {**get(db, key), **value}
    if row is None:
        db.add(AppSetting(key=key, value=merged))
    else:
        row.value, row.updated_at = merged, utcnow()
    return merged


def get_secret(db: Session, key: str) -> dict[str, str]:
    row = db.get(AppSetting, key)
    return decrypt_secrets(row.secret_enc) if row else {}


def put_secret(db: Session, key: str, secrets: dict[str, str]) -> None:
    row = db.get(AppSetting, key)
    current = get_secret(db, key)
    merged = {k: v for k, v in {**current, **secrets}.items() if v}
    if row is None:
        db.add(AppSetting(key=key, value=deepcopy(DEFAULTS.get(key, {})), secret_enc=encrypt_secrets(merged)))
    else:
        row.secret_enc, row.updated_at = encrypt_secrets(merged), utcnow()
