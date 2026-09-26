# Contributing to SUTRA

SUTRA is a CCTV integration and video-analytics platform built for the Gujarat
Police CCTV Integration Hackathon 2026. It is intended for real deployment, so
the bar for a change is the bar for something that would run in a police
control room.

## Ground rules

**Verify against the running system, not just the tests.** The single most
expensive lesson in this project's history: the API-level checks all passed
while the UI was visibly broken, and a whole class of bugs — a stale Postgres
schema, a dataset that never reached the deployed image, a model file absent
from every fresh clone — were green locally and wrong in production. If a
change is observable in the UI or on the hosted tier, drive it there before
calling it done.

**Say what is true in the interface.** A frozen video tile is not "Live". A
fuzzy number-plate match is not a confirmed identification. An empty grid
because a request failed is not "no cameras onboarded". Operators act on what
this system tells them; the UI states uncertainty rather than hiding it.

**No secrets in the repository, ever.** Portal credentials, signing keys and
sync tokens live in `backend/.env`, which is gitignored. CI runs a
full-history secret scan on every push and will fail the build.

## Getting set up

```bash
git clone https://github.com/laveshparyani/SUTRA && cd SUTRA
py -3.13 -m venv .venv
.venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
cd frontend && npm install && cd ..
```

FFmpeg 9+ must be on `PATH`. Create `backend/.env` from the keys listed in
`docs/HANDOFF.md`; without `SUTRA_PORTAL_EMAIL` / `SUTRA_PORTAL_PASSWORD`,
camera discovery returns 502 and no feed will stream.

Run both dev servers from `.claude/launch.json` (`sutra-api` on 8010,
`sutra-command` on 5173), or by hand:

```bash
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8010
npm run dev --prefix frontend
```

## Before you open a pull request

```bash
cd backend && ../.venv/Scripts/python -m pytest -q   # 174 tests, all must pass
npm run build --prefix frontend                       # must build clean
```

CI additionally runs a dependency audit and a secret scan. All four jobs must
be green; `main` is protected and requires them.

## How the codebase is organised

The backend is one FastAPI application, not microservices — deliberately, so
the whole platform fits on a small edge node.

| Area | Where | What lives there |
|---|---|---|
| **Atlas** | `routers/atlas.py` | registry, GIS metadata, gap analysis, audit |
| **Bridge** | `services/sampler.py`, `ffreader.py`, `portal.py`, `scheduler.py` | source adapters, ingest scheduling, portal auth |
| **Insight** | `services/anpr.py`, `insight.py`, `objects.py` | plate detection, OCR, temporal voting, scene analytics |
| **Watch** | `routers/watch.py`, `connectors/` | watchlist matching, alerting, government-DB connectors |
| **Command** | `frontend/src/` | React + Leaflet control-room UI |

## Commit and branch conventions

- Branch from `dev`; open pull requests into `dev`. `dev` → `main` is the
  release path, and `main` auto-deploys the hosted tier.
- Write commit subjects in the imperative and explain **why** in the body —
  the reasoning is the part that is expensive to reconstruct later. Several
  comments in this codebase record a measurement (48 s to first frame, ~5 Mbps
  per client IP) precisely so nobody re-derives it.
- Delete the feature branch after it merges.

## Reporting problems

Use the issue templates. For anything with a security dimension, follow
[SECURITY.md](.github/SECURITY.md) instead of opening a public issue.
