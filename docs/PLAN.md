# SUTRA Build Plan

**Today: 18 Aug 2026. Submission deadline: 29 Aug. Event: 1–2 Sep @ i-Hub Gujarat.**
That is **11 days** to a working platform + docs + two demo videos.

## What actually wins (from the evaluation framework)

1. **Successful test case is gate #1** — onboard the government feeds, show live viewing + analytics output. Everything else is secondary.
2. **The vehicle-tracking challenge is the money shot**: given a registration number on demo day, show the vehicle's route across cameras with timestamps on a GIS map.
3. **Watchlist correlation with real-time alerts** — we bring our own representative watchlist DB.
4. **Mock-ups are explicitly disqualified** — every screen must be backed by a running system.
5. Model 1 (registry + GIS) is **mandatory** and must be combined with another model → our Hybrid 1+3.
6. Bonus points: cross-camera tracking, edge/bandwidth optimisation, cybersecurity/RBAC/audit, health monitoring, integration-ready APIs — but only *after* mandatory items work.

## Day-by-day

### Phase A — Skeleton that ingests (Aug 18–20)
- [x] Install FFmpeg; Python 3.13 venv (torch-compatible; skipped 3.12 — 3.13 already present)
- [x] **Atlas**: camera registry schema + FastAPI CRUD + CSV bulk-import + auto-discovery from `/api/cameras` + gap-analysis endpoint (31 cameras onboarded 18 Aug)
- [x] **Bridge**: sampler workers (OpenCV/FFmpeg, auto-reconnect, health tracking) + snapshot + MJPEG relay endpoints; mp4 + mkv verified flowing (avi blocked by portal-side 5XX)
- [x] **Watch**: watchlist CRUD + alerts API + WebSocket push (matcher lands in Phase B)
- [ ] Docker Desktop + PostgreSQL/PostGIS + Redis (SQLite in use for now — swap when needed for demo credibility)
- [ ] Smoke test: ALL live cameras sampling simultaneously (bandwidth/CPU check)

### Phase B — AI pipeline (Aug 20–24)
- [x] **Insight**: plate detection (YOLOv9-t 640 ONNX) + OCR (cct-s-v2 ONNX) on CPU — 30-40 ms/frame warm; queue + worker pool decoupled from ingest with back-pressure
- [x] Plate normalisation (Indian format structure-aware O↔0/I↔1 correction) + fuzzy watchlist matching (confusion-fold + edit-distance 1 → "probable" alerts)
- [x] Detections persisted with evidence crops; annotated full-frame saved on alert
- [x] **Watch** matcher wired: detection → watchlist match → alert row → WebSocket push (verified E2E 18 Aug on Paldi file camera: exact match, alert received on WS with evidence links)
- [x] Route reconstruction endpoint `/api/insight/route/{plate}` (sightings grouped per camera, time-ordered)
- [ ] **Accuracy work (the hard part)**: temporal voting — aggregate multiple reads of the same vehicle (bbox proximity across consecutive frames) and majority-vote per character; wide-angle cams read partially (~0.4-0.7 conf, 50-90 px plates)
- [x] State-code repair: invalid leading codes fixed via look-alike substitution against the official state-code list (GI01D7553 → GJ01D7553) — added after temporal voting surfaced an I/J confusion the char vote can't resolve
- [ ] Two-line plate handling (trucks/autos): OCR concatenates lines with order errors
- [ ] Ground-truth pass: manually verify 20-30 plates from sample videos, measure read accuracy
- [ ] Test close-range live cams (Adalaj toll cam 12 is HEVC — warmup frame skip added) for best demo cameras

### Phase C — Command UI (Aug 23–27, overlaps B)
- [x] React app (`frontend/` — Vite, Leaflet, dark control-room theme; dev: `npm run dev`, proxies to :8000)
- [x] GIS map (dark CARTO tiles, health-coloured camera markers, popups)
- [x] Video wall (MJPEG grid via Bridge relay, dept filter, live badges)
- [x] Vehicle trace: plate → sighting timeline + route polyline with sequence markers ← **demo-day feature, verified**
- [x] Alert centre: live WebSocket toasts + alert log with evidence thumbnails + ack workflow
- [x] Registry page: search/filter, discover button, per-camera monitor toggle, health/fps columns
- [x] Watchlist manager (add/deactivate, reason/FIR/priority)
- [x] Login + RBAC (JWT; admin / operator dept-scoped / viewer; audit trail uses real usernames; UI login page + role-gated buttons; verified: 401/403/dept-scoping all correct)
- [x] Gap-analysis view (Atlas page: district coverage table + KPIs)
- [x] Detections browser page (filter by plate/camera, evidence lightbox, votes column, trace deep-link)
- [x] **Adaptive ingest scheduler** (`services/scheduler.py`) — concurrency budget (8), dwell-based rotation (90s) with least-recently-served fairness (fixed slot-starvation bug: running cams now ranked by slot start, not just stop time), staggered connects (1.5s), pin API (★ in Registry), **alert boost**: watchlist hit → camera + 3 nearest neighbours become residents for 5 min ("tighten the net"). Verified: budget respected, rotation hands slots 1-8 → 9-16 after dwell, pin holds a slot. Registry UI shows slots/queue/boost chip.
- [ ] Polish pass: loading states, error toasts (low priority)

### Bug sweep — full UI audit in Chrome (19 Aug)
Found by driving every page manually; all fixed and re-verified.

1. **CRITICAL — plate corruption broke vehicle trace.** `normalise_plate`'s structure-forcing
   ran *after* state-code repair and could manufacture an impossible code (`6I…` → `GI01D7553`),
   which the shape-only regex happily accepted. Searching the true plate `GJ01D7553` returned
   NOT SIGHTED while 52 detections of that vehicle sat in the DB under the corrupt spelling —
   exactly the evaluation-day failure mode. Fix: `is_valid_indian` now verifies the state code
   against the real code list, and repair re-runs on the rebuilt candidate.
2. **Junk reads stored as evidence** (`113117`, `417T397`). Only format-valid plates are
   persisted now; the rest are counted in `reads_rejected_invalid_format`.
3. **Alert spam** — 19 identical alerts for one parked vehicle (60 s cooldown). Now 900 s.
4. **Video wall opened 25 MJPEG connections**, saturating the browser's ~6-per-host limit,
   which starved every API call and froze the renderer. Now streams only cameras actually
   delivering frames, capped at 6.
5. **False LIVE badges** — tiles showed LIVE over black video. Badge now derives from real
   frame age; tiles read NO SIGNAL / CONNECTING / AWAITING SLOT honestly.
6. **"Last frame" lied** — it was stamped on socket connect. Now only advances on a real
   decoded frame; a connected-but-silent source reports `connecting`, not `ok`.
7. **`window.fetch` patch stacked a wrapper per hot reload** — made idempotent.

`scripts/repair_detections.py` re-normalises historical rows against current logic
(repaired 55, dropped 122 junk reads).

Demo credentials (also for judges' submission): admin/SutraAdmin@26 · operator_police/Operator@26 · viewer/Viewer@26

### Phase D — Docs + videos + submission (Aug 26–29)
- [ ] Solution Presentation (PPT/PDF): model justification (Hybrid 1+3), architecture, workflow, impact
- [ ] HLD document: architecture diagrams, integration approach, analytics approach, alert workflow, security, **80k-camera scalability plan** (edge nodes per district, Kafka bus, tiered storage, GPU sizing, bandwidth math)
- [ ] Own-feed demo video (2–3 min): onboarding → detection → watchlist match → alert
- [ ] Government-feed demo video + **output report** (detected plates with timestamps)
- [ ] Host the platform + test credentials; push code to GitHub; submit links

## Open decisions (owner: Lavesh)

1. **Category**: Category 1 (DPIIT startup / students) vs Category 2 (companies). Protego → which entity registers?
2. **Demo-day compute**: CPU/OpenVINO only, or rent a cloud GPU (T4/A10) for the event? Recommend budgeting a cloud GPU for the finale; CPU pipeline as the "edge/low-bandwidth" bonus story.
3. **Team**: solo or team? Affects how much Phase B/C can parallelise.
