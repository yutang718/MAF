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
from tests import test_connectors as fx  # noqa: E402


def main() -> None:
    if "prod" in (sys.argv[1:] or [""])[0]:
        raise SystemExit("refusing")
    init_database()
    db = new_session()
    gitlab_routes = {
        "/api/v4/groups/acme": {"full_path": "acme", "require_two_factor_authentication": True, "two_factor_grace_period": 48},
        "/api/v4/groups/acme/members/all": [{"username": "o1", "access_level": 50}, {"username": "o2", "access_level": 50},
                                            {"username": "d1", "access_level": 30}],
        "/api/v4/groups/acme/projects": [{"id": 7, "path_with_namespace": "acme/api", "visibility": "internal",
                                          "default_branch": "main"}],
        "/api/v4/projects/7/protected_branches/main": {"push_access_levels": [{"access_level": 0}], "allow_force_push": False},
        "/api/v4/projects/7/approval_rules": [{"approvals_required": 1}],
        "/api/v4/projects/7/deploy_keys": [],
        "/api/v4/groups/acme/access_tokens": [{"name": "ci", "active": True, "expires_at": None, "scopes": ["api"]}],
        "/api/v4/groups/acme/audit_events": [{"id": 1, "created_at": fx.RECENT, "entity_type": "Project",
                                              "details": {"author_name": "o1", "change": "visibility", "from": "Private",
                                                          "to": "Public", "entity_path": "acme/api"}}],
    }
    sources = [
        ("m365", "EVYD Microsoft 365", {"tenant_id": "tenant-1", "client_id": "app"}, {"client_secret": "demo"},
         lambda row: M365Connector(row.config, {"client_secret": "demo"}, transport=fx.router(fx.m365_routes())[0],
                                   sleep=lambda s: None)),
        ("github", "GitHub · acme", {"org": "acme"}, {"token": "demo"},
         lambda row: GitHubConnector(row.config, {"token": "demo"}, transport=fx.router(fx.github_routes())[0],
                                     sleep=lambda s: None)),
        ("gitlab", "GitLab · acme", {"group": "acme"}, {"token": "demo"},
         lambda row: GitLabConnector(row.config, {"token": "demo"}, transport=fx.router(gitlab_routes)[0],
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
