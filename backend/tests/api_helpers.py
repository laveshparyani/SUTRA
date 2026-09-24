"""Shared helpers for the API contract tests (plain functions, not fixtures).

The session-scoped `client` in conftest.py shares one SQLite database across
every test module, so everything created here carries an `apit-` prefix or a
reserved plate range (GJ9x…) to stay clear of rows other modules create.
"""

from datetime import datetime, timedelta, timezone

RTSP = "rtsp://192.0.2.10:554/apit"   # TEST-NET-1: never routable, never started


def login(client, username: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def operator(client) -> dict:
    return login(client, "operator_police", "Operator@26")


def create_camera(client, headers: dict, external_id: str, **overrides) -> dict:
    body = {
        "external_id": external_id,
        "name": overrides.pop("name", external_id),
        "location": overrides.pop("location", "Paldi Circle"),
        "department": overrides.pop("department", "Police"),
        "source_type": overrides.pop("source_type", "rtsp"),
        "source_url": overrides.pop("source_url", RTSP),
        **overrides,
    }
    r = client.post("/api/atlas/cameras", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def get_or_create_camera(client, headers: dict, external_id: str, **overrides) -> dict:
    cams = client.get("/api/atlas/cameras", headers=headers).json()
    for c in cams:
        if c["external_id"] == external_id:
            return c
    return create_camera(client, headers, external_id, **overrides)


def seed_detections(camera_id: int, plate: str, minutes_ago: list[int], conf: float = 0.9,
                    snapshot_path: str = "") -> list[int]:
    """Insert plate reads straight into the store (the ANPR engine is disabled
    in tests). Returns the new detection ids, oldest first."""
    from app.db import SessionLocal
    from app.models import Detection

    now = datetime.now(timezone.utc)
    ids = []
    db = SessionLocal()
    try:
        for m in sorted(minutes_ago, reverse=True):
            det = Detection(camera_id=camera_id, ts=now - timedelta(minutes=m),
                            plate_text=plate, plate_conf=conf, det_conf=0.8,
                            snapshot_path=snapshot_path)
            db.add(det)
            db.flush()
            ids.append(det.id)
        db.commit()
    finally:
        db.close()
    return ids


def seed_alert(detection_id: int, watchlist_id: int, severity: str = "high",
               match_type: str = "exact") -> int:
    from app.db import SessionLocal
    from app.models import Alert

    db = SessionLocal()
    try:
        a = Alert(detection_id=detection_id, watchlist_id=watchlist_id,
                  severity=severity, match_type=match_type)
        db.add(a)
        db.commit()
        return a.id
    finally:
        db.close()
