"""Test fixtures: isolated temp database, analytics sidecars disabled."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.mkdtemp(prefix="sutra_test_")
os.environ["SUTRA_DATA_DIR"] = _tmp
os.environ["SUTRA_DB_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SUTRA_INSIGHT_ENABLED"] = "false"
os.environ["SUTRA_SCENE_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "SutraAdmin@26"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def viewer(client):
    r = client.post("/api/auth/login", json={"username": "viewer", "password": "Viewer@26"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}
