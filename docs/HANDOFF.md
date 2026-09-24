# SUTRA — Session Handoff (written 25 Sep 2026, 01:00 IST)

Purpose: let a fresh Claude Code session on another PC continue exactly where
the laptop session stopped. Read this first, then `docs/TASKS.md` and
`docs/RECON.md`. Everything below is on branch `dev`, pushed to
https://github.com/laveshparyani/SUTRA. `main` is behind `dev`; the judge URL
on Render redeploys from `main`.

## Deadline

- **28 Sep 2026** — last date to apply and upload the submission (also shortlisting).
- **12–13 Oct 2026** — event at i-Hub Gujarat; results 13 Oct.
- Source: https://sentinel.gujarat.gov.in/schedule (checked 24 Sep). The
  problem statement itself has not changed since the August audit in
  `docs/CHECKLIST.md`.

## What changed in the last session (all committed on `dev`)

1. **Feed portal moved and is behind a login.** It is now
   `https://cctv.corp8.cloud` (own register/login, system-issued password).
   Real endpoints, verified logged-in: catalogue `GET /cameras.json`
   (30 cameras, id + name only); RTSP
   `rtsp://<email%40>:<password>@103.250.160.189:8554/stream/<camNN>`
   (mediamtx, TCP, H.264 + H.265, ~10 s to first frame); HLS
   `https://cctv.corp8.cloud/<camNN>/index.m3u8` (cookie + browser UA,
   AES-128, a finished ~12 h VOD, fallback only). Full notes: `docs/RECON.md`.
2. **Ingest rewritten for it** — `backend/app/services/portal.py` (login,
   cookie cache, credential injection at stream-open, redaction),
   `discovery.py` (cameras.json → existing `sentinel-N` rows updated in
   place, history kept), `ffreader.py` (RTSP `-timeout`, arrival-time
   sampling so the loop-point PTS jump can't stall, cookie/UA for HLS,
   join-time decoder noise ignored, opt-in `SUTRA_RTSP_KEYFRAMES_ONLY`
   low-CPU mode), `sampler.py` (credentials never stored or logged).
3. **Verified live:** 30 cameras discovered; frames at ~1 fps over RTSP;
   111 plate detections from cameras 6, 7 and 12 in a ~90 min run
   (`submission/sutra_gov_feed_output_report_2026-09-24.csv`).
4. **Deliverables regenerated:** `submission/SUTRA_Solution_Presentation.pptx`
   (slide 8 now tells the "sandbox moved three times, platform didn't"
   story), `submission/SUTRA_HLD.pdf` (5 pages, HLD §3/§4 updated), README
   and docs carry the 28 Sep / 12–13 Oct dates, `docs/DEMO_SCRIPT.md` names
   the new ports and cameras to pin.
5. **Bug fixed:** `/api/insight/report?since=…T…Z` returned zero rows on
   SQLite (string comparison). Now parsed as datetimes; tests in
   `backend/tests/test_report_window.py`.
6. **Tests:** 174 passing (`cd backend && ../.venv/Scripts/python -m pytest -q`).
   New API/RBAC integration tests under `backend/tests/test_api_*.py`,
   `backend/pytest.ini` (120 s per-test timeout), `backend/conftest.py`
   (pins role/central/portal settings to safe values so a developer's
   `backend/.env` can never make tests hit the network).

## Set up the office PC (before anything else)

```bash
git clone https://github.com/laveshparyani/SUTRA && cd SUTRA && git checkout dev
py -3.13 -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
cd frontend && npm install && cd ..
```

- FFmpeg 9 must be on PATH (winget `Gyan.FFmpeg` is what the laptop uses).
- **Recreate `backend/.env` by hand** — it is gitignored and holds secrets.
  Copy it from the laptop securely (not via chat, not via the repo). Keys:
  `SUTRA_ROLE=edge`, `SUTRA_CENTRAL_URL`, `SUTRA_SYNC_API_KEY`,
  `SUTRA_SYNC_INTERVAL_S`, `SUTRA_INGEST_BUDGET`, `SUTRA_PORTAL_EMAIL`,
  `SUTRA_PORTAL_PASSWORD`. Without the two portal keys, discovery returns
  502 and no portal camera will stream.
- The ANPR models live under `backend/app/models/` and `data/models/`;
  check they are present after clone (the scene model ships with the code,
  the plate models are downloaded on first run if missing).
- Dev servers: `.claude/launch.json` defines `sutra-api` (port 8010,
  because 8000 is held by a Windows service on the laptop; use 8000 if free)
  and `sutra-command` (Vite on 5173, proxy via `SUTRA_API_URL`). Quick
  check: `curl http://127.0.0.1:8010/api/health`.
- Verify the portal from that network first:
  `python scripts/probe_feeds.py cam04 3` (needs the .env). If port 8554 to
  103.250.160.189 is blocked there, set cameras to their `alt_hls_url`
  (HLS fallback works with the cookie; the sampler handles it).

## Pending — in priority order

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 1 | **Render judge URL is dead** | Lavesh (dashboard), then Claude | `https://sutra-central.onrender.com/api/health` accepts TCP but never answers. Most likely the free Postgres (`sutra-db`) expired after 30 days (~19–20 Sep). Open the Render dashboard (account laveshparyani01@gmail.com), check `sutra-db` and `sutra-central`. Fix: new free DB re-attached, or move the central tier (docs/DEPLOYMENT.md has the Oracle Always Free alternative). The Chrome extension could not read dashboard.render.com from the laptop. |
| 2 | **Open PR `dev` → `main`** and merge | Claude | CI must be green (tests, frontend build, pip-audit, gitleaks). Merging triggers the Render redeploy — do it after #1 so the deploy lands on a live DB. |
| 3 | **Longer government-feed run + final output report** | Claude | Run the edge node for a few hours (`SUTRA_INGEST_BUDGET` 6–10; `SUTRA_RTSP_KEYFRAMES_ONLY=true` if CPU is tight), pin the plate-rich cameras (7, 6, 12 and the Junagadh cluster 8–11), then export `GET /api/insight/report?since=<run start>` to `submission/`. The 24 Sep file is a 111-row preliminary. |
| 4 | **Multi-camera trace check** | Claude | No plate has yet been seen on two cameras in the new run. After a long run: `select plate_text, count(distinct camera_id) … having count(distinct camera_id) >= 2` on `data/sutra.db`. If one appears, screenshot the Trace page for the deck/demo. |
| 5 | **Testing framework, remaining layers** | Claude | Backend API tests are done. Still to build: Playwright e2e under `frontend/e2e` (dedicated ports, e.g. API 8020 / Vite 5174, throwaway SQLite via `SUTRA_DATA_DIR`/`SUTRA_DB_URL`, flows: login, wrong password, registry search, map renders, watchlist add, alerts, trace not-sighted, viewer role gating, logout); `scripts/smoke.py` against a running instance (default 8010, or the hosted URL); `scripts/test_all.ps1` + `.sh` entry point; `docs/TESTING.md` playbook; optional e2e job in CI. A background agent had started this; only the backend part survived and has been committed. |
| 6 | **Record the two demo videos** | Lavesh | `docs/DEMO_SCRIPT.md`. Own-feed and government-feed, 2–3 min each, unlisted YouTube or Drive with viewer access. |
| 7 | **Final read-through of the submission package** | Claude | README judge section (URL + credentials line), `submission/` contents, all seven evaluation areas in `docs/CHECKLIST.md`, links work, repo public. |
| 8 | **Submit on sentinel.gujarat.gov.in** | Lavesh | 28 Sep. |

Nice to have: HLS wall-clock offset so the fallback matches the portal's
"live" position; scheduler dwell tuned for 10 s connects (it was sized for
48 s on the old portal).

## Skills and tooling (not in the repo)

`.claude/skills/` is gitignored on purpose (this repo is the submission).
The laptop has 21 skills there: obra/superpowers workflow set,
anthropics `webapp-testing` / `frontend-design` / `skill-creator`, vercel
`react-best-practices` / `web-design-guidelines`, and
`awesome-skills/code-review-skill`. Sources and review notes are in
`.claude/skills/README.md` on the laptop. To reuse them on the office PC,
copy that folder over, or keep it in a private `claude-config` repo.

## Facts that cost time to learn

- Port 8000 is reserved by a Windows service on the laptop; the API runs on 8010.
- Ten full-decode 1080p25 streams saturate an 8 GB / 8-core laptop
  (~0.2 core per camera before inference). Keyframe-only mode is ~4× cheaper.
- FFmpeg 9 rejects `-rw_timeout` for RTSP; use `-timeout`.
- The hackathon site's Resource page describes `/api/ingest` and `<host>`
  placeholders; `/api/ingest` is a 404 on the real portal. Trust the portal's
  own `/resource` page.
- The Render DB check needs the Render dashboard; the Claude-in-Chrome
  extension timed out on that SPA but works on other sites.
- The HLD PDF is produced with headless Chrome:
  `python scripts/build_hld_pdf.py docs/HLD.md out.html`, then
  `chrome.exe --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=out.pdf file:///out.html`.
- Deck: `node scripts/build_presentation.js` (pptxgenjs is installed
  globally under `C:\Users\Admin\node_modules` on the laptop; `npm i -g pptxgenjs` elsewhere).
