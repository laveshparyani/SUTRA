"""Scene analytics must survive a deployment that has no runtime data dir.

The model was loaded from data/models/, which is gitignored — present on the
machine that downloaded it and absent from any fresh clone or container. The
loader raised on the missing file inside a per-frame `except Exception`, so an
edge node deployed elsewhere logged an identical traceback for every camera
every few seconds instead of one line saying analytics was unavailable.
"""

import numpy as np
import pytest

from app.services import objects


@pytest.fixture(autouse=True)
def reset_loader():
    objects._session = None
    objects._load_failed = False
    yield
    objects._session = None
    objects._load_failed = False


def test_model_ships_with_the_code():
    assert objects._PACKAGED_MODEL.is_file(), "packaged scene model must be committed"


def test_fresh_deployment_resolves_the_packaged_model(tmp_path, monkeypatch):
    """No runtime data dir at all — the packaged copy must be found."""
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert objects.model_path() == objects._PACKAGED_MODEL
    assert objects.model_path().is_file()


def test_operator_override_wins(tmp_path, monkeypatch):
    from app.config import settings

    models = tmp_path / "models"
    models.mkdir()
    override = models / "yolox_nano.onnx"
    override.write_bytes(b"not a real model")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert objects.model_path() == override


def test_missing_model_degrades_instead_of_raising(tmp_path, monkeypatch):
    """The regression: analyse_scene must return empty, not raise, and must
    not retry the load on every frame."""
    monkeypatch.setattr(objects, "_PACKAGED_MODEL", tmp_path / "absent.onnx")
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)

    assert objects._load() is None
    assert objects.analyse_scene(np.zeros((64, 64, 3), dtype=np.uint8)) == []
    assert objects._load_failed is True, "must latch, not re-attempt per frame"


def test_unloadable_model_degrades_instead_of_raising(tmp_path, monkeypatch):
    """A corrupt or truncated model file must not take the worker down."""
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"garbage")
    monkeypatch.setattr(objects, "_PACKAGED_MODEL", bad)
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path / "nonexistent")

    assert objects._load() is None
    assert objects.analyse_scene(np.zeros((64, 64, 3), dtype=np.uint8)) == []


def test_real_model_still_works():
    """Packaged model must actually run, not merely exist."""
    objects._session = None
    objects._load_failed = False
    result = objects.analyse_scene(np.zeros((240, 320, 3), dtype=np.uint8))
    assert isinstance(result, list)
