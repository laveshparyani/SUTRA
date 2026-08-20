"""Probe the hackathon live-feed portal: list cameras, optionally grab a frame.

Usage:
    python scripts/probe_feeds.py               # list cameras, save cameras.json
    python scripts/probe_feeds.py --grab 1      # also save a frame from camera 1 (needs opencv-python)
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://live.sentinelgujarat.in"
OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_cameras() -> list[dict]:
    with urllib.request.urlopen(f"{BASE}/api/cameras", timeout=15) as r:
        payload = json.load(r)
    return payload.get("cameras", payload if isinstance(payload, list) else [])


def grab_frame(camera_id: str, out_path: Path) -> bool:
    try:
        import cv2
    except ImportError:
        print("opencv-python not installed — run: pip install opencv-python", file=sys.stderr)
        return False
    cap = cv2.VideoCapture(f"{BASE}/stream/{camera_id}")
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"could not read a frame from camera {camera_id}", file=sys.stderr)
        return False
    cv2.imwrite(str(out_path), frame)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grab", metavar="CAMERA_ID", help="save one frame from this camera id")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    cameras = fetch_cameras()
    (OUT_DIR / "cameras.json").write_text(json.dumps(cameras, indent=2))
    print(f"{len(cameras)} cameras — saved to {OUT_DIR / 'cameras.json'}\n")
    for cam in cameras:
        print(f"  [{cam['id']:>3}] {cam['location']:<55} {cam['codec']}/{cam['container']} {cam['status']}")

    if args.grab:
        out = OUT_DIR / f"camera_{args.grab}_frame.jpg"
        if grab_frame(args.grab, out):
            print(f"\nframe saved: {out}")


if __name__ == "__main__":
    main()
