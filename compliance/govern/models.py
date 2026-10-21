"""ORM models.

Control catalogs and check-to-control mappings live in YAML (govern/catalog), not
here: they are versioned with the code. The database holds what changes at
runtime — collected data, results, evidence, decisions and who made them.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text,
    TypeDecorator, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from govern.db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always hands back aware UTC datetimes, even from SQLite (which drops the zone)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            raise ValueError("naive datetime; use an aware UTC datetime")
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


# ─── Platform users and its own audit trail ────────────────────────────────────

ROLES = ("admin", "auditor", "viewer")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditEntry(Base):
    """Who did what on this platform. Append-only; nothing in the API deletes rows."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_email: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[dict] = mapped_column(JsonType, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")


# ─── Connectors and what they collect ──────────────────────────────────────────

class Connector(Base):
    __tablename__ = "connectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # m365 | github | gitlab | archery
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JsonType, default=dict)  # non-secret settings
    secrets_enc: Mapped[str] = mapped_column(Text, default="")  # Fernet token over a JSON object
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_minutes: Mapped[int] = mapped_column(Integer, default=360)
    run_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    running_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="never")  # never|ok|partial|error
    last_error: Mapped[str] = mapped_column(Text, default="")
    cursor: Mapped[dict] = mapped_column(JsonType, default=dict)  # incremental event positions
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|partial|error
    stats: Mapped[dict] = mapped_column(JsonType, default=dict)
    # fact key -> why it couldn't be collected (missing licence, permission, API tier)
    unavailable: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class Snapshot(Base):
    """One collected fact (a list of devices, a policy set...) as of one run."""
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    data: Mapped[object] = mapped_column(JsonType)


class Event(Base):
    """An activity record pulled from a source's audit log."""
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("connector_id", "external_id"),
        Index("ix_events_conn_kind_time", "connector_id", "kind", "occurred_at"),
        Index("ix_events_actor_time", "connector_id", "actor", "occurred_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. github.audit, archery.query
    external_id: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    actor: Mapped[str] = mapped_column(String(200), default="")
    action: Mapped[str] = mapped_column(String(120), default="")
    target: Mapped[str] = mapped_column(String(300), default="")
    data: Mapped[dict] = mapped_column(JsonType, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CheckResult(Base):
    __tablename__ = "check_results"
    __table_args__ = (Index("ix_check_results_latest", "connector_id", "check_id", "evaluated_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id", ondelete="CASCADE"), index=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"))
    check_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))  # pass|partial|fail|not_available|error
    summary: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JsonType, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ─── Risk alerts raised from events ────────────────────────────────────────────

ALERT_STATUSES = ("open", "acknowledged", "resolved", "false_positive")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(10))  # low|medium|high|critical
    title: Mapped[str] = mapped_column(String(300))
    actor: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[dict] = mapped_column(JsonType, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    # Same rule + subject + window never alerts twice.
    dedup_key: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[list] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ─── Manual compliance work ────────────────────────────────────────────────────

class Evidence(Base):
    """A document or attestation an auditor attached to a control."""
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_control", "framework", "control_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    framework: Mapped[str] = mapped_column(String(20))
    control_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str] = mapped_column(String(300), default="")
    stored_name: Mapped[str] = mapped_column(String(80), default="")  # random name on disk
    content_type: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    uploader: Mapped[User] = relationship()


class ControlApplicability(Base):
    """A control marked not applicable to this organisation, with the reason."""
    __tablename__ = "control_applicability"
    __table_args__ = (UniqueConstraint("framework", "control_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    framework: Mapped[str] = mapped_column(String(20))
    control_id: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    set_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    set_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


EXCEPTION_STATUSES = ("pending", "approved", "rejected", "revoked")


class RiskException(Base):
    """A failing check the organisation has decided to accept for a while."""
    __tablename__ = "risk_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    check_id: Mapped[str] = mapped_column(String(80), index=True)
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    compensating_controls: Mapped[str] = mapped_column(Text, default="")
    expires_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ScoreHistory(Base):
    """Framework score after each evaluation, for trend lines."""
    __tablename__ = "score_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    framework: Mapped[str] = mapped_column(String(20), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    score: Mapped[float] = mapped_column()
    counts: Mapped[dict] = mapped_column(JsonType, default=dict)


# ─── Security posture: individual findings tracked over time ───────────────────

class Finding(Base):
    """One concrete problem (a leaver's account, a CVE on a device...) from first sighting to fix.

    A finding is resolved when its check runs again with data and no longer
    reports it. If the check can't run, open findings stay open: missing data
    is not a fix.
    """
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("connector_id", "check_id", "key"),
        Index("ix_findings_open", "check_id", "resolved_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id", ondelete="CASCADE"), index=True)
    check_id: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(300))
    label: Mapped[str] = mapped_column(String(500), default="")
    severity: Mapped[str] = mapped_column(String(10))
    exploited: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JsonType, default=dict)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Reappearing after a fix reopens the same row; counted so flapping is visible.
    reopened: Mapped[int] = mapped_column(Integer, default=0)


class AppSetting(Base):
    """Platform settings edited in the UI (report schedule, SLA days, Teams webhook)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JsonType, default=dict)
    secret_enc: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
