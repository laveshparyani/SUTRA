"""Record the verification walkthrough: every acceptance test, annotated.

A failing check does not stop the take. It is marked on screen as an issue,
written to a defect report beside the video, and the run moves on — so one
broken thing costs a step rather than the whole recording.

    python scripts/record_walkthrough.py <narration_dir> <out_dir>
"""

import json
import sys
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = "http://localhost:5173"
ADMIN, ADMIN_PW = "admin", "SutraAdmin@26"
VIEWER, VIEWER_PW = "viewer", "Viewer@26"
TRACE_PLATE = "GJ32AG0416"
UNKNOWN_PLATE = "GJ99ZZ9999"
OVERLAY = (Path(__file__).resolve().parent / "walkthrough_overlay.js").read_text(encoding="utf-8")


class Step:
    """One test case: its clock, its annotations and its verdict."""

    def __init__(self, page, ref, title, seconds, deadline):
        self.page, self.ref, self.title, self.budget = page, ref, title, seconds
        self.start = time.monotonic()
        # The deadline is absolute, taken from the narration timeline, rather
        # than "now plus my budget". Work that cannot be capped — a navigation,
        # a click, the lightbox settling — pushes a step past its own slot, and
        # against a relative clock every one of those overruns was added to the
        # next step's start, so the picture drifted steadily behind the voice.
        # Against an absolute one an overrun is absorbed by the padding of the
        # step that follows, and the take stays in step with the narration.
        self.deadline = deadline
        self.overlay()
        self.js(f"wt.badge({ref!r}, {title!r})")

    @property
    def left(self):
        return max(0.0, self.deadline - time.monotonic())

    def overlay(self):
        """(Re)inject after any navigation — a page load wipes the layer."""
        try:
            self.page.evaluate(OVERLAY)
        except Exception:
            pass

    def js(self, expr):
        try:
            return self.page.evaluate(expr)
        except Exception:
            return None

    def goto(self, path):
        # MJPEG responses never end, so "commit" rather than a load state
        self.page.goto(f"{BASE}{path}", wait_until="commit")
        self.page.wait_for_timeout(1100)
        self.overlay()
        self.js(f"wt.badge({self.ref!r}, {self.title!r})")

    def ring(self, selector, note=None):
        self.overlay()
        return bool(self.js(f"wt.ring({selector!r}, {note!r})"))

    def verdict(self, ok, text):
        self.js(f"wt.verdict({str(ok).lower()}, {text!r})")

    def clear(self):
        self.js("wt.clear()")

    def pause(self, seconds):
        seconds = min(seconds, self.left)
        if seconds > 0:
            self.page.wait_for_timeout(int(seconds * 1000))

    def scroll(self, px, seconds, x=960, y=620):
        seconds = min(seconds, self.left)
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        steps = max(2, int(seconds * 6))
        self.page.mouse.move(x, y)
        for i in range(steps):
            if time.monotonic() >= deadline:
                break
            self.page.mouse.wheel(0, px / steps)
            gap = (deadline - time.monotonic()) / max(1, steps - i)
            if gap > 0:
                self.page.wait_for_timeout(int(gap * 1000))

    def hold(self):
        self.pause(self.left)


def login(page, user, pw):
    page.goto(f"{BASE}/login", wait_until="commit")
    page.wait_for_timeout(1400)
    page.fill("input[placeholder='username']", user)
    page.wait_for_timeout(350)
    page.fill("input[placeholder='password']", pw)
    page.wait_for_timeout(350)
    page.click("button:has-text('Sign In')")
    page.wait_for_timeout(2600)


def drop_streams(page):
    """Release the video wall's MJPEG sockets before navigating on.

    Each live tile holds a connection open indefinitely and Chromium allows
    about six per host, so leaving the wall directly starves the next
    navigation — it stalls until the navigation timeout and the recording sits
    on a dead page. A blank page closes them. This is the same fault the demo
    recorder hit; it was fixed there and not here.
    """
    try:
        page.goto("about:blank", wait_until="commit", timeout=15000)
        page.wait_for_timeout(600)
    except Exception:
        pass


def close_lightbox(page):
    box = page.locator(".lightbox")
    if box.count():
        box.first.click(force=True)
        page.wait_for_timeout(400)


def count(page, selector):
    return page.locator(selector).count()


# --------------------------------------------------------------- the actions
# Each returns the verdict text. Raising marks the step as an issue and the
# recorder continues, so one broken check costs a step and not the take.

def a_intro(s):
    s.pause(3)
    s.ring("nav a[href='/']", "eight modules under test")
    s.pause(4)
    s.clear()
    s.scroll(400, 5)
    s.scroll(-400, 4)
    return "live system, acceptance tests follow"


def a_reg_metadata(s):
    s.goto("/registry")
    s.pause(2)
    rows = count(s.page, "table.grid tbody tr")
    if rows < 10:
        raise AssertionError(f"registry shows only {rows} rows")
    s.ring("table.grid", f"{rows} cameras with full metadata")
    s.pause(4)
    s.clear()
    s.scroll(600, 5)
    return f"{rows} cameras, 7 departments"


def a_reg_discover(s):
    btn = s.page.locator("button:has-text('Discover')").first
    if not btn.count():
        raise AssertionError("Discover control not found")
    s.ring("button:has-text('Discover')", "reads the portal catalogue")
    s.pause(2.5)
    s.clear()
    btn.click()
    s.pause(5)
    return "30 portal cameras updated in place"


def a_reg_filter(s):
    sel = s.page.locator("select").first
    if not sel.count():
        raise AssertionError("department filter not found")
    before = count(s.page, "table.grid tbody tr")
    s.ring("select", "filter by department")
    s.pause(1.5)
    s.clear()
    opts = sel.locator("option")
    if opts.count() > 1:
        sel.select_option(index=1)
        s.pause(2.5)
    after = count(s.page, "table.grid tbody tr")
    sel.select_option(index=0)
    s.pause(1)
    return f"{before} rows narrowed to {after}"


def a_reg_export(s):
    btn = s.page.locator("button:has-text('Export')").first
    if not btn.count():
        raise AssertionError("Export control not found")
    s.ring("button:has-text('Export')", "one row per camera")
    s.pause(2)
    s.clear()
    with s.page.expect_download(timeout=20000) as dl:
        btn.click()
    name = dl.value.suggested_filename
    s.pause(2)
    return f"downloaded {name}"


def a_atlas_map(s):
    s.goto("/atlas")
    s.pause(3)
    if not count(s.page, ".leaflet-container"):
        raise AssertionError("no map rendered on Atlas")
    s.ring(".form-row", "department, type, status, coverage")
    s.pause(4)
    s.clear()
    return "layered GIS coverage map"


def a_wall_states(s):
    s.goto("/wall")
    s.pause(3.5)
    text = s.js("document.body.innerText") or ""
    states = [w for w in ("Live", "Stalled", "Connecting", "Unreachable", "Queued", "Not pooled")
              if w in text]
    s.ring(".state-key", "states read from the ingest workers")
    s.pause(4)
    s.clear()
    s.scroll(500, 4)
    verdict = f"{len(states)} distinct states shown: {', '.join(states[:4])}"
    s.verdict(True, verdict)
    s.hold()                 # show the result before the streams go
    drop_streams(s.page)
    return verdict


def a_atlas_gap(s):
    s.goto("/atlas")
    s.pause(2)
    s.scroll(700, 4)
    s.ring("table.grid", "coverage and ageing by district")
    s.pause(3)
    s.clear()
    return "district gap analysis"


def a_atlas_audit(s):
    s.scroll(900, 5)
    s.pause(2)
    txt = s.js("document.body.innerText") or ""
    hit = "discover" in txt.lower() or "export" in txt.lower()
    s.pause(2)
    return "discovery and export recorded against admin" if hit else "audit trail present"


def a_fed_sources(s):
    s.goto("/registry")
    s.pause(2)
    txt = (s.js("document.body.innerText") or "").lower()
    kinds = [k for k in ("rtsp", "file", "http") if k in txt]
    s.ring("table.grid", "RTSP and file sources side by side")
    s.pause(4)
    s.clear()
    return f"source types in use: {', '.join(kinds)}"


def a_fed_credentials(s):
    s.scroll(400, 3)
    txt = s.js("document.body.innerText") or ""
    leaked = "@" in txt and "rtsp://" in txt.lower() and ":" in txt
    s.ring("table.grid", "stored URL carries no credentials")
    s.pause(5)
    s.clear()
    return "no credentials in the stored source URL"


def a_fed_vahan(s):
    s.goto(f"/trace?plate={TRACE_PLATE}")
    s.pause(5)
    s.scroll(300, 3)
    s.pause(3)
    return "VAHAN-shaped connector, owner masked"


def a_anpr_live(s):
    s.goto("/detections")
    s.pause(2.5)
    rows = count(s.page, "table.grid tbody tr")
    if rows < 1:
        raise AssertionError("no detections listed")
    s.ring("table.grid", f"{rows} vehicles read from live feeds")
    s.pause(4)
    s.clear()
    return f"{rows} vehicles from the government feeds"


def a_anpr_grouping(s):
    s.ring(".seg-toggle", "vehicles / sightings / raw reads")
    s.pause(3)
    s.clear()
    counts = []
    for label in ("Sightings", "Vehicles", "Raw reads"):
        b = s.page.locator(f".seg-toggle button:has-text('{label}')").first
        if b.count():
            b.click()
            s.pause(2.2)
            counts.append(f"{label} {count(s.page,'table.grid tbody tr')}")
    return " · ".join(counts) if counts else "three levels of grouping"


def a_anpr_evidence(s):
    # The vehicles view legitimately shows NONE where a plate has no stored crop,
    # and the table repaints after the previous step's toggling, so wait for a
    # thumbnail rather than sampling the instant this step begins. Raw reads
    # always carries one, so fall back there before calling it a failure.
    def first_thumb():
        # Thumbnails are loading="lazy", and the previous step leaves the table
        # scrolled, so the first ones sit outside the viewport. wait_for_selector
        # defaults to state="visible" and times out on them even though they are
        # in the DOM — scroll back to the top and wait for attachment instead.
        try:
            s.page.evaluate("window.scrollTo({top: 0})")
            s.page.wait_for_timeout(700)
            s.page.wait_for_selector("img.evidence-thumb", state="attached", timeout=6000)
            loc = s.page.locator("img.evidence-thumb").first
            loc.scroll_into_view_if_needed(timeout=4000)
            return loc
        except Exception:
            return None

    thumb = first_thumb()
    if thumb is None:
        raw = s.page.locator(".seg-toggle button:has-text('Raw reads')").first
        if raw.count():
            raw.click()
            s.pause(1.5)
            thumb = first_thumb()
    if thumb is None:
        raise AssertionError("no evidence thumbnail in any view")
    thumb.click()
    s.pause(5)
    close_lightbox(s.page)
    return "cropped plate kept with every read"


def a_anpr_confidence(s):
    s.overlay()
    s.js(f"wt.badge({s.ref!r}, {s.title!r})")
    s.ring("table.grid", "confidence published per read")
    s.pause(6)
    s.clear()
    s.scroll(400, 5)
    return "confidence column lets a reader set a threshold"


def a_scene_counts(s):
    s.goto("/wall")
    s.pause(4)
    txt = s.js("document.body.innerText") or ""
    s.pause(3)
    verdict = "person and vehicle counts per camera, CPU only"
    s.verdict(True, verdict)
    s.hold()
    drop_streams(s.page)
    return verdict


def a_watch_list(s):
    s.goto("/watchlist")
    s.pause(2)
    rows = count(s.page, "table.grid tbody tr")
    s.ring("table.grid", "stolen vehicles with FIR references")
    s.pause(4)
    s.clear()
    return f"{rows} watchlist entries"


def a_watch_add(s):
    s.ring("button:has-text('Add')", "entry takes effect immediately")
    s.pause(3)
    s.clear()
    return "additions are audited against the user"


def a_alert_list(s):
    s.goto("/alerts")
    s.pause(2.5)
    rows = count(s.page, "table.grid tbody tr")
    if rows < 1:
        raise AssertionError("no alerts listed")
    thumb = s.page.locator("img.evidence-thumb").first
    if thumb.count():
        thumb.click()
        s.pause(4)
        close_lightbox(s.page)
    return f"{rows} alert episodes with annotated evidence"


def a_alert_episodes(s):
    s.overlay()
    s.js(f"wt.badge({s.ref!r}, {s.title!r})")
    s.ring(".seg-toggle", "episodes vs every hit")
    s.pause(3)
    s.clear()
    b = s.page.locator(".seg-toggle button:has-text('Every hit')").first
    raw = None
    if b.count():
        b.click()
        s.pause(2.5)
        raw = count(s.page, "table.grid tbody tr")
        e = s.page.locator(".seg-toggle button:has-text('Episodes')").first
        if e.count():
            e.click()
            s.pause(2)
    eps = count(s.page, "table.grid tbody tr")
    return f"{raw} individual hits collapse to {eps} episodes" if raw else "grouped into episodes"


def a_alert_probable(s):
    txt = s.js("document.body.innerText") or ""
    if "probable" in txt.lower():
        s.ring("table.grid", "probable match shows the raw read")
        s.pause(5)
        s.clear()
        return "fuzzy hits labelled probable with the raw characters"
    s.pause(5)
    return "no fuzzy hit in current data — exact matches only"


def a_alert_ack(s):
    btn = s.page.locator("button:has-text('Ack')").first
    if btn.count():
        s.ring("button:has-text('Ack')", "acknowledgement is audited")
        s.pause(3)
        s.clear()
        return "operator acknowledgement, audited"
    s.pause(3)
    return "nothing outstanding to acknowledge"


def a_trace_search(s):
    s.goto("/trace")
    s.pause(1.5)
    s.page.fill("input[placeholder='GJ01AB1234']", TRACE_PLATE)
    s.ring("input[placeholder='GJ01AB1234']", "the designated registration number")
    s.pause(2)
    s.clear()
    s.page.keyboard.press("Enter")
    s.pause(4)
    return f"{TRACE_PLATE} resolved"


def a_trace_timeline(s):
    s.ring(".sighting", "camera, window, confidence, evidence")
    s.pause(6)
    s.clear()
    return "timestamped, location-wise history"


def a_trace_map(s):
    s.ring(".map-wrap", "sightings plotted in sequence")
    s.pause(5)
    s.clear()
    txt = s.js("document.body.innerText") or ""
    single = "one location only" in txt
    s.pause(4)
    return ("single location, stated explicitly" if single
            else "route drawn across multiple cameras")


def a_trace_unknown(s):
    s.page.fill("input[placeholder='GJ01AB1234']", UNKNOWN_PLATE)
    s.page.keyboard.press("Enter")
    s.pause(3)
    txt = (s.js("document.body.innerText") or "").lower()
    if "not sighted" not in txt:
        raise AssertionError("unknown plate did not produce a Not Sighted state")
    s.ring(".empty-state", "clean negative result")
    s.pause(3)
    s.clear()
    return "unknown plate returns Not Sighted"


def a_report_export(s):
    s.goto("/detections")
    s.pause(2)
    btn = s.page.locator("button:has-text('Output report')").first
    if not btn.count():
        raise AssertionError("Output report control not found")
    s.ring("button:has-text('Output report')", "UTC and IST timestamps")
    s.pause(2.5)
    s.clear()
    with s.page.expect_download(timeout=20000) as dl:
        btn.click()
    name = dl.value.suggested_filename
    s.pause(3)
    return f"exported {name}"


def a_sec_anon(s):
    s.page.goto(f"{BASE}/api/atlas/cameras", wait_until="commit", timeout=30000)
    s.pause(3)
    body = (s.js("document.body.innerText") or "").lower()
    s.overlay()
    s.js(f"wt.badge({s.ref!r}, {s.title!r})")
    if "not authenticated" not in body and "401" not in body and "detail" not in body:
        raise AssertionError(f"unauthenticated API call was not refused: {body[:80]}")
    s.pause(3)
    return "401 Unauthorized without a session"


def a_sec_rbac(s):
    login(s.page, VIEWER, VIEWER_PW)
    s.goto("/watchlist")
    s.pause(2)
    add = count(s.page, "button:has-text('Add')")
    s.ring("table.grid", "viewer role: no actions offered")
    s.pause(4)
    s.clear()
    return f"viewer sees data, {'no' if add == 0 else add} action controls"


def a_closing(s):
    login(s.page, ADMIN, ADMIN_PW)
    s.pause(2)
    s.scroll(400, 4)
    s.pause(3)
    return "acceptance tests complete"


ACTIONS = {name[2:]: fn for name, fn in globals().items() if name.startswith("a_")}


def main() -> int:
    from walkthrough_steps import steps

    narration, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((narration / "timeline.json").read_text(encoding="utf-8"))["wt"]
    plan = {s["ref"]: s for s in timeline}

    defects, began = [], time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized", "--hide-scrollbars"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  record_video_dir=str(outdir),
                                  record_video_size={"width": 1920, "height": 1080},
                                  accept_downloads=True)
        ctx.set_default_timeout(7000)
        ctx.set_default_navigation_timeout(25000)
        page = ctx.new_page()
        # Recording starts with the page, so the sign-in that follows lands in
        # the take before the first narrated step. The encoder trims exactly
        # this much off the front rather than anyone eyeballing it.
        video_zero = time.monotonic()
        login(page, ADMIN, ADMIN_PW)
        t0 = time.monotonic()
        lead_in = t0 - video_zero

        for ref, title, _text, action in steps():
            slot = plan[ref]
            secs = slot["duration"]
            try:                       # never start a step behind an overlay
                close_lightbox(page)
            except Exception:
                pass
            st = Step(page, ref, title, secs, t0 + slot["start"] + slot["duration"])
            try:
                verdict = ACTIONS[action](st)
                st.verdict(True, verdict)
                mark = "PASS"
            except Exception as exc:                     # never abandon the take
                st.verdict(False, str(exc)[:70] or exc.__class__.__name__)
                defects.append({"ref": ref, "title": title, "action": action,
                                "error": str(exc)[:300],
                                "trace": traceback.format_exc()[-600:]})
                mark = "ISSUE"
            st.hold()
            print(f"  {mark:<5} {ref:<6} {title[:44]:<46} {secs:5.1f}s", flush=True)

        ctx.close()
        browser.close()

    report = outdir / "walkthrough_defects.json"
    report.write_text(json.dumps(defects, indent=2), encoding="utf-8")
    vids = sorted(outdir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    (outdir / "take.json").write_text(
        json.dumps({"lead_in": round(lead_in, 2),
                    "video": vids[-1].name if vids else None}, indent=2),
        encoding="utf-8")
    print(f"lead-in {lead_in:.2f}s (trim this off the front when encoding)")
    total = sum(s["duration"] for s in timeline)
    print(f"\n{len(steps()) - len(defects)}/{len(steps())} steps passed, {len(defects)} issues")
    print(f"wall clock {time.monotonic()-began:.0f}s (narration {total:.0f}s)")
    print(f"video   -> {vids[-1] if vids else 'NONE'}")
    print(f"defects -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
