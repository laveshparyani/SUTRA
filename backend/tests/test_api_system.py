"""Operational surface: health, system status, bridge status/scheduler, the
SPA fallback and API error shapes."""

from pathlib import Path

import pytest

from api_helpers import create_camera

_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def test_health_is_public_and_describes_the_node(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "sutra" and body["status"] == "ok"
    assert body["role"] in ("full", "edge", "central")
    assert isinstance(body["ingest_workers"], int)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_system_status_lists_background_tasks(client, admin, viewer):
    client.cookies.clear()   # drop the media cookie login left in the shared jar
    assert client.get("/api/system").status_code == 401
    r = client.get("/api/system", headers=viewer)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == client.get("/api/health").json()["role"]
    if body["role"] in ("full", "edge"):
        assert "ingest_scheduler" in body and "analytics" in body
        assert body["edge_sync"] == {"enabled": False}      # tests never push upstream
    if body["role"] == "central":
        assert "retention" in body


def test_bridge_status_and_scheduler_shape(client, viewer):
    status = client.get("/api/bridge/status", headers=viewer).json()
    assert isinstance(status["workers"], (list, dict))
    sched = client.get("/api/bridge/scheduler", headers=viewer).json()
    assert status["scheduler"]["budget"] == sched["budget"]
    assert {"budget", "pinned", "boosted", "dwell_s"} <= set(sched)


def test_pin_is_reflected_in_scheduler_status(client, admin):
    cam = create_camera(client, admin, "apit-pin")
    assert client.post(f"/api/bridge/cameras/{cam['id']}/pin", headers=admin).json() == {"camera_id": cam["id"], "pinned": True}
    assert cam["id"] in client.get("/api/bridge/scheduler", headers=admin).json()["pinned"]
    assert client.post(f"/api/bridge/cameras/{cam['id']}/unpin", headers=admin).json()["pinned"] is False
    assert cam["id"] not in client.get("/api/bridge/scheduler", headers=admin).json()["pinned"]


def test_start_stop_validate_the_camera(client, admin):
    """A camera without a source cannot be pooled; stop is always safe.
    Nothing here has a routable source, so no ingest worker is spawned."""
    assert client.post("/api/bridge/cameras/999999/start", headers=admin).status_code == 404
    assert client.post("/api/bridge/cameras/999999/stop", headers=admin).status_code == 404
    cam = create_camera(client, admin, "apit-nosrc", source_url="")
    r = client.post(f"/api/bridge/cameras/{cam['id']}/start", headers=admin)
    assert r.status_code == 400
    r = client.post(f"/api/bridge/cameras/{cam['id']}/stop", headers=admin)
    assert r.status_code == 200 and r.json() == {"camera_id": cam["id"], "pooled": False}
    assert client.get(f"/api/atlas/cameras/{cam['id']}", headers=admin).json()["monitoring"] is False


def test_snapshot_needs_auth_and_reports_no_frame(client, admin):
    client.cookies.clear()
    assert client.get("/api/bridge/cameras/999999/snapshot").status_code == 401
    r = client.get("/api/bridge/cameras/999999/snapshot", headers=admin)
    assert r.status_code == 404   # unknown camera: nothing to snapshot


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


@pytest.mark.skipif(not _DIST.is_dir(), reason="frontend/dist not built")
def test_spa_fallback_serves_the_shell_for_client_routes(client):
    for path in ("/", "/trace", "/alerts", "/registry"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "text/html" in r.headers["content-type"]
        assert "<div id=\"root\"" in r.text or "<div id='root'" in r.text


def test_evidence_route_confined_to_images(client, admin):
    assert client.get("/data/frames/../.jwt_secret", headers=admin).status_code == 404
    assert client.get("/data/nothing/here.jpg", headers=admin).status_code == 404
