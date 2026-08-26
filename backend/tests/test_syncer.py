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
