"""Dashboard aggregations.

The timezone test exists because of a production-only failure: SQLite hands
back naive datetimes while Postgres hands back aware ones, so datetime
arithmetic that passed locally raised TypeError in the hosted central tier.
These tests pin both shapes.
"""

from datetime import datetime, timedelta, timezone


def _seed(client, admin, ts_list, aware):
    """Insert detections directly, with the tz shape a given backend returns."""
    from app.db import SessionLocal
    from app.models import Camera, Detection

    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.external_id == "an-cam").one_or_none()
        if cam is None:
            cam = Camera(external_id="an-cam", name="Analytics Cam", location="Paldi",
                         department="Police", source_url="rtsp://10.0.0.9/x", health="ok")
            db.add(cam)
            db.flush()
        for i, ts in enumerate(ts_list):
            db.add(Detection(
                camera_id=cam.id,
                ts=ts if aware else ts.replace(tzinfo=None),
                plate_text=f"GJ01AB{1000 + i}",
                plate_conf=0.5 + (i % 5) * 0.1,
            ))
        db.commit()
    finally:
        db.close()


def test_analytics_handles_aware_and_naive_timestamps(client, admin):
    now = datetime.now(timezone.utc)
    _seed(client, admin, [now - timedelta(hours=h) for h in (0, 1, 5)], aware=True)
    _seed(client, admin, [now - timedelta(hours=h) for h in (2, 3)], aware=False)

    r = client.get("/api/insight/analytics?hours=24", headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totals"]["detections"] >= 5
    assert len(d["activity"]) == 24
    assert sum(a["count"] for a in d["activity"]) >= 5


def test_analytics_shape(client, admin):
    d = client.get("/api/insight/analytics?hours=6", headers=admin).json()
    for key in ("totals", "activity", "top_vehicles", "by_camera", "by_department",
                "confidence_bands", "camera_health", "alerts_by_severity"):
        assert key in d, key
    assert len(d["activity"]) == 6
    # confidence bands are ordered low -> high and cover every stored read
    assert [b["band"] for b in d["confidence_bands"]] == ["<60%", "60-75%", "75-90%", ">90%"]


def test_sightings_group_repeated_reads(client, admin):
    """Many reads of one plate on one camera collapse into few sightings."""
    now = datetime.now(timezone.utc)
    from app.db import SessionLocal
    from app.models import Camera, Detection

    db = SessionLocal()
    try:
        cam = db.query(Camera).filter(Camera.external_id == "grp-cam").one_or_none()
        if cam is None:
            cam = Camera(external_id="grp-cam", name="Group Cam", source_url="rtsp://10.0.0.8/x")
            db.add(cam)
            db.flush()
        for i in range(30):            # a vehicle parked in view: 30 reads, minutes apart
            db.add(Detection(camera_id=cam.id, ts=now - timedelta(minutes=i),
                             plate_text="GJ18ZZ4321", plate_conf=0.7))
        db.commit()
    finally:
        db.close()

    rows = client.get("/api/insight/sightings?hours=24&limit=50", headers=admin).json()
    mine = [s for s in rows if s["plate"] == "GJ18ZZ4321"]
    assert mine, "sighting missing"
    assert sum(s["reads"] for s in mine) == 30      # every read accounted for
    assert len(mine) <= 3                           # but collapsed, not 30 rows
    assert mine[0]["camera_name"] == "Group Cam"
