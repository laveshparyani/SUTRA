"""Drive and record the demo videos in a Playwright-controlled browser.

Screen capture was tried first and does not work here: ffmpeg's gdigrab either
records whichever window happens to be in front (so the take catches the tool
driving it), or, when targeted at the Chrome window by title, returns black
frames — Chrome composites on the GPU and there is nothing in the GDI surface
to copy. Driving Chrome over CDP also stamps a "Claude started debugging this
browser" banner across every frame.

Playwright records from inside the browser's own compositor, so none of that
applies: focus is irrelevant, the GPU path is captured directly, and its
Chromium shows no debugging banner.

Each shot is held for exactly the duration of its narration line, read from the
timeline produced by make_narration.py, so the picture and the voice line up
when they are muxed without anyone editing by hand.

    python scripts/record_demo.py v1 <narration_dir> <out_dir>
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
USER, PASSWORD = "admin", "SutraAdmin@26"
TRACE_PLATE = "GJ32AG0416"      # 29 reads on a government camera — a populated result


class Shot:
    """Holds a page on screen for exactly its narration length.

    Actions are given a slice of the budget; whatever is left is spent idle so
    the shot never runs short or long. Motion matters more than information
    here — a still frame for 25 seconds reads as a screenshot, not a system.
    """

    def __init__(self, page, seconds: float, name: str):
        self.page, self.budget, self.name = page, seconds, name
        self.start = time.monotonic()

    @property
    def left(self) -> float:
        return max(0.0, self.budget - (time.monotonic() - self.start))

    # Every mouse call is a round trip to the browser, and that overhead is not
    # in the requested sleep. At 25 steps a second it compounded into several
    # seconds a shot and pushed the first take 19s past its narration. Steps are
    # now sparser, and both loops watch the clock and stop when the budget is
    # gone, so a shot can finish a motion early but can never overrun.
    def glide(self, x1, y1, x2, y2, seconds):
        """Move the cursor slowly between two points — visible, unhurried."""
        seconds = min(seconds, self.left)
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        steps = max(2, int(seconds * 10))
        self.page.mouse.move(x1, y1)
        for i in range(1, steps + 1):
            if time.monotonic() >= deadline:
                break
            self.page.mouse.move(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
            pause = (deadline - time.monotonic()) / max(1, steps - i + 1)
            if pause > 0:
                self.page.wait_for_timeout(int(pause * 1000))

    def scroll(self, total_px, seconds, x=960, y=600):
        seconds = min(seconds, self.left)
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        steps = max(2, int(seconds * 6))
        self.page.mouse.move(x, y)
        for i in range(steps):
            if time.monotonic() >= deadline:
                break
            self.page.mouse.wheel(0, total_px / steps)
            pause = (deadline - time.monotonic()) / max(1, steps - i)
            if pause > 0:
                self.page.wait_for_timeout(int(pause * 1000))

    def hold(self):
        """Spend whatever remains, then report the overshoot."""
        remaining = self.left
        if remaining > 0:
            self.page.wait_for_timeout(int(remaining * 1000))
        actual = time.monotonic() - self.start
        print(f"  {self.name:<14} target {self.budget:6.1f}s  actual {actual:6.1f}s")


def goto(page, path):
    # "commit" rather than "domcontentloaded": an MJPEG response never ends, so
    # after the video wall the open streams keep the page from ever reaching a
    # loaded state and the navigation times out. Committing is enough — the SPA
    # paints on its own and each shot waits afterwards anyway.
    page.goto(f"{BASE}{path}", wait_until="commit", timeout=60000)
    page.wait_for_timeout(900)       # let the first data fetch paint


def close_lightbox(page):
    """Dismiss the evidence overlay.

    It closes on click rather than on Escape, and while it is open it covers
    the page and swallows the next shot's click."""
    box = page.locator(".lightbox")
    if box.count():
        box.first.click(force=True)
        page.wait_for_timeout(500)
    page.wait_for_selector(".lightbox", state="detached", timeout=5000)


def drop_streams(page):
    """Release the wall's MJPEG sockets before navigating on.

    Chromium allows about six connections per host and each live tile holds one
    open indefinitely, so leaving the wall directly starves the next
    navigation. A blank page closes them."""
    page.goto("about:blank", wait_until="commit", timeout=30000)
    page.wait_for_timeout(700)


def video_one(page, dur):
    """Own-feed demonstration. dur maps shot name -> seconds."""

    # 1 — sign in, then let the Overview settle. The login is worth showing:
    # it is the access gate the security section of the HLD describes.
    s = Shot(page, dur["01_intro"], "01_intro")
    page.fill("input[placeholder='username']", USER)
    page.wait_for_timeout(600)
    page.fill("input[placeholder='password']", PASSWORD)
    page.wait_for_timeout(600)
    page.click("button:has-text('Sign In')")
    page.wait_for_timeout(3500)
    s.glide(500, 400, 1300, 620, min(8, s.left))
    s.hold()

    # 2 — the GIS map carries this shot; drift across the markers
    s = Shot(page, dur["02_overview"], "02_overview")
    s.scroll(500, 5)
    s.glide(700, 700, 1150, 560, min(7, s.left))
    s.hold()

    # 3 — registry table and the scheduler's pin control
    s = Shot(page, dur["03_registry"], "03_registry")
    goto(page, "/registry")
    s.scroll(700, 9)
    s.glide(400, 500, 1500, 430, min(7, s.left))
    s.hold()

    # 4 — the wall is the shot that proves feeds are live
    s = Shot(page, dur["04_wall"], "04_wall")
    goto(page, "/wall")
    page.wait_for_timeout(2200)              # tiles need a beat to start streaming
    s.glide(300, 300, 1550, 320, min(8, s.left))
    s.scroll(600, 8)
    s.hold()
    drop_streams(page)

    # 5 — watchlist entries with their FIR references
    s = Shot(page, dur["05_watchlist"], "05_watchlist")
    goto(page, "/watchlist")
    s.glide(400, 400, 1200, 520, min(7, s.left))
    s.hold()

    # 6 — an alert, its annotated evidence, and the connector panel
    s = Shot(page, dur["06_alerts"], "06_alerts")
    goto(page, "/alerts")
    page.wait_for_timeout(1500)
    thumb = page.locator("img.evidence-thumb").first
    if thumb.count():
        thumb.click()
        page.wait_for_timeout(4000)          # hold the lightbox open, it is the evidence
        close_lightbox(page)
    s.scroll(400, 6)
    s.hold()

    # 7 — the evaluation scenario itself; give it room
    s = Shot(page, dur["07_trace"], "07_trace")
    goto(page, "/trace")
    page.fill("input[placeholder='GJ01AB1234']", TRACE_PLATE)
    page.wait_for_timeout(900)
    page.keyboard.press("Enter")
    page.wait_for_timeout(4200)              # timeline, map and vehicle panel
    s.glide(400, 400, 500, 720, min(6, s.left))
    s.scroll(350, 6, x=400)
    s.hold()

    # 8 — the exported report closes the video
    s = Shot(page, dur["08_report"], "08_report")
    goto(page, "/detections")
    page.wait_for_timeout(2000)
    btn = page.locator("button:has-text('Output report')").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(2500)
    s.scroll(400, 5)
    s.hold()


def video_two(page, dur):
    """Government-feed demonstration — the take the evaluation weighs most.

    Every shot must visibly be the portal's own cameras, so this one opens on
    the registry mid-discovery rather than on a dashboard.
    """

    # 1 — sign in, then run discovery against the portal catalogue
    s = Shot(page, dur["01_onboard"], "01_onboard")
    page.fill("input[placeholder='username']", USER)
    page.wait_for_timeout(500)
    page.fill("input[placeholder='password']", PASSWORD)
    page.wait_for_timeout(500)
    page.click("button:has-text('Sign In')")
    page.wait_for_timeout(2500)
    goto(page, "/registry")
    disc = page.locator("button:has-text('Discover')").first
    if disc.count():
        disc.click()
        page.wait_for_timeout(5000)      # let it report created/updated
    s.scroll(500, 6)
    # linger on a source URL: the narration claims no credentials are stored
    s.glide(500, 480, 1450, 560, min(6, s.left))
    s.hold()

    # 2 — the portal's cameras actually streaming
    s = Shot(page, dur["02_live"], "02_live")
    goto(page, "/wall")
    page.wait_for_timeout(2500)
    s.glide(300, 300, 1550, 340, min(9, s.left))
    s.scroll(550, 8)
    s.hold()
    drop_streams(page)

    # 3 — longest shot: ANPR output, and the confidence column the narration
    #     spends half its words justifying
    s = Shot(page, dur["03_anpr"], "03_anpr")
    goto(page, "/detections")
    page.wait_for_timeout(2000)
    s.scroll(450, 8)
    s.glide(500, 620, 1350, 470, min(9, s.left))
    s.scroll(-250, 5)
    s.hold()

    # 4 — one evidence crop, held open
    s = Shot(page, dur["04_evidence"], "04_evidence")
    thumb = page.locator("img.evidence-thumb").first
    if thumb.count():
        thumb.click()
        page.wait_for_timeout(max(1000, min(8000, int(s.left * 1000) - 2500)))
        close_lightbox(page)
    s.hold()

    # 5 — export the report
    s = Shot(page, dur["05_report"], "05_report")
    btn = page.locator("button:has-text('Output report')").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(2500)
    s.scroll(350, 5)
    s.hold()

    # 6 — Atlas closes it: coverage, gap analysis, audit
    s = Shot(page, dur["06_atlas"], "06_atlas")
    goto(page, "/atlas")
    page.wait_for_timeout(2500)
    s.glide(500, 400, 1200, 520, min(7, s.left))
    s.scroll(900, 10)
    s.hold()


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "v1"
    narration = Path(sys.argv[2])
    outdir = Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)

    timeline = json.loads((narration / "timeline.json").read_text(encoding="utf-8"))
    dur = {s["shot"]: s["duration"] for s in timeline[which]}
    target = sum(dur.values())
    print(f"{which}: {len(dur)} shots, target {target:.1f}s\n")

    began = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized", "--hide-scrollbars"])
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(outdir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        goto(page, "/login")
        page.wait_for_timeout(1500)

        {"v1": video_one, "v2": video_two}[which](page, dur)

        ctx.close()      # flushes the video file
        browser.close()

    elapsed = time.monotonic() - began
    vids = sorted(outdir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    print(f"\nwall clock {elapsed:.1f}s (narration {target:.1f}s)")
    print(f"video -> {vids[-1] if vids else 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
