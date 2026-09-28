"""Caption the ten submission screenshots (run after capture_screenshots.py).

    python scripts/capture_screenshots.py <raw_dir>
    python scripts/annotate_submission_screenshots.py <raw_dir> submission/screenshots
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from annotate_screenshot import annotate  # noqa: E402

SHOTS = [
 ("01_login", "01_sign_in_role_based_access", "1 of 10 · Sign in", "Sign in — role-based access",
  "Every session is authenticated with a JWT and a department-scoped role: admin, operator or read-only viewer. Access rules are enforced on the server, not only in the UI.|The sandbox accounts shown are the ones supplied to the judges.",
  [(610, 318, 990, 682)]),
 ("02_state_overview", "02_state_overview_dashboard", "2 of 10 · State overview", "State overview — measured, not sampled",
  "Every figure is computed from cameras SUTRA has actually processed: plates read, distinct vehicles, cameras onboarded, feeds healthy right now, mean OCR quality.|The read-quality distribution is published on purpose, so an operator can apply their own confidence threshold instead of trusting every read equally.",
  [(230, 168, 1580, 258), (571, 569, 897, 773)]),
 ("03_camera_registry", "03_camera_registry_and_ingest_scheduler", "3 of 10 · Registry", "Camera registry — the Model 1 foundation",
  "One row per onboarded camera: department, district, source protocol, an honest health state and the live ingest rate. Export, Discover and Monitor All are one click each.|The chip beside the title is the adaptive scheduler: six live slots in use, 24 cameras queued to rotate through them. The star pins a camera into a slot.",
  [(375, 86, 520, 110), (1250, 84, 1568, 112), (1120, 160, 1460, 996)]),
 ("04_atlas_gis_and_gap_analysis", "04_atlas_gis_coverage_and_gap_analysis", "4 of 10 · Atlas", "Atlas — GIS coverage map and gap analysis",
  "Every registered camera on a layered map, filterable by department, camera type and status, with a coverage radius coloured by live health.|Below the map, district-wise gap analysis flags thin coverage and ageing cameras, so new budget can be pointed at measured gaps rather than guesses.",
  [(245, 122, 950, 158), (230, 563, 1580, 655), (1330, 718, 1460, 996)]),
 ("05_video_wall", "05_live_video_wall_federated_feeds", "5 of 10 · Video wall", "Live video wall — federated government feeds",
  "Live tiles from the challenge portal's cameras over authenticated RTSP, each with person and vehicle counts from the scene model in its footer.|Tiles that are waiting for an ingest slot say so. SUTRA never presents a frozen frame as live.",
  [(440, 155, 700, 177), (230, 493, 672, 772), (230, 790, 1580, 996)]),
 ("06_detections_browser", "06_anpr_detections_one_row_per_vehicle", "6 of 10 · Detections", "ANPR detections — one row per vehicle",
  "95 vehicles from 114 reads: how many times and on how many cameras each plate was seen, its active period, and the best read with its OCR confidence.|Every row carries the evidence crop it was read from and a one-click trace.",
  [(1510, 160, 1580, 220), (1330, 270, 1420, 996), (1490, 270, 1545, 996)]),
 ("07_detection_evidence", "07_detection_evidence_crop", "7 of 10 · Evidence", "Evidence behind every read",
  "Clicking a row opens the plate crop the read was made from, so any result can be checked by a human before it is acted on.|Confidence is shown, not hidden: a 0.82 read and a 1.00 read are not the same fact.",
  [(720, 466, 880, 532)]),
 ("08_watchlist", "08_watchlist_management", "8 of 10 · Watchlist", "Watchlist — representative stolen-vehicle records",
  "Investigators register plates with a reason, FIR reference and priority. Every live read is cross-checked against this list, exactly and fuzzily; a fuzzy hit is labelled probable and shows the characters actually read.|Variants of a battered plate can be registered under the same FIR.",
  [(245, 127, 995, 163), (230, 236, 1580, 442)]),
 ("09_alert_centre", "09_alert_centre_episodes", "9 of 10 · Alerts", "Alert centre — episodes, not spam",
  "A watchlisted vehicle standing in one camera's view would re-trigger on every cooldown window, so SUTRA groups hits into episodes: one row per vehicle per camera with evidence, FIR, location, time window and an acknowledgement workflow.",
  [(1240, 82, 1570, 110), (230, 250, 1580, 300)]),
 ("10_vehicle_trace", "10_vehicle_trace_and_vahan_enrichment", "10 of 10 · Trace", "Vehicle trace — movement history on the GIS map",
  "Type a registration number: SUTRA lists every sighting with its time window, camera and evidence, enriches it from a VAHAN-shaped connector with the owner's name masked, and draws the route between cameras.|When a vehicle has been seen at one location only, it says so plainly rather than drawing a misleading path.",
  [(245, 208, 595, 385), (245, 517, 595, 600), (1080, 495, 1125, 538)]),
]


def main() -> None:
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    for src, name, step, title, text, boxes in SHOTS:
        annotate(raw / f"{src}.png", out / f"{name}.png", title, text, boxes, step)
        print("wrote", name)


if __name__ == "__main__":
    main()
