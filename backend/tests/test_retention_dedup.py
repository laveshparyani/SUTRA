"""Collapsing detections that repeat one identical observation.

The edge->central intake inserted a detection before checking whether the
alert already existed, so every replay of the alert history orphaned a copy.
With a sync cursor that reset on each restart, the hosted tier reached 28
copies of a single observation and 59% redundant rows, inflating every count
a judge sees.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models import Alert, Camera, Detection, WatchlistVehicle
from app.services.retention import RetentionWorker

TS = datetime(2026, 8, 21, 9, 4, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    Base.metadata.create_all(engine)
    s = SessionLocal()
    cam = Camera(external_id="dedup-cam", name="Dedup Cam", source_url="")
    s.add(cam)
    s.flush()
    yield s, cam.id
    s.rollback()
    s.close()


def test_identical_observations_collapse_to_one(db):
    s, cam_id = db
    for _ in range(5):
        s.add(Detection(camera_id=cam_id, ts=TS, plate_text="GJ01D7553"))
    s.flush()

    collapsed = RetentionWorker()._collapse_duplicates(s)
    s.flush()

    assert collapsed == 4
    remaining = s.query(Detection).filter(Detection.plate_text == "GJ01D7553").all()
    assert len(remaining) == 1


def test_distinct_observations_are_untouched(db):
    """Same plate at different times, and different plates at one time, are
    real observations — collapsing them would destroy the trace."""
    s, cam_id = db
    s.add(Detection(camera_id=cam_id, ts=TS, plate_text="GJ05AA1111"))
    s.add(Detection(camera_id=cam_id, ts=TS + timedelta(seconds=1), plate_text="GJ05AA1111"))
    s.add(Detection(camera_id=cam_id, ts=TS, plate_text="GJ05BB2222"))
    s.flush()

    assert RetentionWorker()._collapse_duplicates(s) == 0
    assert s.query(Detection).filter(Detection.plate_text.like("GJ05%")).count() == 3


def test_row_with_evidence_survives(db):
    """Evidence is what an operator acts on; the copy holding it must win."""
    s, cam_id = db
    bare = Detection(camera_id=cam_id, ts=TS, plate_text="GJ07EV1234")
    withimg = Detection(camera_id=cam_id, ts=TS, plate_text="GJ07EV1234",
                        snapshot_path="detections/1/evidence.jpg")
    s.add_all([bare, withimg])
    s.flush()
    kept_id = withimg.id

    RetentionWorker()._collapse_duplicates(s)
    s.flush()

    rows = s.query(Detection).filter(Detection.plate_text == "GJ07EV1234").all()
    assert len(rows) == 1
    assert rows[0].id == kept_id
    assert rows[0].snapshot_path


def test_alerts_are_repointed_not_orphaned(db):
    """Deleting a duplicate must never leave an alert pointing at nothing."""
    s, cam_id = db
    entry = WatchlistVehicle(plate="GJ09AL0001", reason="stolen", added_by="test")
    s.add(entry)
    s.flush()

    keep = Detection(camera_id=cam_id, ts=TS, plate_text="GJ09AL0001",
                     snapshot_path="detections/1/a.jpg")
    dup = Detection(camera_id=cam_id, ts=TS, plate_text="GJ09AL0001")
    s.add_all([keep, dup])
    s.flush()

    alert = Alert(detection_id=dup.id, watchlist_id=entry.id, ts=TS, severity="high")
    s.add(alert)
    s.flush()

    RetentionWorker()._collapse_duplicates(s)
    s.flush()

    s.refresh(alert)
    assert alert.detection_id == keep.id
    assert s.get(Detection, keep.id) is not None
