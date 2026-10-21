"""Collection scheduler. Run as its own process: python -m govern.worker

Every tick it runs connectors that are due (or that someone asked to run now).
Several workers can share a database: claiming a connector is atomic.
"""
import signal
import threading
from datetime import timedelta

from sqlalchemy import select

from govern.config import get_settings
from govern.db import new_session
from govern.engine.collector import run_connector
from govern.log import get_logger
from govern.models import Connector
from govern.timeutil import utcnow

logger = get_logger("govern.worker")


def due_connectors() -> list[int]:
    now = utcnow()
    with new_session() as db:
        due = []
        for c in db.scalars(select(Connector).where(Connector.enabled.is_(True), Connector.running_since.is_(None))):
            if c.run_requested or c.last_run_at is None or c.last_run_at + timedelta(minutes=c.schedule_minutes) <= now:
                due.append(c.id)
        return due


def tick() -> None:
    from govern.notify import send_weekly_if_due
    with new_session() as db:
        try:
            if send_weekly_if_due(db):
                logger.info("weekly security report sent to Teams")
        except Exception:
            logger.exception("weekly report check failed")
    for connector_id in due_connectors():
        with new_session() as db:
            try:
                run = run_connector(db, connector_id)
                if run:
                    logger.info(f"connector {connector_id}: {run.status} {run.stats}")
            except Exception:
                logger.exception(f"connector {connector_id} run crashed")


def loop(stop: threading.Event) -> None:
    interval = get_settings().WORKER_TICK_SECONDS
    logger.info(f"worker started, tick every {interval}s")
    while not stop.is_set():
        try:
            tick()
        except Exception:
            logger.exception("worker tick failed")
        stop.wait(interval)


def start_background() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), name="govern-worker", daemon=True).start()
    return stop


def main() -> None:
    from govern.main import init_database
    init_database()
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    loop(stop)


if __name__ == "__main__":
    main()
