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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import settings  # noqa: E402


def main() -> int:
    cursor = settings.data_dir / ".sync_cursor"
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
