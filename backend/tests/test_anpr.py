"""ANPR normalisation and matching — the correctness core of the evaluation."""

from app.services import anpr


def test_valid_plate_passes_through():
    assert anpr.normalise_plate("GJ01AB1234") == ("GJ01AB1234", True)


def test_bharat_series_valid():
    assert anpr.normalise_plate("22BH1234AB") == ("22BH1234AB", True)


def test_state_code_repair_i_to_j():
    assert anpr.normalise_plate("GI01D7553") == ("GJ01D7553", True)


def test_structure_forcing_repairs_leading_digit():
    assert anpr.normalise_plate("6I01D7553") == ("GJ01D7553", True)


def test_invalid_state_code_rejected():
    plate, valid = anpr.normalise_plate("XX01AB1234")
    assert not valid


def test_partial_reads_rejected():
    for junk in ("113117", "417T397", "K02TCJ"):
        _, valid = anpr.normalise_plate(junk)
        assert not valid, junk


def test_fuzzy_similarity_confusion_fold():
    assert anpr.plate_similarity("GJ01D7553", "GJ01D7553") == "exact"
    assert anpr.plate_similarity("GJ0ID7553", "GJ01D7553") == "probable"  # I/1 fold
    assert anpr.plate_similarity("GJ99Z9999", "GJ01D7553") is None


def test_vote_plate_majority():
    reads = [("GJ01D7553", [0.9] * 9), ("GJ01D7553", [0.9] * 9), ("GJ01O7553", [0.4] * 9)]
    voted, conf = anpr.vote_plate(reads)
    assert voted == "GJ01D7553"
    assert conf > 0.5


def test_probable_match_is_labelled_not_silently_downgraded():
    """A fuzzy watchlist hit must stay identifiable as fuzzy.

    Severity alone cannot carry this: a medium-priority entry matched only
    after OCR-confusion folding ends up with the same severity as one matched
    character for character, so the distinction has to be persisted separately
    or an operator sees an inferred plate presented as a confirmed one.
    """
    from app.models import Alert

    exact = Alert(detection_id=1, watchlist_id=1, severity="medium", match_type="exact")
    fuzzy = Alert(detection_id=2, watchlist_id=1, severity="medium", match_type="probable")
    assert exact.severity == fuzzy.severity
    assert exact.match_type != fuzzy.match_type

    # the label the backfill/matcher assigns comes straight from the comparator
    assert anpr.plate_similarity("GJ81O1512", "GJ81O7512") == "probable"
    assert anpr.plate_similarity("GJ81O7512", "GJ81O7512") == "exact"


def test_alert_model_defaults_to_exact():
    """Rows created before the column existed must not claim more than 'exact'
    by omission — the default is explicit and the backfill corrects history."""
    from app.models import Alert

    assert Alert.__table__.c.match_type.default.arg == "exact"
