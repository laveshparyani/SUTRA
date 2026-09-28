"""Capture clean, full-resolution screenshots of every SUTRA Command page.

Drives the local dev UI with Playwright (same approach as record_walkthrough.py),
signs in with the sandbox admin account, and writes one PNG per page into the
output directory. Pair with annotate_screenshot.py to add captions.

    python scripts/capture_screenshots.py <out_dir> [--base http://localhost:5173]
                                          [--plate GJ01D7553] [--window 7d]
"""

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = [
    # (file stem, route, settle seconds, prep callable name)
    ("01_login", "/login", 1.5, None),
    ("02_state_overview", "/", 4.0, "overview"),
    ("03_camera_registry", "/registry", 4.0, None),
    ("04_atlas_gis_and_gap_analysis", "/atlas", 5.0, None),
    ("06_detections_browser", "/detections", 4.0, None),
    ("07_detection_evidence", "/detections", 4.0, "evidence"),
    ("08_watchlist", "/watchlist", 3.0, None),
    ("09_alert_centre", "/alerts", 4.0, None),
    ("10_vehicle_trace", "/trace?plate={plate}", 6.0, None),
    ("05_video_wall", "/wall", 8.0, None),   # last: its open streams stall later loads
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--base", default="http://localhost:5173")
    ap.add_argument("--plate", default="GJ01D7553")
    ap.add_argument("--window", default="7d")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="SutraAdmin@26")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1,
                                  color_scheme="dark")
        page = ctx.new_page()

        # login page first, unauthenticated, with the sandbox account typed in
        page.goto(f"{a.base}/login", wait_until="load")
        page.fill("input[placeholder='username']", a.user)
        page.fill("input[placeholder='password']", a.password)
        time.sleep(1.0)
        page.screenshot(path=str(a.out / "01_login.png"))
        page.click("button:has-text('Sign In')")
        page.wait_for_url(f"{a.base}/", timeout=20000)
        time.sleep(2.0)

        for stem, route, settle, prep in PAGES[1:]:
            # "commit" not "load": the video wall keeps MJPEG streams open, so a
            # load event may never fire; a fixed settle after commit is what the
            # walkthrough recorder does too
            try:
                page.goto(f"{a.base}{route.format(plate=a.plate)}", wait_until="commit", timeout=20000)
            except Exception as exc:  # keep going: one slow page must not lose the rest
                print("skip", stem, type(exc).__name__)
                continue
            time.sleep(settle)
            if prep == "overview":
                try:
                    btn = page.locator(f"button:has-text('{a.window}')")
                    if btn.count():
                        btn.first.click(force=True, timeout=5000)
                        time.sleep(2.5)
                except Exception as exc:
                    print("window prep skipped:", type(exc).__name__)
            if prep == "evidence":
                try:
                    raw = page.locator(".seg-toggle button:has-text('Raw reads')").first
                    if raw.count():
                        raw.click(force=True, timeout=5000)
                        time.sleep(2.0)
                    thumb = page.locator("img.evidence-thumb").first
                    if thumb.count():
                        thumb.click(force=True, timeout=5000)
                        time.sleep(1.5)
                except Exception as exc:
                    print("evidence prep skipped:", type(exc).__name__)
            page.screenshot(path=str(a.out / f"{stem}.png"))
            print("captured", stem)

        browser.close()


if __name__ == "__main__":
    main()
