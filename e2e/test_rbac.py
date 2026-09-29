"""Roles are enforced by the server, not merely hidden in the interface.

Both halves matter. Hiding a button is a courtesy; refusing the request is the
control. A viewer who crafts the call by hand must still be refused.
"""

import json
import urllib.error
import urllib.request

from conftest import ADMIN, VIEWER, api_token, sign_in


def test_viewer_is_offered_no_action_controls(page, server, seeded):
    sign_in(page, server, *VIEWER)
    page.goto(f"{server}/watchlist", wait_until="commit")
    page.wait_for_selector("table.grid", timeout=20000)

    assert page.locator("button:has-text('Add')").count() == 0, \
        "a read-only viewer was offered a control that changes state"
    assert page.locator("table.grid tbody tr").count() >= 1, \
        "the viewer should still be able to read the watchlist"


def test_viewer_is_refused_by_the_server(server, seeded):
    token = api_token(server, *VIEWER)
    req = urllib.request.Request(
        f"{server}/api/watch/vehicles",
        data=json.dumps({"plate": "GJ09XX9999", "reason": "stolen"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        raise AssertionError("a viewer was allowed to write to the watchlist")
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"expected 403 for a viewer, got {e.code}"


def test_operator_may_do_what_the_viewer_may_not(server, seeded):
    token = api_token(server, "operator_police", "E2eOperator@26")
    req = urllib.request.Request(
        f"{server}/api/watch/vehicles",
        data=json.dumps({"plate": "GJ09YY8888", "reason": "suspect"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        assert r.status in (200, 201)


def test_camera_data_is_not_readable_without_a_session(server):
    try:
        urllib.request.urlopen(f"{server}/api/atlas/cameras", timeout=15)
        raise AssertionError("camera data was served to an anonymous caller")
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"expected 401 without a session, got {e.code}"


def test_evidence_is_not_served_without_a_session(server):
    try:
        urllib.request.urlopen(f"{server}/data/detections/anything.jpg", timeout=15)
        raise AssertionError("evidence was served to an anonymous caller")
    except urllib.error.HTTPError as e:
        assert e.code in (401, 404), f"expected 401 or 404, got {e.code}"
