"""End-to-end fixtures: a real server, a throwaway database, a real browser.

These tests drive the built application the way an operator would, which is the
gap the API-level suite cannot cover: every API check passed at one point while
the detections view was crashing to a blank page, because nothing was looking
at the page.

The backend mounts `frontend/dist` and serves the SPA itself, so one process on
one port serves both the API and the UI - closer to how the hosted tier runs
than a separate dev server would be.

Isolation: its own port, its own temp data directory, its own SQLite file and
its own seed passwords. Nothing here touches a developer's working instance on
8010 or the data under ./data.

    python -m pytest e2e -q          (after: npm run build --prefix frontend)
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DIST = ROOT / "frontend" / "dist"

PORT = 8020                     # deliberately not 8010: never collide with a dev instance
BASE = f"http://127.0.0.1:{PORT}"

ADMIN = ("admin", "E2eAdmin@26")
OPERATOR = ("operator_police", "E2eOperator@26")
VIEWER = ("viewer", "E2eViewer@26")
SYNC_KEY = "e2e-local-sync-key"


def _free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait_for_health(proc, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"server did not become healthy within {timeout}s")


@pytest.fixture(scope="session")
def server():
    """A real uvicorn process against a throwaway database."""
    if not DIST.is_dir():
        pytest.skip("frontend/dist missing - run: npm run build --prefix frontend")

    # These tests exercise the built bundle, not the sources. A stale dist
    # silently tests yesterday's code: during development of this suite a
    # regression test "passed" against a build that still contained the bug it
    # was written to catch. Fail loudly rather than report a misleading green.
    # Only meaningful locally: in CI the bundle arrives as a downloaded
    # artifact whose timestamps say nothing about the source it was built from.
    built = (DIST / "index.html").stat().st_mtime
    newest_src = max((f.stat().st_mtime for f in (ROOT / "frontend" / "src").rglob("*")
                      if f.is_file()), default=0)
    if newest_src > built and not os.environ.get("CI"):
        pytest.fail("frontend/dist is older than frontend/src - "
                    "run: npm run build --prefix frontend", pytrace=False)
    if not _free(PORT):
        pytest.skip(f"port {PORT} is already in use")

    tmp = tempfile.mkdtemp(prefix="sutra_e2e_")
    env = {
        **os.environ,
        "SUTRA_ROLE": "central",
        "SUTRA_DATA_DIR": tmp,
        "SUTRA_DB_URL": f"sqlite:///{tmp}/e2e.db",
        # no camera workers, no model loading: these tests are about the
        # interface, and ingest would make them slow and non-deterministic
        "SUTRA_INSIGHT_ENABLED": "false",
        "SUTRA_SCENE_ENABLED": "false",
        "SUTRA_INGEST_BUDGET": "0",
        # CRITICAL: cut every outbound path. backend/.env is read by pydantic
        # whatever we pass here, so without these the test server inherits the
        # real central URL and sync key and starts the syncer - which pushes
        # every camera in its database, including the ones these tests create,
        # straight into the live hosted tier. The first run of this suite did
        # exactly that. Blanking them stops the syncer from starting at all.
        "SUTRA_CENTRAL_URL": "",
        # a local key so the seeding fixture can use /api/sync/push. The
        # central tier never syncs outward, so this opens no path off the box.
        "SUTRA_SYNC_API_KEY": SYNC_KEY,
        "SUTRA_PORTAL_EMAIL": "",
        "SUTRA_PORTAL_PASSWORD": "",
        # never run the suite on the published sandbox passwords
        "SUTRA_SEED_ADMIN_PW": ADMIN[1],
        "SUTRA_SEED_OPERATOR_PW": OPERATOR[1],
        "SUTRA_SEED_VIEWER_PW": VIEWER[1],
    }
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)

    # Log to a file, never to a pipe. An unread PIPE fills its buffer after a
    # few dozen KB of uvicorn request logging and the server then blocks on
    # write - the first handful of tests pass and every later one times out
    # against a process that is alive but frozen.
    log_path = Path(tmp) / "server.log"
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [str(py), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT, text=True,
    )
    try:
        try:
            _wait_for_health(proc)
        except Exception:
            log.flush()
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError("e2e server failed to start:\n" + tail) from None
        yield BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def browser(server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    """A fresh context per test, so no test inherits another's session."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 950})
    ctx.set_default_timeout(15000)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.uncaught_errors = errors
    yield pg
    ctx.close()


def api_token(base: str, username: str, password: str) -> str:
    """Log in over the API - used to seed data without driving the UI."""
    import json
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["token"]


def sign_in(page, base: str, username: str, password: str) -> None:
    """Sign in through the interface and wait for the application shell.

    Waits for the shell rather than a fixed interval: a slow sign-in once let a
    recording proceed against a login form still reading AUTHENTICATING.
    """
    page.goto(f"{base}/login", wait_until="commit")
    page.wait_for_selector("input[placeholder='username']")
    page.fill("input[placeholder='username']", username)
    page.fill("input[placeholder='password']", password)
    page.click("button:has-text('Sign In')")
    page.wait_for_selector("nav a[href='/']", state="visible", timeout=30000)


@pytest.fixture(scope="session")
def seeded(server):
    """Realistic reference data: two cameras, plate reads on both, one alert.

    Seeded through /api/sync/push, which is the same contract an edge node
    uses, so the rows land exactly as production rows do - including the
    vehicle/sighting/raw-read groupings the detections page derives from them.

    This matters more than it looks. An earlier version of this fixture
    created only a camera, so every detections view rendered empty and the
    regression test below passed even with the crash deliberately put back.
    A test that cannot fail is worse than no test.

    One plate is deliberately read on both cameras, so vehicle rows carry a
    multi-camera `cameras` array and Trace has a route to draw.
    """
    import json
    from datetime import datetime, timedelta, timezone

    base_t = datetime.now(timezone.utc) - timedelta(hours=2)

    def at(minutes):
        return (base_t + timedelta(minutes=minutes)).isoformat()

    cameras = [
        {"external_id": "e2e-cam-1", "name": "E2E Paldi Circle", "location": "Paldi Circle",
         "district": "Ahmedabad", "department": "Police", "lat": 23.01, "lon": 72.56,
         "camera_type": "fixed", "ownership": "government", "health": "ok"},
        {"external_id": "e2e-cam-2", "name": "E2E Janpath Junction", "location": "Janpath",
         "district": "Ahmedabad", "department": "Municipal", "lat": 23.04, "lon": 72.58,
         "camera_type": "ptz", "ownership": "government", "health": "ok"},
    ]

    detections = []
    # one vehicle seen on both cameras - gives Trace a route and gives vehicle
    # rows a cameras array with more than one entry
    for i, (cam, minute) in enumerate([("e2e-cam-1", 0), ("e2e-cam-1", 3), ("e2e-cam-2", 21)]):
        detections.append({"camera_external_id": cam, "ts": at(minute),
                           "plate_text": "GJ01AB1234", "plate_conf": 0.97 - i * 0.02,
                           "det_conf": 0.9, "track_id": "votes:3"})
    # a handful of other vehicles so the groupings are not degenerate
    for i, plate in enumerate(["GJ05CD5678", "GJ18EF9012", "GJ27GH3456", "GJ01JK7890"]):
        detections.append({"camera_external_id": "e2e-cam-1" if i % 2 else "e2e-cam-2",
                           "ts": at(30 + i * 4), "plate_text": plate,
                           "plate_conf": 0.88 + i * 0.02, "det_conf": 0.9})

    alerts = [{"plate": "GJ01AB1234", "camera_external_id": "e2e-cam-1", "ts": at(3),
               "severity": "high", "reason": "stolen", "fir_ref": "FIR/E2E/1",
               "status": "new", "match_type": "exact"}]

    req = urllib.request.Request(
        f"{server}/api/sync/push",
        data=json.dumps({"node": "e2e", "cameras": cameras,
                         "detections": detections, "alerts": alerts}).encode(),
        headers={"Content-Type": "application/json", "X-Sync-Key": SYNC_KEY},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())

    token = api_token(server, *ADMIN)
    return {"token": token, "pushed": result,
            "multi_camera_plate": "GJ01AB1234", "cameras": 2}
