# SUTRA — Statewide Unified Tracking, Registry & Analytics

**Gujarat Police CCTV Integration Hackathon 2026** (sentinel.gujarat.gov.in)

*"Sutra" — the thread that connects. A federation layer weaving 26 departments'
fragmented CCTV systems into one intelligent fabric.*

## Architecture: Hybrid Model 1 + Model 3 (+ selective Model 2/4 analytics)

| Module | Role | Maps to |
|---|---|---|
| **SUTRA Atlas** | CCTV registry + GIS map (PostGIS/Leaflet) | Model 1 (mandatory) |
| **SUTRA Bridge** | Adapter/federation layer — RTSP, ONVIF, HTTP/HLS, vendor SDK connectors | Model 3 |
| **SUTRA Insight** | AI analytics — ANPR, vehicle detection, cross-camera tracking | Model 2/4 analytics |
| **SUTRA Watch** | Watchlist DB + real-time correlation & alerting | Challenge core |
| **SUTRA Command** | Control-room UI — video wall, alerts, vehicle route timeline on map | Challenge core |

## Repo layout

```
sutra/
├── atlas/      # registry service + GIS (FastAPI + PostGIS)
├── bridge/     # feed adapters & stream gateway (FFmpeg/OpenCV ingestion)
├── insight/    # AI pipeline: detection → plate OCR → track association
├── watch/      # watchlist store + matching engine + alert bus
├── command/    # React frontend: video wall, map, alerts, search
├── scripts/    # dev utilities (feed probe, dataset prep)
├── docs/       # PLAN, ARCHITECTURE (HLD), RECON
└── infra/      # docker-compose, deployment configs
```

## Quick start (current state)

```bash
# one-time: python 3.13 venv + deps
py -3.13 -m venv .venv && .venv/Scripts/pip install -r requirements.txt

# run the backend (Atlas + Bridge + Insight + Watch)
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8000

# run the Command UI (separate terminal) → http://localhost:5173
cd frontend && npm install && npm run dev
```

Then, against `http://127.0.0.1:8000` (interactive docs at `/docs`):

- `POST /api/atlas/discover` — auto-onboard all portal cameras into the registry
- `GET  /api/atlas/cameras` · `GET /api/atlas/gap-analysis` — registry & coverage
- `POST /api/bridge/cameras/{id}/start` — begin live ingestion for a camera
- `GET  /api/bridge/cameras/{id}/snapshot` · `/mjpeg` — latest frame / live preview
- `POST /api/watch/vehicles` — add a plate to the watchlist (alerts wired in Phase B)

## Key dates (2026)

- **29 Aug** — last date to apply / submit
- **30 Aug** — shortlisting
- **1–2 Sep** — hackathon event @ i-Hub Gujarat, Grand Finale + results

See [docs/PLAN.md](docs/PLAN.md) for the day-by-day build plan and submission checklist.
