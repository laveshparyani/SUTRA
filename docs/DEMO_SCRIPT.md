# Demo Video Shot Scripts

Two videos are required. Record with OBS Studio (free) or Windows Game Bar
(Win+Alt+R), 1080p, with the browser at full screen. Speak plainly; judges
explicitly reject mock-ups, so let the running system carry the video. Keep
own-feed ≤3:00.

**Pre-flight (both videos):** backend + frontend running, portal healthy
(Registry shows green cameras), mediamtx + truck publisher running, logged in
as `admin`. Practice the click path once before recording.

---

## Video 1 — Own-Feed Demonstration (2–3 min)

| # | Time | Screen | Say |
|---|------|--------|-----|
| 1 | 0:00 | Login page → sign in | "SUTRA — Statewide Unified Tracking, Registry and Analytics. A hybrid Model-1-plus-Model-3 platform. Everything you'll see is live." |
| 2 | 0:15 | Overview: KPIs + Gujarat map | "The Atlas registry has onboarded cameras across departments — government feeds, a recorded file source, and an RTSP relay — all federated into one platform." |
| 3 | 0:35 | Registry page; point at `slots x/8 · queue` chip; hover ★ | "Live connections are time-multiplexed under a concurrency budget by an adaptive scheduler; pinned cameras hold slots. Health is reported honestly per camera." |
| 4 | 0:55 | Video Wall: live tiles incl. demo cam; point at `1p · 8v` scene counts | "Beyond ANPR, every feed gets live person and vehicle counts from an object-detection sidecar — all CPU, no GPUs anywhere in this demo." |
| 5 | 1:15 | Watchlist page: show GJ01D7553 stolen entry + variant | "A representative watchlist — stolen vehicles with FIR references. Investigators can register OCR variants of a battered plate under one FIR." |
| 6 | 1:30 | Wait on Wall/Overview for the alert toast (fires ~every 15 min; time the take, or trigger by re-adding watchlist entry after deleting) | "There — continuous cross-referencing just matched a watchlisted vehicle on a live feed: real-time alert with the camera, location and evidence." |
| 7 | 1:50 | Alerts page: click evidence thumbnail (annotated frame), point at VAHAN details | "Each alert carries the evidence frame and is enriched from a VAHAN-shaped connector — make, model, owner, insurance status. Production integration is a connector swap." |
| 8 | 2:15 | Trace page: type GJ01D7553 → sightings + map pin + VAHAN panel | "The evaluation scenario: given a registration number, SUTRA reconstructs the vehicle's timestamped movement history on the GIS map." |
| 9 | 2:40 | Detections page: click ⬇ Output Report; show the CSV | "And every detection exports to a timestamped output report. All of it open-source, running on one machine." |

## Video 2 — Government-Feed Demonstration

| # | Time | Screen | Say |
|---|------|--------|-----|
| 1 | 0:00 | Registry: filter/scroll to portal cameras (sentinel-*); click ⟳ Discover | "SUTRA onboards the Government-provided cameras automatically from the hackathon portal's API — thirty-plus heterogeneous feeds: MP4, MKV, AVI containers across five departments." |
| 2 | 0:30 | Video Wall: live government tiles (pick a moment when several flow) | "Live viewing of the Government feeds, multiplexed under the concurrency budget the portal can sustain." |
| 3 | 1:00 | Detections page filtered to Camera 7 | "AI analytics on the Government feed: automatic number-plate recognition on Camera 7, Gir Somnath — reads up to 98 percent confidence, each with an evidence crop." |
| 4 | 1:30 | Click a cam-7 evidence thumbnail (lightbox) | "Every read is evidenced." |
| 5 | 1:45 | ⬇ Output Report with camera 7 filter; open CSV | "The required output report: detected plates with UTC and IST timestamps, straight from the Government feed." |
| 6 | 2:10 | Atlas page: district coverage + audit trail | "Registry, coverage analysis, and a full metadata audit trail complete the Model-1 foundation." |

Submit alongside: `submission/sutra_gov_feed_output_report_cam7.csv` + evidence_cam7/ snapshots.

**Timing tip for shot 6 (video 1):** delete + re-add the GJ01O7512 watchlist entry
right before recording — the RTSP camera's next truck pass (≤60 s) fires a fresh alert.
