import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("GOVERN_MASTER_KEY", Fernet.generate_key().decode())
os.environ.setdefault("GOVERN_JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ["GOVERN_COOKIE_SECURE"] = "false"
os.environ["GOVERN_BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["GOVERN_BOOTSTRAP_ADMIN_PASSWORD"] = "correct-horse-battery"


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'govern.db'}"
    monkeypatch.setenv("GOVERN_DATABASE_URL", url)
    monkeypatch.setenv("GOVERN_EVIDENCE_DIR", str(tmp_path / "evidence"))
    from govern.config import get_settings
    from govern.db import reset_engine
    get_settings.cache_clear()
    reset_engine()
    yield url
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def db(db_url):
    from govern.main import init_database
    from govern.db import new_session
    init_database()
    session = new_session()
    yield session
    session.close()


@pytest.fixture
def client(db_url):
    from fastapi.testclient import TestClient
    from govern.main import app
    with TestClient(app) as c:
        yield c


def login(client, email="admin@example.com", password="correct-horse-battery"):
    r = client.post("/api/v1/governance/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


@pytest.fixture
def admin(client):
    login(client)
    return client
