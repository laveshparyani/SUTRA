"""Scan all local sample clips for plates and find vehicles seen on >=2 cameras.

The evaluation requires tracing a vehicle ACROSS cameras. The three sample
clips are neighbouring Ahmedabad locations recorded the same day, so a vehicle
genuinely appearing on two of them is plausible. Scans the daylight window of
each clip at ~1 frame per 2 s of video, records format-valid reads, then
intersects (with confusion-fold tolerance).

Output: data/cross_scan.json  (per-camera plate lists + cross-camera matches)
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services import anpr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# chinman bridge scanned 4000 daylight frames with 0 readable plates (camera
# angle/distance) — excluded to spend compute where plates actually resolve
CLIPS = {
    "janpath": ROOT / "CCTV Control Room" / "Camera 2 - Janpath.mp4",
    "paldi_circle": ROOT / "CCTV Control Room" / "Camera 2 - Paldi Circle.mp4",
}
# footage runs ~21:00 -> 09:00; daylight is the last ~3h (sunrise ~06:15)
DAY_START_H, DAY_END_H, STEP_S = 9.3, 11.95, 1

def scan(name: str, path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    plates: dict[str, dict] = {}
    frames = 0
    t0 = time.time()
    for sec in range(int(DAY_START_H * 3600), int(DAY_END_H * 3600), STEP_S):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * sec))
        ok, frame = cap.read()
        if not ok:
            continue
        frames += 1
        for h in anpr.analyse_frame(frame):
            norm, valid = h.normalised, h.valid_format
            # targeted hunt: anything within fuzzy range of the watchlist truck
            if anpr.plate_similarity(norm, "GJ01D7553"):
                print(f"[{name}] TRUCK CANDIDATE {norm} conf={h.ocr_conf:.2f} at {sec}s", flush=True)
            if not valid or h.ocr_conf < 0.45:
                continue
            rec = plates.setdefault(norm, {"count": 0, "best_conf": 0, "video_s": []})
            rec["count"] += 1
            rec["best_conf"] = max(rec["best_conf"], round(h.ocr_conf, 3))
            rec["video_s"].append(sec)
        if frames % 500 == 0:
            print(f"[{name}] {frames} frames, {len(plates)} plates, {time.time()-t0:.0f}s", flush=True)
    cap.release()
    print(f"[{name}] DONE: {frames} frames, {len(plates)} valid plates in {time.time()-t0:.0f}s", flush=True)
    return plates

def main() -> None:
    results = {}
    for name, path in CLIPS.items():
        results[name] = scan(name, path)
        # incremental save so a killed run still leaves usable data
        (ROOT / "data" / f"scan_{name}.json").write_text(json.dumps(results[name], indent=2))
    # cross-camera intersection with confusion-fold tolerance
    folded = defaultdict(dict)  # folded_plate -> {camera: (plate, rec)}
    for cam, plates in results.items():
        for p, rec in plates.items():
            folded[anpr.fold_plate(p)][cam] = {"plate": p, **rec}
    matches = {f: cams for f, cams in folded.items() if len(cams) >= 2}
    out = {"per_camera_counts": {c: len(p) for c, p in results.items()},
           "per_camera": results, "cross_camera_matches": matches}
    (ROOT / "data" / "cross_scan.json").write_text(json.dumps(out, indent=2))
    print(f"\nCROSS-CAMERA MATCHES: {len(matches)}", flush=True)
    for f, cams in matches.items():
        print(" ", f, "->", {c: v["plate"] for c, v in cams.items()}, flush=True)

if __name__ == "__main__":
    main()
