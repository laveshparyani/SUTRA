# SUTRA — Statewide Unified Tracking, Registry & Analytics

**Gujarat Police CCTV Integration Hackathon 2026** · Category 1 (Individual) · Lavesh Paryani

*"Sutra" — the thread that connects.* A federation layer weaving 26 departments'
fragmented CCTV systems into one intelligent fabric: one registry, one map, one
alert stream — without asking any department to replace its existing VMS.

---

## Live platform (for judges)

| | |
|---|---|
| **Platform URL** | **https://sutra-central.onrender.com** |
| **Credentials** | supplied in the submission form (admin + read-only viewer) |
| **Status** | live 24/7, HTTPS, no login wall on `/api/health` |

The hosted instance is the **central tier**. Live camera ingest runs on an
**edge node**, matching the deployment model proposed in the HLD — video stays
at the edge, metadata flows up. This is the architecture, not a compromise:
centralising 80,000 video streams is a bandwidth trap (see HLD §8).

```
edge node (ingest + ANPR)  ──metadata/evidence, 30s──▶  central tier (hosted)
   your PC / dept. hardware                                registry · alerts · trace
```

---

## What it does

| Module | Capability | Hackathon model |
|---|---|---|
| **SUTRA Atlas** | CCTV registry, GIS coverage map, health monitoring, gap & ageing analysis, bulk/API onboarding, CSV export, audit trail | **Model 1** (mandatory) |
| **SUTRA Bridge** | Source adapters — RTSP (forced TCP), HTTP-progressive, file, HLS/ONVIF-ready — plus an adaptive ingest scheduler and shared MJPEG relay | **Model 3** |
| **SUTRA Insight** | ANPR (YOLOv9-t + CCT OCR, ONNX/CPU), temporal voting, Indian-plate normalisation, scene analytics (YOLOX-nano), route reconstruction | Model 2/4 analytics |
| **SUTRA Watch** | Watchlist store, exact + fuzzy matching, real-time alerting, government-DB connector interface (VAHAN/SARTHI/eGujCop/AFIS) | Challenge core |
| **SUTRA Command** | React control room — video wall, GIS map, vehicle trace, alerts, registry, watchlist, audit | Challenge core |

### Measured on the working platform

All figures from the running system on a **CPU-only** machine (no GPU):

- Plate detection + OCR — **30–75 ms/frame**
- Scene analytics (person/vehicle) — **43 ms/frame**
- Central tier memory — **102 MB** · Edge node with 9 cameras — **514 MB**
- **59 automated tests** across 10 files · CI runs tests, frontend build,
  `pip-audit` and a full-history secret scan on every push

---

## Repo layout

```
SUTRA/
├── backend/            FastAPI service — the whole server side
│   ├── app/
│   │   ├── routers/    atlas · bridge · insight · watch · auth · sync  (40 endpoints)
│   │   ├── services/   ingest workers, ANPR pipeline, scheduler, syncer, retention
│   │   ├── connectors/ government-database adapter interface (VAHAN et al.)
│   │   └── models/     bundled ONNX model (YOLOX-nano)
│   └── tests/          59 tests — security, ANPR, migration, sync, retention
├── frontend/           React + Vite + Leaflet control room (9 pages)
├── docs/               HLD, architecture, security, deployment, demo scripts
├── submission/         deliverables — presentation, output reports, registry CSV
├── scripts/            utilities (presentation builder, backfills)
├── infra/              deployment configs, edge-node installers
└── render.yaml         one-click blueprint for the hosted central tier
```

The backend is a single FastAPI application; Atlas / Bridge / Insight / Watch
are **modules within it** (`backend/app/routers/`, `backend/app/services/`),
not separate services — deliberate, so the whole platform runs on one small
node at the edge.

---

## Running it locally

**Prerequisites:** Python 3.13, Node 20+, and **FFmpeg on `PATH`** (the ingest
workers shell out to it for decoding).

```bash
# backend
py -3.13 -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
# frontend (separate terminal) → http://localhost:5173
cd frontend && npm install && npm run dev
```

Interactive API docs at `http://127.0.0.1:8000/docs`. On first run the database
is created and seeded automatically; seed passwords are printed as a startup
warning and are overridable via `SUTRA_SEED_ADMIN_PW` / `_OPERATOR_PW` / `_VIEWER_PW`.

### Running as an edge node

Create `backend/.env` to push metadata to a hosted central tier:

```ini
SUTRA_ROLE=edge
SUTRA_CENTRAL_URL=https://sutra-central.onrender.com
SUTRA_SYNC_API_KEY=<key from the central tier's environment>
```

Roles are `full` (all-in-one), `edge` (ingest + inference), `central`
(command centre, no video decode).

---

## API surface

Six routers, 40 endpoints, all authenticated except `/api/health`:

| Prefix | Purpose |
|---|---|
| `/api/atlas` | registry, GIS, discovery, bulk import, gap analysis, CSV export, audit |
| `/api/bridge` | ingest control, health, snapshot / MJPEG relay, scheduler |
| `/api/insight` | detections, sightings, analytics, vehicle trace, output report, scene |
| `/api/watch` | watchlist CRUD, alerts, acknowledgement, alert WebSocket |
| `/api/auth` | login, token refresh, media cookie |
| `/api/sync` | edge → central metadata + evidence channel |

Selected endpoints:

- `POST /api/atlas/discover` — auto-onboard portal cameras into the registry
- `GET  /api/atlas/gap-analysis` · `/api/atlas/export` — coverage & registry CSV
- `POST /api/bridge/cameras/{camera_id}/start` — begin ingestion (also `/stop`, `/pin`)
- `GET  /api/bridge/cameras/{camera_id}/mjpeg` — live relay preview
- `GET  /api/insight/report` — **output report** (plates + timestamps, CSV/JSON)
- `GET  /api/insight/route/{plate}` — timestamped cross-camera movement history
- `GET  /api/insight/sightings` — consecutive reads collapsed into sightings
- `POST /api/watch/vehicles` — add a plate to the watchlist

---

## Security

Hardened against a pre-submission audit that closed 10 findings — see
[docs/SECURITY.md](docs/SECURITY.md). Highlights: per-install generated JWT
secret, authenticated evidence store with path confinement, cookie-authenticated
MJPEG and alert WebSocket, login rate limiting, SSRF-safe source onboarding,
restricted CORS, and a full audit trail. Verified against the live host.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/HLD.md](docs/HLD.md) | **High-Level Design** — the technical proposal (also as PDF in `submission/`) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | component and data-flow detail |
| [docs/SECURITY.md](docs/SECURITY.md) | threat model, audit findings, fixes |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | sizing, hosting options, deployment guide |
| [docs/SETUP_STEPS.md](docs/SETUP_STEPS.md) | hosted-deployment walkthrough |
| [docs/CONNECTORS.md](docs/CONNECTORS.md) | government-database connector interface |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | demo video shot scripts |
| [docs/TASKS.md](docs/TASKS.md) | build log and audit history |

---

## Key dates (2026)

- **4 Aug** — registration opened
- **7 Sep** — last date to apply / submit
- **7 Sep, evening** — shortlisting
- **10–11 Sep** — hackathon event, Grand Finale + results
