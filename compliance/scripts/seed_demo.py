"""Fill a development database with demo data. Never point this at production.

Runs the real connectors against the canned API responses from the test suite,
so every page has something realistic to show:

    GOVERN_DATABASE_URL=sqlite:///./govern.db ... python scripts/seed_demo.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from govern.connectors.archery import ArcheryConnector  # noqa: E402
from govern.connectors.github import GitHubConnector  # noqa: E402
from govern.connectors.gitlab import GitLabConnector  # noqa: E402
from govern.connectors.m365 import M365Connector  # noqa: E402
from govern.db import new_session  # noqa: E402
from govern.engine.collector import run_connector  # noqa: E402
from govern.main import init_database  # noqa: E402
from govern.models import Connector  # noqa: E402
from govern.security.crypto import encrypt_secrets  # noqa: E402
from tests import fixtures_security as sec  # noqa: E402
from tests import test_connectors as fx  # noqa: E402


def main() -> None:
    if "prod" in (sys.argv[1:] or [""])[0]:
        raise SystemExit("refusing")
    init_database()
    db = new_session()
    sources = [
        ("m365", "EVYD Microsoft 365", {"tenant_id": "tenant-1", "client_id": "app",
                                        "break_glass_accounts": ["breakglass@evyd.com"]}, {"client_secret": "demo"},
         lambda row: M365Connector(row.config, {"client_secret": "demo"}, row.cursor, sleep=lambda s: None,
                                   transport=fx.router({**fx.m365_routes(), **sec.m365_security_routes(),
                                                        "/v1.0/users": {"value": sec.ENTRA_USERS},
                                                        "/v1.0/organization": {"value": [{"displayName": "EVYD",
                                                            "verifiedDomains": [{"name": "evyd.com"}]}]}})[0])),
        ("github", "GitHub · acme", {"org": "acme"}, {"token": "demo"},
         lambda row: GitHubConnector(row.config, {"token": "demo"}, transport=fx.router(fx.github_routes())[0],
                                     sleep=lambda s: None)),
        ("gitlab", "GitLab · gitlab.evyd.com", {"base_url": "https://gitlab.evyd.com"},
         {"token": "demo", "log_ingest_token": "demo-ingest-token-0123456789"},
         lambda row: GitLabConnector(row.config, {"token": "demo"}, transport=fx.router(sec.gitlab_routes())[0],
                                     sleep=lambda s: None)),
        ("archery", "Archery · prod", {"host": "archery-db", "user": "govern_ro", "timezone": fx.time_zone()},
         {"password": "demo", "discovery_dsns": json.dumps([{"instance": "prod-his", "dsn": "mysql://ro@db/his"}])},
         lambda row: ArcheryConnector(row.config, {"password": "demo", "discovery_dsns": "[]"},
                                      connect=lambda: fx.FakeConn(fx.archery_tables()), scan=fx.scan_stub)),
    ]
    for kind, name, config, secrets, factory in sources:
        row = Connector(kind=kind, name=name, config=config, secrets_enc=encrypt_secrets(secrets), schedule_minutes=360)
        db.add(row)
        db.commit()
        from govern.engine import discovery
        discovery.connect = lambda dsn: (fx.FakeConn({}), "mysql")
        run = run_connector(db, row.id, factory)
        print(f"{name}: {run.status} {run.stats}")
    db.close()


if __name__ == "__main__":
    main()
