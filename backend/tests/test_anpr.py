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
