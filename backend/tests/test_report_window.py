"""The output report's since/until window must be a datetime comparison.
Passing an ISO string with a 'T' separator used to return zero rows on
SQLite, because the raw string sorted above every stored timestamp."""

from datetime import datetime, timezone

from app.db import Base, SessionLocal, engine
from app.models import Camera, Detection

TS = datetime(2026, 9, 24, 18, 0, 0, tzinfo=timezone.utc)


def _seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    cam = db.query(Camera).filter(Camera.external_id == "report-cam").one_or_none()
    if cam is None:
        cam = Camera(external_id="report-cam", name="Report Cam", source_url="")
        db.add(cam)
        db.flush()
    db.query(Detection).filter(Detection.camera_id == cam.id).delete()
    db.add(Detection(camera_id=cam.id, ts=TS, plate_text="GJ01AB1234", plate_conf=0.9))
    db.commit()
    cam_id = cam.id
    db.close()
    return cam_id


def test_iso_with_t_and_z_selects_rows(client, admin):
    cam_id = _seed()
    r = client.get("/api/insight/report", headers=admin,
                   params={"camera_id": cam_id, "since": "2026-09-24T17:00:00Z"})
    assert r.status_code == 200
    assert "GJ01AB1234" in r.text


def test_window_excludes_rows_outside_it(client, admin):
    cam_id = _seed()
    r = client.get("/api/insight/report", headers=admin,
                   params={"camera_id": cam_id, "since": "2026-09-24T19:00:00Z"})
    assert "GJ01AB1234" not in r.text
    r = client.get("/api/insight/report", headers=admin,
                   params={"camera_id": cam_id, "until": "2026-09-24 17:00"})
    assert "GJ01AB1234" not in r.text


def test_garbage_timestamp_is_a_422(client, admin):
    r = client.get("/api/insight/report", headers=admin, params={"since": "yesterday"})
    assert r.status_code == 422
