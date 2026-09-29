# SUTRA - API reference

Generated from the application's own OpenAPI schema by
`scripts/build_api_reference.py`, so it cannot drift from the code.
Regenerate after changing any route:

```
python scripts/build_api_reference.py
```

Every running instance also serves an interactive version at `/docs` and
the raw schema at `/openapi.json`.

**42 endpoints.** The base URL is the instance root:
`https://sutra-central.onrender.com` for the hosted central tier, or
`http://localhost:8010` for a local edge node.

## Authentication

`POST /api/auth/login` returns a JWT and sets an HttpOnly media cookie.
Send the token as `Authorization: Bearer <token>` on API calls. The cookie
exists because `<img>` tags and WebSocket handshakes cannot carry a header;
it authenticates `/data/...` evidence and the alert socket.

Three roles, enforced server side rather than only in the interface:

| Role | Can |
|---|---|
| `admin` | everything |
| `operator` | everything except user administration, scoped to their department |
| `viewer` | read only - every state-changing endpoint returns 403 |

The sync endpoint uses no session at all. It is authenticated by a shared
`X-Sync-Key` header, because it is called by an edge node rather than by a person.

## Conventions

- Timestamps are ISO-8601. The output report carries both UTC and IST.
- Errors return `{"detail": "..."}` with a conventional status code:
  401 unauthenticated, 403 wrong role, 404 not found, 422 validation.
- List endpoints take `limit`; most also take `hours` to bound the window.
- Evidence images are served from `/data/{path}` and require authentication.

## Authentication

Sign in, sign out and introspect the current session.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/login` | none | Login |
| `POST` | `/api/auth/logout` | none | Logout |
| `GET` | `/api/auth/me` | any signed-in user | Me |

## Registry and GIS (Model 1)

The camera registry: onboarding, metadata, search, export, gap analysis and the audit trail.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/atlas/audit` | any signed-in user | Metadata audit trail (Model 1) — who did what, most recent first. |
| `GET` | `/api/atlas/cameras` | any signed-in user | List Cameras |
| `POST` | `/api/atlas/cameras` | admin or operator | Create Camera |
| `POST` | `/api/atlas/cameras/bulk` | admin or operator | Bulk onboarding via CSV: external_id,name,location,department,lat,lon,source_type,source_url. |
| `GET` | `/api/atlas/cameras/{camera_id}` | any signed-in user | Get Camera |
| `PATCH` | `/api/atlas/cameras/{camera_id}` | admin or operator | Update Camera |
| `POST` | `/api/atlas/discover` | admin or operator | Pull the hackathon portal's camera list and upsert into the registry. |
| `GET` | `/api/atlas/export` | any signed-in user | Model 1 'export': full registry as CSV (respects operator dept scoping). |
| `GET` | `/api/atlas/gap-analysis` | any signed-in user | Model 1 deliverable: coverage & infrastructure gaps by district/department. |

## Feed integration (Model 3)

Live ingest control and the video relay. The scheduler multiplexes cameras through a concurrency budget; these endpoints start, stop and pin streams and expose health.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/bridge/cameras/{camera_id}/mjpeg` | media cookie or bearer | Lightweight live preview: multipart MJPEG built from the sampler's frame cache. |
| `POST` | `/api/bridge/cameras/{camera_id}/pin` | admin or operator | Pin Camera |
| `GET` | `/api/bridge/cameras/{camera_id}/snapshot` | media cookie or bearer | Snapshot |
| `POST` | `/api/bridge/cameras/{camera_id}/start` | admin or operator | Add a camera to the sampling pool; the scheduler assigns it a slot. |
| `POST` | `/api/bridge/cameras/{camera_id}/stop` | admin or operator | Stop Monitoring |
| `POST` | `/api/bridge/cameras/{camera_id}/unpin` | admin or operator | Unpin Camera |
| `GET` | `/api/bridge/scheduler` | any signed-in user | Scheduler Status |
| `POST` | `/api/bridge/start-all` | admin or operator | Pool every camera with a source; the scheduler multiplexes within budget. |
| `GET` | `/api/bridge/status` | any signed-in user | Ingest Status |

## Analytics and trace

Plate reads at three levels of grouping, scene analytics, the vehicle route reconstruction and the output report export.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/insight/analyse` | any signed-in user | Run ANPR on an uploaded image — used for testing and the demo video. |
| `GET` | `/api/insight/analytics` | any signed-in user | Aggregations behind the dashboard charts — computed from stored rows. |
| `GET` | `/api/insight/detections` | any signed-in user | List Detections |
| `GET` | `/api/insight/report` | any signed-in user | Submission artifact: detected number plates with corresponding timestamps. |
| `GET` | `/api/insight/route/{plate}` | any signed-in user | The evaluation feature: full movement history of a registration number. |
| `GET` | `/api/insight/scene` | any signed-in user | Latest person/vehicle counts per monitored camera (YOLOX sidecar). |
| `GET` | `/api/insight/sightings` | any signed-in user | Detections collapsed into vehicle *sightings*. |
| `GET` | `/api/insight/stats` | any signed-in user | Stats |
| `GET` | `/api/insight/vehicles` | any signed-in user | One row per vehicle — the answer to "what have we seen?". |

## Watchlist and alerting

The watchlist registry, the alert queue and its acknowledgement workflow, and government-database correlation.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/watch/alerts` | any signed-in user | List Alerts |
| `GET` | `/api/watch/alerts/episodes` | any signed-in user | Alerts collapsed into *episodes*. |
| `POST` | `/api/watch/alerts/episodes/ack` | admin or operator | Acknowledge every alert in an episode in one action. |
| `POST` | `/api/watch/alerts/{alert_id}/ack` | admin or operator | Ack Alert |
| `GET` | `/api/watch/vehicle-info/{plate}` | any signed-in user | Government-DB correlation: vehicle details by registration number. |
| `GET` | `/api/watch/vehicles` | any signed-in user | List Watchlist |
| `POST` | `/api/watch/vehicles` | admin or operator | Add Watchlist |
| `DELETE` | `/api/watch/vehicles/{entry_id}` | admin or operator | Remove Watchlist |

## Edge to central sync

The federation boundary. Mounted **only when `SUTRA_ROLE=central`**.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/sync/push` | `X-Sync-Key` header | Idempotent upsert of edge metadata into the central store. |

## Service and media

Not part of a feature area: liveness, runtime introspection and the
authenticated evidence store.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | none | Health |
| `GET` | `/api/system` | media cookie or bearer | Operational view of every background task on this node. |
| `GET` | `/data/{rel_path}` | media cookie or bearer | Serve detection/alert imagery. |

## Worked example

Sign in, then export the output report:

```bash
TOKEN=$(curl -s -X POST http://localhost:8010/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}' | jq -r .token)

curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8010/api/insight/report?since=2026-09-26T00:00:00Z' \
  -o output_report.csv
```
