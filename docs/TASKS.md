# SUTRA — Gap-Closure Task Sheet
*Live status board. Updated by Claude as work progresses. Started 19 Aug 2026.*

| # | Task | Status | Notes |
|---|------|--------|-------|
| T1 | Output report generator (detections + timestamps, CSV export + UI button) | ✅ done | /api/insight/report CSV+JSON, UI button on Detections |
| T2 | Git initial commit (+ GitHub if gh auth available) | ✅ done | commits 07e5860+1edaea7 pushed to github.com/laveshparyani/SUTRA (private) |
| T3 | Multi-camera trace: cross-camera ANPR scan of 3 sample clips, find plate on ≥2 cameras | ✅ done (verdict) | Scanned all 3 clips: Janpath+Chinman are ANPR-blind (angle); NO genuine cross-camera vehicle exists in sample footage. Demo = dual-path correlation (file cam 31 + RTSP cam 36, truck-centred loop) + eval-day network. Finding: seek-based scanning unreliable vs sequential decode |
| T4 | VAHAN-style connector: interface + representative lookup + alert enrichment + docs | ✅ done | connectors/ pkg, VAHAN rep. data, alert enrichment, Trace panel, docs/CONNECTORS.md |
| T5a | Camera model: camera_type / ownership / install_date fields + migration | ✅ done | fields + auto-migration on startup |
| T5b | Registry CSV export endpoint + button | ✅ done | /api/atlas/export + Registry button |
| T5c | Audit-trail endpoint + UI viewer | ✅ done | /api/atlas/audit + Atlas page section |
| T5d | Bulk CSV import — test end-to-end | ✅ done | 4 cameras imported incl. private/society ownership; new fields flow through; ageing analysis live |
| T6 | RTSP adapter proof (serve clip via RTSP, onboard as rtsp source) | ✅ done | mediamtx + Defender exclusion; root causes: unsigned-binary freeze + RTP-over-UDP firewall drop (sampler now forces rtsp_transport=tcp); cam 36 flowing through full pipeline |
| T7 | Bonus analytics: person/vehicle detection (YOLOX-nano ONNX) | ✅ done | YOLOX-nano sidecar: 43ms/frame, throttled 1 frame/20s/camera; live counts on Video Wall + /api/insight/scene |

Status legend: ⬜ pending · 🔄 in progress · ✅ done · ⚠️ blocked

## Phase D — Submission deliverables (deadline 29 Aug)

| # | Task | Status | Notes |
|---|------|--------|-------|
| D1 | Government-feed evidence capture | ✅ done | submission/: full report (101 rows), cam-7 gov report (15 rows), registry CSV, 19 evidence JPEGs |
| D2 | Demo video shot scripts | ✅ done | docs/DEMO_SCRIPT.md — both videos, shot-by-shot with narration |
| D3 | HLD document | ✅ done | docs/HLD.md + submission/SUTRA_HLD.pdf (4 pages, A4); regenerate with `python scripts/build_hld_pdf.py docs/HLD.md out.html` then print-to-PDF |
| D4 | Record own-feed demo video (2-3 min) | ⬜ pending | Lavesh records per script; system stays demo-ready |
| D5 | Record government-feed demo video | ⬜ pending | record around Camera 7 while portal healthy |
| D6 | Solution Presentation (PPT/PDF) | ✅ done | submission/SUTRA_Solution_Presentation.pptx — 12 slides; regenerate with `node scripts/build_presentation.js` |
| D7 | Scalability plan doc | ✅ folded into HLD §8 | expand to standalone if guidelines require |
| D8 | Hosting + judge credentials | ✅ done | Render central (sutra-central.onrender.com) + edge sync; judge creds ready |
| D9 | Final submission package (links, YouTube unlisted, repo public) | ⬜ pending | checklist in official Step 5 |

## Security hardening sprint (pre-submission audit, 20 Aug)

| Issue found | Severity | Fix | Verified |
|---|---|---|---|
| Hardcoded JWT secret in repo → token forgery | CRITICAL | per-install auto-generated secret (data/.jwt_secret, gitignored); env override | ✅ test |
| /data evidence store fully public | CRITICAL | authenticated route, path-confined, image-only | ✅ tests incl. encoded traversal |
| Camera snapshot/MJPEG endpoints public | HIGH | HttpOnly media-cookie auth (+ bearer) | ✅ test + UI |
| Alert WebSocket public (plate/location leak) | HIGH | cookie-authenticated handshake (4401 on fail) | ✅ browser check |
| No login rate limit → brute force | HIGH | 5 fails/5 min per client, 429, audited | ✅ test |
| XSS via Leaflet popups (camera names from CSV/portal) | HIGH | HTML-escape all popup interpolation | ✅ code |
| SSRF/file-read via source_url onboarding | MEDIUM | scheme allowlist + file sources confined to data dir | ✅ tests |
| CORS wildcard | MEDIUM | restricted to configured origins | ✅ |
| Bridge status/scheduler endpoints public (recon) | LOW | authenticated | ✅ test |
| Seeded passwords documented in repo | NOTE | env-overridable + loud warning; MUST set SUTRA_SEED_*_PW on any public host | docs |
| **Reliability**: OpenCV global open-lock starvation (dead portal cams blocked file/RTSP reop

## Security hardening sprint (pre-submission audit, 20 Aug)

Full write-up: docs/SECURITY.md · 19 automated tests in backend/tests/

| Issue found | Severity | Fix | Verified by |
|---|---|---|---|
| Hardcoded JWT secret in repo (token forgery for any deployment) | CRITICAL | per-install generated secret, gitignored, env-overridable | test_security |
| /data evidence store served unauthenticated | CRITICAL | authenticated route + path confinement + image allowlist | tests incl. encoded traversal |
| Camera snapshot/MJPEG endpoints unauthenticated | HIGH | HttpOnly media cookie (or bearer) | test + browser |
| Alert WebSocket unauthenticated (plates/locations leak) | HIGH | authenticated handshake, 4401 close | browser check |
| No login rate limiting | HIGH | 5 fails / 5 min per client -> 429, audited | test |
| XSS via Leaflet popups (names from CSV/portal) | HIGH | HTML-escape all interpolation | code review |
| SSRF / arbitrary file read via source_url | MEDIUM | scheme allowlist + file confinement | 2 tests |
| CORS wildcard with credentials | MEDIUM | restricted to configured origins | code |
| Bridge status/scheduler endpoints public (recon) | LOW | authenticated | test |
| Seed passwords documented in repo | NOTE | env-overridable + startup warning | docs/SECURITY.md |
| Reliability: OpenCV global open-lock starvation - dead cameras blocked healthy ones reopening | HIGH | 8s network open timeouts + exponential backoff + file sources rewind in place instead of reopening | live verify |

## CI/CD & hosting (20 Aug)

| Item | Status | Notes |
|---|---|---|
| Branch model main/dev/feature | DONE | master renamed to main; dev created; both pushed |
| CI pipeline | DONE | tests + frontend build + pip-audit + gitleaks full-history scan; all green |
| Docker deployment stack | DONE | Dockerfile (non-root, healthcheck) + compose (api + nginx, MJPEG-safe proxy) |
| Staging auto-deploy workflow | READY | fires on dev after CI; needs host secrets |
| Production deploy workflow | READY | fires on main after CI, gated by GitHub Environment reviewer; auto-rollback on failed smoke test |
| Deployment guide | DONE | docs/DEPLOYMENT.md: measured sizing, Oracle Always Free recommendation, setup steps |
| Secret-safety of git history | VERIFIED | gitleaks full-history scan clean |

### Needs Lavesh (cannot be automated)
1. Make repo public -> unlocks free branch protection + unlimited CI minutes
2. Provision host (Oracle Always Free ARM 4c/24GB recommended)
3. Add GitHub secrets DEPLOY_HOST / DEPLOY_USER / DEPLOY_SSH_KEY
4. Create staging + production Environments; set required reviewer on production
5. Write .env.production on the host with non-default passwords

## Live deployment verified (21 Aug)

**Judge URL: https://sutra-central.onrender.com** — Render free tier, always on, no card.

| Check | Result |
|---|---|
| Health, role=central, 0 ingest workers | PASS (232 ms) |
| SPA served incl. client routes | PASS |
| All API endpoints require auth | PASS (401) |
| Weak credentials (admin@123, admin, password, sandbox default) | PASS (all 401) |
| Login rate limiting | PASS (429 after 5 failures) |
| Evidence store requires auth | PASS (401) |
| Path traversal on live host | PASS (no leak) |
| Sync channel key enforcement | PASS (401 without/with wrong key) |
| Security headers (nosniff / DENY / no-referrer) | PASS |
| HTTPS | PASS (Cloudflare edge in front of uvicorn) |

Keep-warm pinger: cron-job.org every 10 min -> /api/health (60s timeout).


## Recheck audit (25 Aug) — pre-submission sweep

| Finding | Severity | Fix | Verified |
|---|---|---|---|
| Judge URL 15 commits behind (Render deploys main; everything since portal move was dev-only) | HIGH | dev pushed, PR #7 open dev→main; merge redeploys | CI running |
| Edge→central sync 500 crash-loop after restarts (in-memory cursor resent full history; multi-MB batches) | HIGH | cursor persisted to data/.sync_cursor; ≤600 KB evidence per batch | ✅ sync green post-restart |
| Atlas page had no GIS map (Model 1 mandatory: layered map) | HIGH | coverage map on Atlas: dept/type/status layers + coverage-radius | build ✅; visual check pending |
| Video wall starved connection pool (MJPEG cap = browser limit; login hung, "no cameras onboarded" over healthy core) | HIGH | cap 4, streams aborted on unmount, load-failure state distinct from empty | ✅ network log |
| Fuzzy watchlist hits displayed as exact reads | HIGH | Alert.match_type persisted + labelled in both alert views; 2 rows backfilled | ✅ API+UI |
| Frozen tiles labelled LIVE up to 30 s | MED | Stalled state at 8 s with age shown; stalled tiles release stream slots | ✅ API rule |
| Raw FFmpeg errors shown to operators ("Error number -138") | MED | translated to causes; raw kept in log | ✅ live (cam 6) |
| Portal capacity characterised: ~5 Mbps/IP ration → 3-4 live streams per IP | INFO | measured (10 vs 20 conns); email to organizers sent; rotation covers all 30 | ✅ measured |

All 21 API endpoints verified 200 with real data · 34 tests passing · frontend builds clean.
