# SUTRA — Acceptance Test Plan

Every requirement from the official hackathon statement, in order, with the
exact steps to prove it. Work top to bottom: read the requirement, run the
steps, tick the box if it behaves as described, or write the failure in the
**Defects** table at the end.

A step that says *"should"* is the pass condition. If what you see differs,
that is a defect even if nothing crashed.

| | |
|---|---|
| Platform (local) | http://localhost:5173 — `admin` / `SutraAdmin@26` |
| Platform (hosted) | https://sutra-central.onrender.com — `admin` / `Sutra#Gandhinagar26` |
| API (local) | http://127.0.0.1:8010 |
| Other roles | `operator_police` / `Operator@26` · `viewer` / `Viewer@26` |

---

## 0. Pre-flight

- [ ] **0.1 — Servers running.** Start `sutra-api` and `sutra-command` from `.claude/launch.json`.
  1. Open http://127.0.0.1:8010/api/health → should return `{"service":"sutra","status":"ok","role":"edge",...}`.
  2. Open http://localhost:5173 → should show the SUTRA login page, not an error.

- [ ] **0.2 — Backend test suite.** `cd backend && ..\.venv\Scripts\python -m pytest -q`
  - Should end **174 passed, 1 skipped**. Any failure is a defect.

- [ ] **0.3 — Sign in.** Sign in as `admin`.
  - Should land on **Overview**. The header should show your role and a live clock.

---

## 1. Mandatory — Model 1: Centralised Registry & GIS

> *"Bulk import, manual entry, and API-based camera onboarding. Interactive GIS
> map with department, camera type, status and coverage layers. Camera health
> and maintenance-status monitoring. Gap-analysis reports. Role-based search,
> filtering, export, and metadata audit trails."*

- [ ] **1.1 — Registry holds real camera metadata.** Go to **Registry**.
  1. The table should list ~38 cameras.
  2. Each row should show department, district, source type and health — not blanks.
  3. Confirm a mix of source types exists (`rtsp` for portal cameras, `file` for demo clips).

- [ ] **1.2 — API-based onboarding (auto-discovery).** On **Registry**, click **⟳ Discover**.
  1. Should complete and report cameras created/updated (30 from the portal).
  2. The table should still show the same cameras — updated in place, not duplicated.
  3. **Note:** after Discover, the API must be restarted before new feeds stream. Workers keep the URL they started with.

- [ ] **1.3 — Search and filtering.** On **Registry**, use the department filter and the search box.
  1. Filtering by a department should narrow the list to that department only.
  2. Typing part of a camera name or location should narrow the list live.

- [ ] **1.4 — CSV export.** On **Registry**, click **⬇ Export**.
  1. A CSV should download.
  2. Open it — should contain one row per camera with external_id, name, location, department, district, lat, lon, camera type, ownership, source type, retention and health.

- [ ] **1.5 — GIS map with layers.** Go to **Atlas**.
  1. A map of Gujarat should render with camera markers (not a blank grey panel).
  2. Change **All departments**, **All camera types** and **Any status** — the marker count in the panel header should change accordingly.
  3. Toggle **coverage radius** — shaded circles should appear around cameras, coloured by health.
  4. Use the **Dark map / Satellite** switch bottom-right — the basemap should change and markers stay in place.

- [ ] **1.6 — Camera health monitoring.** Go to **Video Wall**.
  1. Tiles should show distinct states: **Live**, **Stalled**, **Connecting**, **Unreachable**, **Queued**, **Not pooled**.
  2. A tile that is not streaming should say *why* in plain words — never a black rectangle labelled Live.
  3. An unreachable camera should give a readable cause (e.g. "connection timed out"), not a raw error number.

- [ ] **1.7 — Gap analysis.** On **Atlas**, scroll to **District Coverage & Gap Analysis**.
  1. A table should list districts with camera counts, unhealthy counts, **Ageing (5y+)** and an assessment.
  2. At least one district should be flagged thin coverage or degraded — the analysis should discriminate, not mark everything fine.

- [ ] **1.8 — Metadata audit trail.** On **Atlas**, scroll to the audit section.
  1. Should list recent actions with time, actor and detail.
  2. Your **⟳ Discover** and **⬇ Export** from steps 1.2/1.4 should appear, attributed to `admin`.

- [ ] **1.9 — Role-based access.** Sign out, sign in as `viewer` / `Viewer@26`.
  1. Read-only pages should still work.
  2. Action buttons (watchlist add, alert acknowledge, monitor toggles) should be **absent or disabled**.
  3. Sign in as `operator_police` / `Operator@26` — should see Police-department data, scoped server-side.
  4. Sign back in as `admin` before continuing.

---

## 2. Mandatory — Model 3: VMS Federation & Middleware

> *"Adapter/plugin architecture for multiple VMS vendors. Metadata exchange bus.
> Cross-system event correlation. Unified workflow and alert dashboard.
> Extensible connector framework."*

- [ ] **2.1 — Heterogeneous sources in one platform.** On **Registry**, look at the source-type column.
  1. Should show at least two different protocols in use simultaneously (`rtsp` portal cameras and `file` demo clips).
  2. Both kinds should be able to reach **Live** on the Video Wall.

- [ ] **2.2 — Credentials are never stored with the camera.** On **Registry**, open a portal camera's details; also re-open the exported CSV from 1.4.
  1. The stored source URL should be `rtsp://103.250.160.189:8554/stream/camNN` — **with no email or password in it**.
  2. The CSV should contain no credentials anywhere. *(Credentials are injected only at connection time.)*

- [ ] **2.3 — Federation: edge → central.** Open http://127.0.0.1:8010/api/system (signed in).
  1. `edge_sync` should show the central URL and a recent `last_success_at`.
  2. Now open the **hosted** platform and sign in — its Detections should contain rows the edge produced. *Metadata flows up; video does not.*

- [ ] **2.4 — Government-database connector.** Go to **Trace**, search a plate that has detections.
  1. A vehicle-details panel should appear with source, make, model, class, RTO and insurance status.
  2. The owner name should be **masked**, not fully printed.

---

## 3. Mandatory — AI-powered video analytics

> *"ANPR, object detection, person and vehicle tracking, and other intelligent
> analytics proposed by the team."*

- [ ] **3.1 — ANPR is reading live feeds.** Go to **Detections**.
  1. Rows should exist with today's timestamps from government cameras (not only demo clips).
  2. Each row should carry a plate, a confidence and a camera.

- [ ] **3.2 — Three levels of grouping.** On **Detections**, use the **Vehicles / Sightings / Raw reads** toggle.
  1. **Vehicles** should show one row per registration number — no duplicates of the same plate.
  2. **Sightings** should show more rows than Vehicles; **Raw reads** more again.
  3. Each level should explain itself in the blurb above the table.

- [ ] **3.3 — Evidence for every read.** On **Detections**, click an evidence thumbnail.
  1. A lightbox should open showing the actual cropped plate image.
  2. The characters in the image should match the plate in the row **for high-confidence reads**.
  3. *Known and documented:* reads at ≤0.86 confidence can have character errors. That is expected, not a defect — see `submission/README.md`.

- [ ] **3.4 — Scene analytics beyond ANPR.** Go to **Video Wall**.
  1. Live tiles should show person/vehicle counts (e.g. `2p · 8v`).
  2. Counts should change over time on a moving feed.

- [ ] **3.5 — Indian-plate normalisation.** On **Detections**, scan the plate column.
  1. Plates should be well-formed Indian registrations (2 state letters + RTO digits + series + 4 digits).
  2. Junk strings like `113117` or `K02TCJ` should **not** appear — they are rejected before storage.

---

## 4. Mandatory — Watchlist correlation & real-time alerts

> *"Continuous cross-referencing between live CCTV feeds and representative
> watchlist records, with automated real-time alert generation upon detecting a
> match."*

- [ ] **4.1 — Watchlist database exists.** Go to **Watchlist**.
  1. Should list stolen-vehicle entries with FIR references and priorities.

- [ ] **4.2 — Add an entry.** On **Watchlist**, use **Add to Watchlist** with a plate you saw in Detections.
  1. The entry should appear immediately in the list.
  2. Check **Atlas** audit — the addition should be recorded against `admin`.

- [ ] **4.3 — Automated alert on match.** Go to **Alerts**.
  1. Alerts should exist, each with plate, camera, location, time and severity.
  2. Click an evidence thumbnail → should show the **annotated** frame with the plate boxed.

- [ ] **4.4 — Alerts are grouped, not spammed.** On **Alerts**, use the **Episodes / Every hit** toggle.
  1. **Episodes** should show one row per vehicle per camera with a hit count (e.g. `84×`).
  2. **Every hit** should show many more rows — the raw audit trail.
  3. Both views should name the **same vehicle** for the same alert.

- [ ] **4.5 — Fuzzy matches are labelled honestly.** On **Alerts**, look for a `⚠ probable match` row.
  1. It should say **probable match** and show the characters the camera actually read.
  2. A confirmed exact match should carry no such warning.
  - *If no probable match exists in current data, mark N/A — it depends on what the cameras read.*

- [ ] **4.6 — Acknowledge workflow.** On **Alerts**, click **Ack** (or **Ack all N**) on an episode.
  1. Status should change from open to cleared.
  2. The acknowledgement should appear in the **Atlas** audit trail against your user.

---

## 5. Mandatory — Test case: trace a designated vehicle

> *"Given a vehicle registration number, identify, trace and present the
> movement of the vehicle across the integrated CCTV network as it appears at
> different camera locations and times. Complete route traversed, including
> timestamped and location-wise movement history."*

- [ ] **5.1 — Trace by registration number.** Go to **Trace**, enter a plate from Detections, submit.
  1. Should return the vehicle with badges for cameras seen and total detections.

- [ ] **5.2 — Timestamped, location-wise history.** On the same result.
  1. A numbered timeline should list each sighting with **location, district, first/last seen time, read confidence and an evidence image**.
  2. Times should be readable and correct (IST).

- [ ] **5.3 — GIS visualisation.** Look at the map beside the timeline.
  1. Sighting locations should be marked with numbered sequence pins.
  2. The wider camera network should be visible as context, not an empty canvas.
  3. If the vehicle was seen on **2+ cameras**, a route polyline should connect the pins in time order.
  4. If seen at **one location only**, the page should say so explicitly. *This is current expected behaviour — no plate in this dataset has yet appeared on two cameras.*

- [ ] **5.4 — Unknown plate.** Search a plate that does not exist, e.g. `GJ99ZZ9999`.
  1. Should show a clear **Not Sighted** state — not a crash, spinner or empty screen.

---

## 6. Mandatory — Output report

> *"Submit a screen-recorded video along with an output report showing detected
> vehicles or number plates with corresponding timestamps."*

- [ ] **6.1 — Export from the UI.** On **Detections**, click **⬇ Output report**.
  1. A CSV should download.

- [ ] **6.2 — Report contents.** Open the CSV.
  1. Columns should include camera, location, district, plate, **ocr_confidence**, reads_in_vote, **timestamp_utc**, **timestamp_ist**, evidence path.
  2. Timestamps should be populated and plausible.

- [ ] **6.3 — Submission copy is valid.** Open `submission/sutra_gov_feed_output_report_2026-09-26.csv`.
  1. Should contain 82 rows, government cameras only (cam06/cam07) — no demo file cameras.
  2. Pick any row and confirm its `evidence_snapshot` file exists in `submission/evidence_2026-09-26/`.

---

## 7. Cybersecurity & access control

> *"Enhanced cybersecurity, privacy protection, auditability, or role-based
> access controls."*

- [ ] **7.1 — No anonymous access.** Sign out. Open http://127.0.0.1:8010/api/atlas/cameras directly in the browser.
  1. Should return **401 Unauthorized**, not camera data.

- [ ] **7.2 — Bad credentials rejected.** At the login page, try `admin` with a wrong password.
  1. Should fail with an error and **not** sign you in.

- [ ] **7.3 — Evidence is protected.** While signed out, open an evidence URL directly, e.g. `http://127.0.0.1:8010/data/detections/6/<any-file>.jpg`.
  1. Should be refused, not served.

- [ ] **7.4 — Security headers.** On the hosted platform, open browser DevTools → Network → click the `health` request → Response Headers.
  1. Should include `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`.

- [ ] **7.5 — Audit trail is real.** On **Atlas**, review the audit list.
  1. Your logins, exports, watchlist edits and acknowledgements from this test run should all be present and attributed.

---

## 8. Hosted platform (judge-facing)

- [ ] **8.1 — Judge URL is up.** Open https://sutra-central.onrender.com in a **private window**.
  1. Should load the SUTRA login page.

- [ ] **8.2 — Judge credentials work.** Sign in as `admin` / `Sutra#Gandhinagar26`.
  1. Should sign in successfully.

- [ ] **8.3 — Hosted platform has real data.** Visit Overview, Registry, Detections, Alerts, Atlas, Trace.
  1. Each should show real accumulated data, not empty states.
  2. **Video Wall will show no live streams** — expected. Ingest is an edge responsibility; the hosted tier is the central tier.

- [ ] **8.4 — Deep links work.** Paste https://sutra-central.onrender.com/atlas straight into the address bar.
  1. Should load the Atlas page directly, not a 404.

---

## 9. Submission package

- [ ] **9.1 — Repository is public and complete.** Open https://github.com/laveshparyani/SUTRA in a private window.
  1. Should load without a login; README should render with the judge section at the top.
  2. Licence, Contributing, Security and Code of Conduct should be listed.
  3. Contributors should show **only** laveshparyani.

- [ ] **9.2 — Submission artifacts present.** Check the `submission/` folder.
  1. `SUTRA_Solution_Presentation.pptx` opens and has 12 slides.
  2. `SUTRA_HLD.pdf` opens and is readable.
  3. Output report CSV and `evidence_2026-09-26/` are present.
  4. `README.md` indexes them.

- [ ] **9.3 — Demo videos.** *(after recording)*
  1. Both links open in a **private window** and play.
  2. Each is within 2–3 minutes.
  3. Visibility is Unlisted (YouTube) or "Anyone with the link — Viewer" (Drive).

- [ ] **9.4 — Submission form.** On sentinel.gujarat.gov.in, before submitting, confirm you have: presentation, HLD PDF, both video links, output report, repo URL, hosted URL **with credentials**.

---

## Defects found

| # | Test ref | What I did | What I expected | What happened | Severity |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

Severity: **blocker** (cannot submit) · **major** (a requirement fails) ·
**minor** (cosmetic).

---

## Known and accepted — do not log these

These are documented behaviours, not bugs:

1. **No plate appears on 2+ cameras**, so Trace draws a single point rather than a route line. The portal's cameras are up to ~1,000 km apart replaying independent footage. Trace states this explicitly rather than hiding it.
2. **Low-confidence reads (≤0.86) can have character errors.** Characterised in `submission/README.md`; the confidence column exists so a reader can apply a threshold.
3. **Only 3–4 government cameras stream at once.** The portal rations ~5 Mbps per client IP — measured. The scheduler rotates all 30 through the available slots.
4. **The hosted Video Wall shows no live video.** By design: video stays at the edge, metadata flows up.
5. **Decoder warnings on camera join** (`Could not find ref with POC`) are expected and self-correct — the portal's own integrator guide says so.
