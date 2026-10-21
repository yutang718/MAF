"""Service settings, read from GOVERN_* environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOVERN_", env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./govern.db"

    # Fernet key that encrypts connector credentials at rest. Generate with
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # There is deliberately no default: without it the service refuses to start.
    MASTER_KEY: str = ""
    # Signs session tokens. Separate from MASTER_KEY so rotating one doesn't force the other.
    JWT_SECRET: str = ""
    SESSION_MINUTES: int = 8 * 60
    # Cookies are Secure unless explicitly running over plain http in local dev.
    COOKIE_SECURE: bool = True

    # Created on first start when the users table is empty.
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    EVIDENCE_DIR: Path = Path("./evidence")
    EVIDENCE_MAX_BYTES: int = 20 * 1024 * 1024

    # Run the collection scheduler inside the API process (dev convenience).
    # In production run `python -m govern.worker` as its own container instead.
    INLINE_WORKER: bool = False
    WORKER_TICK_SECONDS: int = 60

    SNAPSHOT_RETENTION_PER_CONNECTOR: int = 30
    EVENT_RETENTION_DAYS: int = 400  # ISO/HIPAA audits usually ask for a year of logs

    # MAF's own PII detector, used to confirm sensitive columns found by Archery data discovery.
    MAF_URL: str = "http://maf:8000"

    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
