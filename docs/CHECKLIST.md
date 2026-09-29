# SUTRA — Requirements Checklist vs. Official Hackathon Statement
*First audited 19 Aug 2026 against the full problem statement; statuses
re-verified 28 Sep 2026 on submission day, against the acceptance run recorded
in [TESTING.md](TESTING.md) (31 of 31 passed). Deadline: **28 Sep 2026**, event
12–13 Oct (organisers moved it twice: 29 Aug → 7 Sep → 28 Sep). The problem
statement itself was re-checked on 24 Sep 2026 and is unchanged.*

Legend: ✅ done & verified · 🟡 partial / untested · ❌ missing

## A. Mandatory — Model 1 (Registry & GIS Foundation, compulsory)

| Requirement | Status | Notes |
|---|---|---|
| Working registry portal with GIS map view | ✅ | Atlas + Leaflet map, health-coloured markers |
| Manual + API-based onboarding | ✅ | POST /api/atlas/cameras, auto-discovery |
| Bulk import | ✅ | `POST /api/atlas/cameras/bulk`; covered by `test_bulk_import_creates_and_skips` and a role/file-validation test |
| Camera metadata: location, dept, connectivity, storage, retention | ✅ | |
| Camera metadata: **camera type, ownership** | ✅ | `camera_type`, `ownership` and `install_date` on the model and shown in the registry (test 1.1) |
| Health & maintenance-status monitoring | ✅ | Live health, honest connecting/down states |
| Gap-analysis reports (uncovered zones, ageing infra) | ✅ | District coverage plus ageing against a five-year cutoff, driven by `install_date` (test 1.7) |
| Role-based search, filtering, **export**, audit trails | ✅ | Search/filter/RBAC, `GET /api/atlas/export` CSV, and the audit viewer on Atlas (tests 1.3, 1.4, 1.8, 7.2) |
| Registry API documentation | ✅ | [API.md](API.md) — all 42 endpoints with role requirements, generated from the OpenAPI schema by `scripts/build_api_reference.py` so it cannot drift; FastAPI `/docs` also served live |
| Sample onboarded metadata dataset | ✅ | 38 cameras across 7 departments via discovery |

## B. Mandatory — Test case (Step 4, the live evaluation)

| Requirement | Status | Notes |
|---|---|---|
| Onboard ~50 heterogeneous cameras onto one platform | ✅ | All portal cameras auto-onboard; mp4/mkv verified (avi & portal outages are their side, reported) |
| Centralised monitoring | ✅ | Video wall (honest states) + scheduler |
| AI analytics: ANPR | ✅ | ONNX det+OCR, temporal voting, state-code repair, 30-75 ms/frame CPU |
| Designated-vehicle trace: route, timestamped movement history | 🟡 | Works end to end (tests 5.1–5.4). Still only ever **observed on one camera**: no plate has been read by two of the portal's cameras, which sit up to ~1,000 km apart replaying independent footage. Trace states this on screen rather than leaving an unexplained point, and draws the route as soon as a second camera reads the same plate. |
| Watchlist DB + continuous cross-referencing | ✅ | Exact + fuzzy (confusion-fold, edit-dist 1) |
| Automated real-time alerts on match | ✅ | WS push, toasts, evidence frames, ack workflow, 15-min cooldown |
| GIS visualisation of route | ✅ | Polyline + numbered sequence markers |
| **Output report (plates + timestamps)** — required with gov-feed video | ✅ | `GET /api/insight/report` exports CSV in-product (test 6.1); the submitted run is `submission/sutra_gov_feed_output_report_2026-09-26.csv` — 82 reads, each with its evidence crop |

## C. Mandatory — Submission documents (all present)

| Deliverable | Status |
|---|---|
| Solution Presentation (PPT/PDF) | ✅ `submission/SUTRA_Solution_Presentation.pptx` |
| HLD document (arch diagrams, integration, analytics incl. **FRS approach**, alert workflow, security, 80k scale, dept prerequisites, infra sizing, **cost-benefit**, roadmap) | ✅ `submission/SUTRA_HLD.pdf`, written from [HLD.md](HLD.md) |
| Own-feed demo video (2–3 min, real working software) | ✅ `SUTRA_own_feed_demo_captioned.mp4` — 2:36, narrated, captions burned in |
| Gov-feed demo video + output report | ✅ `SUTRA_government_feed_demo_captioned.mp4` — 2:31 — with `sutra_gov_feed_output_report_2026-09-26.csv` (82 reads) and all 82 evidence crops |
| Scalability plan (~80k: edge/regional/central, GPU sizing, bandwidth, storage tiers, HA/DR, **costs**) | ✅ HLD §8, on measured throughput rather than estimates |
| Hosted URL + test credentials (optional, recommended) | ✅ https://sutra-central.onrender.com — credentials given on the submission form, deliberately not in this repository |
| GitHub repo (optional, recommended) | ✅ https://github.com/laveshparyani/SUTRA |
| Verification walkthrough (extra, not required) | ✅ `SUTRA_verification_walkthrough.mp4` — 6:04, every acceptance test in [TESTING.md](TESTING.md) run against the live system |

## D. Core objective coverage — "correlate with Government databases"

| Item | Status | Notes |
|---|---|---|
| Representative watchlist DB (explicitly permitted) | ✅ | |
| VAHAN/SARTHI/eGujCop/AFIS/NAFIS **integration readiness** | ❌ | Claimed in architecture text but **no connector interface or doc exists in code** — cheap, high-visibility gap |
| Private/society camera viewing support | 🟡 | Any RTSP/HTTP/file source onboards in principle; say so explicitly in HLD |

## E. Bonus criteria (scored extras)

| Bonus item | Status |
|---|---|
| Innovative hybrid architecture | ✅ Model 1+3 hybrid, justified |
| Advanced cross-camera tracking | 🟡 route reconstruction ✅; no multi-camera demo yet |
| Analytics beyond ANPR (person/object/intrusion detection, FRS) | ❌ none implemented |
| Edge-processing / bandwidth optimisation / low-connectivity | ✅ adaptive ingest scheduler + CPU-only ONNX story |
| Cybersecurity, privacy, auditability, RBAC | 🟡 JWT+RBAC+audit-log ✅; media endpoints unauthenticated (document as sandbox choice); no audit viewer |
| Operational dashboards, health monitoring, integration-ready APIs | ✅ |

## F. Known technical debt (not blocking, disclosed honestly)

Still open:

- Two-line truck and auto plates OCR poorly (concatenation order)
- Accuracy is a seven-row spot check across the confidence range
  (`submission/README.md`), not an exhaustive ground-truth audit

Closed since the first audit:

- ~~No end-to-end browser suite~~ — `e2e/` drives the built bundle in a real
  browser against a throwaway database on its own port: sign-in and rejection,
  role enforcement in the interface *and* at the server, every main route, the
  detections-view regression, and a multi-camera trace
- ~~RTSP never exercised~~ — RTSP over TCP is now the transport for all 30
  government cameras, with credentials injected at connection time
- ~~Snapshot folders grow unbounded~~ — retention worker enforces an evidence
  budget and a detection-retention window, and collapses duplicate rows
- ~~WS alert channel unauthenticated~~ — the handshake is checked against the
  HttpOnly media cookie and closed with 4401 when absent

## Priority order to close (recommended)

Items 1–9 below were the August plan. All are done except the third, which the
dataset does not permit.

1. ~~Output report generator~~ — `GET /api/insight/report`, CSV, in-product
2. ~~Initial git commit + push to GitHub~~
3. **Multi-camera trace demo** — *not achieved, and not achievable here.* No
   plate has ever been read by two of the portal's cameras: they are up to
   ~1,000 km apart replaying independent footage. The route logic is built and
   draws as soon as a second camera reads the same plate; until then Trace says
   so on screen rather than implying a route that was never observed
4. ~~VAHAN-style connector interface~~ — enrichment on alerts, owner masked
5. ~~Model 1 gaps~~ — camera_type/ownership/install_date, registry CSV export,
   audit-trail viewer, bulk import (all tested)
6. ~~RTSP adapter proof~~ — superseded: RTSP is the live government transport
7. ~~HLD + presentation + scalability doc~~
8. ~~Demo videos~~ — own-feed and government-feed, both narrated and captioned
9. ~~Analytics bonus~~ — person/vehicle counts per camera on CPU