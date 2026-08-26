"""Operator-facing translation of FFmpeg's raw failure text."""

from app.services.ffreader import explain_error


def test_windows_errno_becomes_a_cause():
    """FFmpeg prints AVERROR(ETIMEDOUT) as a bare -138 on Windows (MSVCRT
    numbers ETIMEDOUT 138, not glibc's 110). 'Error number -138 occurred' tells
    a control-room operator nothing about whether to send someone out."""
    msg = explain_error("Error opening input files: Error number -138 occurred")
    assert "timed out" in msg
    assert "-138" not in msg


def test_no_packets_explained():
    msg = explain_error(
        "[out#0/rawvideo @ 000002224f46aa00] Nothing was written into output file, "
        "because at least one of its streams received no packets."
    )
    assert msg == "connected, but the source sent no video packets"


def test_component_prefix_and_pointer_stripped_from_unknown_text():
    """An unrecognised message still reaches the operator — but without
    FFmpeg's internal component tag and heap address."""
    msg = explain_error("[hls @ 0x7f9e1c00] some future failure mode")
    assert msg == "some future failure mode"


def test_unknown_message_is_passed_through_not_swallowed():
    assert explain_error("brand new failure") == "brand new failure"
    assert explain_error("") == ""


def test_http_status_codes_named():
    assert "no longer exists" in explain_error("Server returned 404 Not Found")
    assert "forbidden" in explain_error("Server returned 403 Forbidden")
