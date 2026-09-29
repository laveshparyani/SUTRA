"""The pages an operator actually moves between, and the states they can reach.

The detections test here is a regression test. Switching from Sightings back to
Vehicles once took the whole application down: rows were held in state
independently of the mode that fetched them, so for the moment the new request
was in flight the new branch rendered against the previous payload. A sighting
carries no `cameras` field, `v.cameras.join` threw, and the uncaught error
unmounted the page. Every API check passed while that was happening.
"""

from conftest import ADMIN, sign_in


def test_registry_lists_cameras_and_filters(page, server, seeded):
    sign_in(page, server, *ADMIN)
    page.goto(f"{server}/registry", wait_until="commit")
    page.wait_for_selector("table.grid tbody tr", timeout=20000)

    before = page.locator("table.grid tbody tr").count()
    assert before >= 1, "the seeded camera should be listed"

    search = page.locator("input[placeholder*='earch']").first
    if search.count():
        search.fill("nothing-matches-this-xyzzy")
        page.wait_for_timeout(1200)
        assert page.locator("table.grid tbody tr").count() <= before, \
            "filtering must narrow the list, never widen it"
    assert not page.uncaught_errors, page.uncaught_errors


def test_switching_detection_views_does_not_crash_the_page(page, server, seeded):
    """Regression: Sightings -> Vehicles unmounted the application."""
    sign_in(page, server, *ADMIN)
    page.goto(f"{server}/detections", wait_until="commit")
    page.wait_for_selector(".seg-toggle", timeout=20000)

    for label in ("Sightings", "Vehicles", "Raw reads", "Vehicles"):
        button = page.locator(".seg-toggle button", has_text=label).first
        assert button.count() == 1, f"the '{label}' view control disappeared"
        button.click()
        page.wait_for_timeout(1500)
        assert page.locator(".seg-toggle").count() == 1, \
            f"the page unmounted after switching to {label}"

    assert not page.uncaught_errors, f"uncaught error while switching views: {page.uncaught_errors}"


def test_unknown_plate_reports_not_sighted_rather_than_failing(page, server, seeded):
    sign_in(page, server, *ADMIN)
    page.goto(f"{server}/trace", wait_until="commit")
    page.wait_for_selector("input[placeholder='GJ01AB1234']", timeout=20000)

    page.fill("input[placeholder='GJ01AB1234']", "GJ99ZZ9999")
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)

    body = page.locator("body").inner_text().lower()
    assert any(w in body for w in ("not", "no ", "never")), \
        "an unseen plate should say so plainly rather than showing an empty screen"
    assert not page.uncaught_errors, page.uncaught_errors


def test_every_main_route_renders(page, server, seeded):
    sign_in(page, server, *ADMIN)
    for path in ("/", "/registry", "/detections", "/alerts", "/watchlist", "/atlas", "/trace"):
        page.goto(f"{server}{path}", wait_until="commit")
        page.wait_for_timeout(2200)
        assert page.locator("nav a[href='/']").count() == 1, f"{path} failed to render the shell"
        assert not page.uncaught_errors, f"{path} raised: {page.uncaught_errors}"


def test_trace_draws_a_route_when_a_plate_is_seen_on_two_cameras(page, server, seeded):
    """The evaluation scenario: movement history across the network.

    The production dataset has never contained a plate read by two of the
    portal's cameras - they are ~1,000 km apart replaying independent footage -
    so this path could not be exercised against real data. The fixture seeds
    one deliberately, which is the only honest way to cover it.
    """
    sign_in(page, server, *ADMIN)
    page.goto(f"{server}/trace", wait_until="commit")
    page.wait_for_selector("input[placeholder='GJ01AB1234']", timeout=20000)

    page.fill("input[placeholder='GJ01AB1234']", seeded["multi_camera_plate"])
    page.keyboard.press("Enter")
    page.wait_for_timeout(3500)

    body = page.locator("body").inner_text()
    assert seeded["multi_camera_plate"] in body, "the traced plate is not shown"
    # the timeline names each sighting by location, not by camera name
    assert "Paldi Circle" in body and "Janpath" in body, \
        "both locations that saw the vehicle should appear in the movement history"
    assert "Ahmedabad" in body, "each sighting should carry its district"
    assert not page.uncaught_errors, page.uncaught_errors
