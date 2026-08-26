"""Government-database connector: the representative dataset must deploy.

It previously lived only under the gitignored runtime data/ directory, so it
was absent from every built image. The hosted tier returned 404 for every
lookup and the VAHAN correlation panel — a headline requirement — was blank on
the judge URL while passing locally.
"""

import json

from app.connectors.vahan import RepresentativeVahanConnector


def test_packaged_dataset_ships_with_the_code():
    """Guards the regression: the file must sit inside the package, not in
    the runtime data dir that deployment does not carry."""
    assert RepresentativeVahanConnector._PACKAGED.is_file()
    records = json.loads(RepresentativeVahanConnector._PACKAGED.read_text(encoding="utf-8"))
    assert records, "packaged dataset must not be empty"


def test_lookup_without_any_runtime_data_dir(tmp_path, monkeypatch):
    """Simulates a fresh deployment: nothing in data/, packaged file only."""
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    c = RepresentativeVahanConnector()
    assert c.available()

    plate = next(iter(json.loads(RepresentativeVahanConnector._PACKAGED.read_text(encoding="utf-8"))))
    rec = c.lookup(plate)
    assert rec is not None
    assert rec["registration_no"] == plate
    assert rec["source"].startswith("VAHAN")


def test_operator_override_wins_over_packaged(tmp_path, monkeypatch):
    """A real extract dropped into data/ must take precedence."""
    from app.config import settings

    (tmp_path / "vahan_representative.json").write_text(
        json.dumps({"GJ99ZZ9999": {"maker": "Override", "model": "X"}}), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    c = RepresentativeVahanConnector()
    assert c.lookup("GJ99ZZ9999")["maker"] == "Override"


def test_unknown_plate_returns_none(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert RepresentativeVahanConnector().lookup("XX00XX0000") is None


def test_corrupt_dataset_does_not_crash_the_endpoint(tmp_path, monkeypatch):
    from app.config import settings

    (tmp_path / "vahan_representative.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert RepresentativeVahanConnector().lookup("GJ01D7553") is None
