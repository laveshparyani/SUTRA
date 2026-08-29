# SUTRA — Requirements Checklist vs. Official Hackathon Statement
*Audited 19 Aug 2026 against the full problem statement. Deadline: 7 Sep 2026
(extended by the organisers from the original 29 Aug).*

Legend: ✅ done & verified · 🟡 partial / untested · ❌ missing

## A. Mandatory — Model 1 (Registry & GIS Foundation, compulsory)

| Requirement | Status | Notes |
|---|---|---|
| Working registry portal with GIS map view | ✅ | Atlas + Leaflet map, health-coloured markers |
| Manual + API-based onboarding | ✅ | POST /api/atlas/cameras, auto-discovery |
| Bulk import | 🟡 | CSV endpoint exists but **never tested** |
| Camera metadata: location, dept, connectivity, storage, retention | ✅ | |
| Camera metadata: **camera type, ownership** | ❌ | Fields absent from model — spec names them explicitly |
| Health & maintenance-status monitoring | ✅ | Live health, honest connecting/down states |
| Gap-analysis reports (uncovered zones, ageing infra) | 🟡 | District coverage works; no **ageing** (no install_date), no **report export** |
| Role-based search, filtering, **export**, audit trails | 🟡 | Search/filter/RBAC/audit-log ✅; **CSV export missing**; **no audit-trail viewer UI** |
| Registry API documentation | 🟡 | FastAPI /docs auto-generated; needs a written API doc page for submission |
| Sample onboarded metadata dataset | ✅ | 31 live cameras via discovery |

## B. Mandatory — Test case (Step 4, the live evaluation)

| Requirement | Status | Notes |
|---|---|---|
| Onboard ~50 heterogeneous cameras onto one platform | ✅ | All portal cameras auto-onboard; mp4/mkv verified (avi & portal outages are their side, reported) |
| Centralised monitoring | ✅ | Video wall (honest states) + scheduler |
| AI analytics: ANPR | ✅ | ONNX det+OCR, temporal voting, state-code repair, 30-75 ms/frame CPU |
| Designated-vehicle trace: route, timestamped movement history | 🟡 | Works end-to-end but only **demonstrated on 1 camera** — need a genuine multi-camera trace before demo day |
| Watchlist DB + continuous cross-referencing | ✅ | Exact + fuzzy (confusion-fold, edit-dist 1) |
| Automated real-time alerts on match | ✅ | WS push, toasts, evidence frames, ack workflow, 15-min cooldown |
| GIS visualisation of route | ✅ | Polyline + numbered sequence markers |
| **Output report (plates + timestamps)** — required with gov-feed video | ❌ | No report/export generator yet — must build (CSV/PDF) |

## C. Mandatory — Submission documents (none started; ALL required)

| Deliverable | Status |
|---|---|
| Solution Presentation (PPT/PDF) | ❌ |
| HLD document (arch diagrams, integration, analytics incl. **FRS approach**, alert workflow, security, 80k scale, dept prerequisites, infra sizing, **cost-benefit**, roadmap) | ❌ (ARCHITECTURE.md is a skeleton, not submission-grade) |
| Own-feed demo video (2–3 min, real working software) | ❌ |
| Gov-feed demo video + output report | ❌ (blocked on portal uptime for fresh footage; output report generator needed) |
| Scalability plan (~80k: edge/regional/central, GPU sizing, bandwidth, storage tiers, HA/DR, **costs**) | ❌ (we have measured numbers; document not written) |
| Hosted URL + test credentials (optional, recommended) | ❌ (Cloudflare Tunnel planned) |
| GitHub repo (optional, recommended) | ❌ **repo has zero commits** |

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

## F. Known technical debt (not blocking, disclose honestly)

- Two-line truck/auto plates OCR poorly (concatenation order)
- No ground-truth accuracy measurement yet
- RTSP source type never actually exercised (OpenCV supports it; needs one test)
- Snapshot/frames folders grow unbounded (no retention cleanup)
- WS alert channel unauthenticated (sandbox)

## Priority order to close (recommended)

1. **Output report generator** (CSV/PDF of detections w/ timestamps) — required submission artifact
2. **Initial git commit** + push to GitHub
3. **Multi-camera trace demo**: run ANPR over Chinman Bridge + Janpath + Paldi daylight clips, find a plate genuinely seen on ≥2 cameras
4. **VAHAN-style connector interface** (documented stub + representative vehicle-details enrichment on alerts)
5. **Model 1 gaps**: camera_type/ownership/install_date fields, registry CSV export, audit-trail viewer, test bulk import
6. **RTSP adapter proof** (serve demo clip via local RTSP → onboard it) — federates a 3rd source type
7. **HLD + presentation + scalability doc** (Phase D)
8. Demo videos (own-feed anytime; gov-feed when portal recovers)
9. Optional analytics bonus: lightweight person/vehicle detection pass
