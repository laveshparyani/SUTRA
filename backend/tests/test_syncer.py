"""Edge->central sync: restart survival and batch shaping."""

from app.services.syncer import Syncer, _MAX_BATCH_EVIDENCE_BYTES


def test_cursor_survives_restart(tmp_path, monkeypatch):
    """An in-memory-only cursor meant every restart re-sent the full detection
    history — multi-megabyte batches the central tier answered with 500s, and
    the failed batch was retried identically every 30 s. The cursor now
    persists, so a restarted edge resumes where it left off."""
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s1 = Syncer.__new__(Syncer)          # avoid Thread init side effects
    s1.last_detection_id, s1.last_alert_id = 641, 95
    s1._save_cursor()

    s2 = Syncer.__new__(Syncer)
    assert s2._load_cursor() == (641, 95)


def test_missing_cursor_defaults_to_zero(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s = Syncer.__new__(Syncer)
    assert s._load_cursor() == (0, 0)


def test_corrupt_cursor_defaults_to_zero(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / ".sync_cursor").write_text("not numbers")
    s = Syncer.__new__(Syncer)
    assert s._load_cursor() == (0, 0)


def test_evidence_budget_is_bounded():
    """A batch's inlined evidence must stay well under what a 512 MB central
    instance can absorb in one request."""
    assert _MAX_BATCH_EVIDENCE_BYTES <= 1_000_000


def test_alert_payload_carries_match_type_and_raw_read():
    """A fuzzy hit must stay fuzzy across the federation boundary.

    The edge sends the *watchlist* plate as the alert's identity, so the
    central tier never sees the raw OCR read and cannot recompute the match
    class. Omitting it defaulted every synced alert to 'exact', which
    presented a one-character OCR inference on the judge-facing tier as a
    confirmed identification — the exact claim the edge UI refuses to make.
    """
    from app.routers.sync import AlertIn

    fields = AlertIn.model_fields
    assert "match_type" in fields
    assert "read_as" in fields

    fuzzy = AlertIn(plate="GJ81O7512", camera_external_id="sentinel-36",
                    ts="2026-08-20T07:14:36Z", match_type="probable", read_as="GJ01O7512")
    assert fuzzy.match_type == "probable"
    assert fuzzy.read_as == "GJ01O7512"


def test_alert_payload_defaults_are_backward_compatible():
    """An older edge that does not send the field must still be accepted."""
    from app.routers.sync import AlertIn

    legacy = AlertIn(plate="GJ01D7553", camera_external_id="sentinel-31", ts="2026-08-20T07:14:36Z")
    assert legacy.match_type == "exact"
    assert legacy.read_as == ""
