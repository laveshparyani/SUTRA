"""Edge -> central sync channel contract.

The main test app runs as `full`, where the router is deliberately not
mounted (test_security pins that). The router is exercised here on a
throwaway FastAPI app sharing the same database, with the shared key set
per test — the auth rule, idempotent upsert and evidence storage are what
matter, not which node mounts it.
"""

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.routers import sync as sync_router

KEY = "apit-sync-key"
# smallest valid JPEG header bytes — enough to be stored and served back
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


@pytest.fixture
def central(monkeypatch):
    monkeypatch.setattr(settings, "sync_api_key", KEY)
    sub = FastAPI()
    sub.include_router(sync_router.router)
    return TestClient(sub)


def _payload(node="apit-edge"):
    return {
        "node": node,
        "cameras": [{"external_id": "apit-sync-cam", "name": "Sync Cam", "location": "Paldi Circle",
                     "department": "Police", "district": "Ahmedabad", "lat": 23.01, "lon": 72.56,
                     "health": "ok", "monitoring": True, "source_type": "rtsp"}],
        "detections": [{"camera_external_id": "apit-sync-cam", "ts": "2026-09-20T10:00:00Z",
                        "plate_text": "GJ95SY0001", "plate_conf": 0.91,
                        "snapshot_path": "detections/apit-sync/d1.jpg",
                        "snapshot_b64": base64.b64encode(JPEG).decode()}],
        "alerts": [{"plate": "GJ95SY0002", "camera_external_id": "apit-sync-cam",
                    "ts": "2026-09-20T10:05:00Z", "severity": "high", "reason": "stolen",
                    "fir_ref": "FIR/SYNC/1", "match_type": "probable", "read_as": "GJ95SYO002",
                    "snapshot_path": "alerts/apit-sync/a1.jpg",
                    "snapshot_b64": base64.b64encode(JPEG).decode()}],
    }


def test_push_requires_the_shared_key(central):
    assert central.post("/api/sync/push", json=_payload()).status_code == 401
    assert central.post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": "wrong"}).status_code == 401


def test_push_refused_when_channel_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "sync_api_key", "")
    sub = FastAPI()
    sub.include_router(sync_router.router)
    r = TestClient(sub).post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": "anything"})
    assert r.status_code == 503


def test_push_upserts_and_replays_idempotently(central, client, admin):
    r = central.post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": KEY})
    assert r.status_code == 200, r.text
    assert r.json() == {"cameras_new": 1, "detections_new": 1, "alerts_new": 1}

    cams = {c["external_id"]: c for c in client.get("/api/atlas/cameras", headers=admin).json()}
    cam = cams["apit-sync-cam"]
    assert cam["source_url"] == ""                         # the centre never holds stream URLs
    assert cam["health"] == "ok" and cam["monitoring"] is True and cam["district"] == "Ahmedabad"

    dets = client.get("/api/insight/detections?plate=GJ95SY0001", headers=admin).json()
    assert len(dets) == 1 and dets[0]["camera_id"] == cam["id"]

    wl = {w["plate"]: w for w in client.get("/api/watch/vehicles", headers=admin).json()}
    assert wl["GJ95SY0002"]["added_by"] == "edge-sync" and wl["GJ95SY0002"]["fir_ref"] == "FIR/SYNC/1"
    ep = next(e for e in client.get("/api/watch/alerts/episodes?hours=100000", headers=admin).json()
              if e["plate"] == "GJ95SY0002")
    assert ep["match_type"] == "probable" and ep["read_as"] == ["GJ95SYO002"]

    # replay: nothing new, nothing duplicated
    r = central.post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": KEY})
    assert r.json() == {"cameras_new": 0, "detections_new": 0, "alerts_new": 0}
    assert len(client.get("/api/insight/detections?plate=GJ95SY0001", headers=admin).json()) == 1

    trail = client.get("/api/atlas/audit?limit=5", headers=admin).json()
    assert trail[0]["action"] == "sync.push" and trail[0]["actor"] == "edge:apit-edge"


def test_replay_updates_alert_fields_in_place(central, client, admin):
    central.post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": KEY})
    changed = _payload()
    changed["alerts"][0]["status"] = "acknowledged"
    changed["alerts"][0]["severity"] = "medium"
    r = central.post("/api/sync/push", json=changed, headers={"X-Sync-Key": KEY})
    assert r.json()["alerts_new"] == 0
    acked = [a for a in client.get("/api/watch/alerts?status=acknowledged&limit=500", headers=admin).json()
             if a["severity"] == "medium"]
    assert acked


def test_inlined_evidence_is_stored_and_served_from_the_database(central, client, admin):
    central.post("/api/sync/push", json=_payload(), headers={"X-Sync-Key": KEY})
    r = client.get("/data/detections/apit-sync/d1.jpg", headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == JPEG
    assert client.get("/data/alerts/apit-sync/a1.jpg", headers=admin).content == JPEG
    client.cookies.clear()   # the shared jar still holds the media cookie from login
    assert client.get("/data/detections/apit-sync/d1.jpg").status_code == 401


def test_detection_for_unknown_camera_is_dropped_not_crashed(central):
    payload = {"cameras": [], "detections": [{"camera_external_id": "apit-never", "ts": "2026-09-20T10:00:00Z",
                                              "plate_text": "GJ95SY0009"}], "alerts": []}
    r = central.post("/api/sync/push", json=payload, headers={"X-Sync-Key": KEY})
    assert r.status_code == 200 and r.json()["detections_new"] == 0


def test_payload_validation(central):
    r = central.post("/api/sync/push", json={"detections": [{"plate_text": "x"}]}, headers={"X-Sync-Key": KEY})
    assert r.status_code == 422


def test_detection_and_its_alert_may_share_one_snapshot(central):
    """An alert and the detection it was raised from carry the same image.

    The session runs with autoflush off, so the Evidence row added for the
    detection is invisible to the alert's lookup until something flushes.
    Adding it twice violates Evidence.path's unique constraint at commit, and
    the whole push fails — which is what the hosted tier was doing. The
    watchlist entry has to exist beforehand to reproduce it: creating one
    flushes, and the flush hid the bug on a first-ever sync.
    """
    shared = "detections/apit-shared/s1.jpg"
    b64 = base64.b64encode(JPEG).decode()
    seed = {
        "node": "apit-edge",
        "cameras": [{"external_id": "apit-shared-cam", "name": "Shared", "location": "X"}],
        "detections": [],
        "alerts": [{"plate": "GJ95SY7777", "camera_external_id": "apit-shared-cam",
                    "ts": "2026-09-21T09:00:00Z", "reason": "stolen", "fir_ref": "FIR/SHARED/1",
                    "snapshot_path": "alerts/apit-shared/seed.jpg", "snapshot_b64": b64}],
    }
    assert central.post("/api/sync/push", json=seed, headers={"X-Sync-Key": KEY}).status_code == 200

    both = {
        "node": "apit-edge",
        "cameras": [],
        "detections": [{"camera_external_id": "apit-shared-cam", "ts": "2026-09-21T10:00:00Z",
                        "plate_text": "GJ95SY7777", "plate_conf": 0.93,
                        "snapshot_path": shared, "snapshot_b64": b64}],
        # a second apart, so this pair is not also a duplicate observation —
        # the retention dedup tests count those, and the shared snapshot is
        # the only condition this test is about
        "alerts": [{"plate": "GJ95SY7777", "camera_external_id": "apit-shared-cam",
                    "ts": "2026-09-21T10:00:01Z", "reason": "stolen", "fir_ref": "FIR/SHARED/1",
                    "snapshot_path": shared, "snapshot_b64": b64}],
    }
    r = central.post("/api/sync/push", json=both, headers={"X-Sync-Key": KEY})
    assert r.status_code == 200, r.text
    assert r.json()["detections_new"] == 1 and r.json()["alerts_new"] == 1
