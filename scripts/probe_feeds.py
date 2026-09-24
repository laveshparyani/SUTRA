"""Probe the Sentinel Camera Grid with the edge node's portal credentials.

Reads SUTRA_PORTAL_EMAIL / SUTRA_PORTAL_PASSWORD from backend/.env (via the
app settings), lists the catalogue and pulls a few frames from one camera
over RTSP, printing only redacted URLs. Usage:

    python scripts/probe_feeds.py            # catalogue + cam04
    python scripts/probe_feeds.py cam17 5    # camera id, frames to pull
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import discovery, portal  # noqa: E402
from app.services.ffreader import FFmpegFrameReader  # noqa: E402


def main() -> None:
    cam = sys.argv[1] if len(sys.argv) > 1 else "cam04"
    want = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if not portal.configured():
        raise SystemExit("set SUTRA_PORTAL_EMAIL / SUTRA_PORTAL_PASSWORD in backend/.env first")

    cams = asyncio.run(discovery.fetch_portal_cameras())
    print(f"catalogue: {len(cams)} cameras")
    for c in cams:
        print(f"  {c['id']:6s} {c.get('name', '')}")

    meta = discovery._metadata({"id": cam, "name": cam})
    url = portal.authenticate_url(meta["source_url"])
    print(f"\npulling {want} frames from {portal.redact_url(url)} ...")
    reader = FFmpegFrameReader(url, width=640, height=360, fps=1.0, is_rtsp=True, timeout_s=30)
    t0 = time.time()
    if not reader.start():
        raise SystemExit("ffmpeg did not start")
    got = 0
    while got < want and time.time() - t0 < 90:
        frame = reader.read()
        if frame is None:
            break
        got += 1
        print(f"  frame {got} at {time.time() - t0:.1f}s shape={frame.shape}")
    reader.stop()
    print(f"done: {got}/{want} frames; last_error={reader.last_error!r}")


if __name__ == "__main__":
    main()
