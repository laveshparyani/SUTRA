"""Replay this edge node's alerts to the central tier.

The sync cursor only moves forward, so rows that synced before a payload field
existed keep whatever the central column defaulted to. That is how every alert
on the hosted tier came to read match_type=exact, including hits the edge had
classified as probable — the central tier cannot recompute the class, because
the payload carries the watchlist plate rather than the raw OCR read.

Rewinding only the alert half of the cursor re-pushes alerts (tens of rows)
without replaying the detection history (thousands). The central intake now
updates an existing alert instead of skipping it, so the replay corrects rows
in place rather than duplicating them.

    python scripts/resync_alerts.py            # show the cursor
    python scripts/resync_alerts.py --rewind   # rewind alerts, keep detections
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    """Locate the runtime data directory without importing the application.

    This only rewrites a two-integer text file, so it should not require the
    backend's dependency stack to be importable — running it with the system
    interpreter instead of the venv would otherwise fail on pydantic_settings
    before it read anything. Resolution order mirrors app.config: an explicit
    environment variable, then backend/.env, then the repo-root default.
    """
    env = os.environ.get("SUTRA_DATA_DIR")
    if env:
        return Path(env)
    dotenv = REPO / "backend" / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "SUTRA_DATA_DIR" and value.strip():
                return Path(value.strip())
    return REPO / "data"


def main() -> int:
    cursor = data_dir() / ".sync_cursor"
    if not cursor.exists():
        print(f"no cursor at {cursor} — the syncer will start from the beginning already")
        return 0

    try:
        det_id, alert_id = (int(x) for x in cursor.read_text().split())
    except ValueError:
        print(f"cursor at {cursor} is unreadable; delete it to force a full resync")
        return 1

    print(f"cursor: last_detection_id={det_id}  last_alert_id={alert_id}")
    if "--rewind" not in sys.argv:
        print("dry run — pass --rewind to replay alerts from the start")
        return 0

    cursor.write_text(f"{det_id} 0")
    print(f"rewound to: last_detection_id={det_id}  last_alert_id=0")
    print("restart the edge node; alerts replay on the next tick and the centre updates in place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
