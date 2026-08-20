# SUTRA — High-Level Design (working draft)

Hybrid architecture: **Model 1 (Registry & GIS foundation) + Model 3 (Federation middleware)**,
with Model 2/4-style analytics running on federated streams. This is the skeleton that
becomes the submitted HLD document.

## System overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SUTRA COMMAND (React)                       │
│   video wall · GIS map · vehicle search/route · alerts · health      │
└───────────────▲──────────────────────────────▲──────────────────────┘
                │ REST / WebSocket             │
┌───────────────┴───────────┐   ┌──────────────┴───────────────────────┐
│        SUTRA ATLAS        │   │            SUTRA WATCH               │
│  camera registry (CRUD,   │   │  watchlist DB · matcher · alert bus  │
│  bulk/API onboarding)     │   │  (stolen/blacklisted vehicles,       │
│  PostGIS · gap analysis   │   │   wanted/missing persons)            │
└───────────────▲───────────┘   └──────────────▲───────────────────────┘
                │ metadata                     │ detections (plate, ts, cam)
┌───────────────┴───────────────────────────────┴──────────────────────┐
│                         SUTRA INSIGHT                                │
│   vehicle detection (YOLO/OpenVINO) → plate OCR → normalisation      │
│   → cross-camera track association                                   │
└───────────────────────────────▲──────────────────────────────────────┘
                                │ sampled frames / streams (Redis→Kafka)
┌───────────────────────────────┴──────────────────────────────────────┐
│                          SUTRA BRIDGE                                │
│   adapter framework: http-progressive · HLS · RTSP · ONVIF ·         │
│   vendor SDK · file — normalises heterogeneous sources               │
│   stream relay (WebRTC/HLS out) · health probes                      │
└───────────────────────────────▲──────────────────────────────────────┘
                                │
        26 departments' VMS / NVRs / cameras (+ private feeds where permitted)
```

## Design principles (mirrors the official architecture principles)

- **Vendor-neutral, adapter-based**: every source type is a plugin implementing
  `discover() / probe() / open_stream() / health()`. New vendor = new adapter, no core change.
- **Metadata-first federation** (Model 3): departments keep their VMS and storage;
  SUTRA pulls streams/metadata, never replaces infrastructure.
- **Event bus decoupling**: detections and alerts flow over a message bus
  (Redis Streams in prototype → Kafka at scale) so analytics, matching, and UI scale independently.
- **No mass central recording** in the prototype: store *metadata + evidence snapshots*
  (detection thumbnails), which is also the honest 80k-camera bandwidth answer.

## Data model (core tables)

- `cameras` — id, dept, name, lat/lon (PostGIS point), source_type, source_url, codec,
  status, storage_type, retention_days, install_date, health fields
- `detections` — id, camera_id, ts, class, plate_text, plate_conf, bbox, snapshot_path, track_id
- `watchlist_vehicles` — plate, reason (stolen/blacklisted/suspect), fir_ref, priority, added_by
- `watchlist_persons` — (photo embedding for FRS if attempted), name, reason
- `alerts` — id, detection_id, watchlist_id, ts, severity, status (new/ack/closed), acked_by
- `users` / `roles` — RBAC: admin, dept-operator (sees own dept cams), viewer, auditor
- `audit_log` — who viewed/searched/exported what, when

## Vehicle route reconstruction (demo-day feature)

1. Query `detections` by normalised plate (fuzzy: Levenshtein ≤1 with char-confusion map).
2. Order by ts, join camera lat/lon → sequence of (location, time) sightings.
3. Render polyline on Leaflet map + timeline strip with snapshots; export as PDF report.

## Government DB integration readiness (VAHAN, SARTHI, eGujCop, AFIS/NAFIS)

Prototype uses representative watchlist tables shaped like the real sources; a
`connectors/` interface documents the intended API contract (e.g., VAHAN vehicle-details
lookup by plate) so production integration is a connector swap, not a redesign.

## Security architecture (summary — expand in HLD)

- TLS everywhere; streams relayed, never exposing department source URLs to clients
- JWT auth + RBAC + per-department data scoping; full audit trail
- Network segmentation: Bridge in DMZ-ish ingest zone; DB private
- Privacy: watchlist-match-only alerting, snapshot retention policy, purpose limitation

## Scale path to ~80,000 cameras (summary — expand in HLD)

- **Edge tier**: district-level ingest+inference nodes (GPU boxes) sampling frames locally,
  shipping only metadata + thumbnails upstream (≈ KB/s per camera instead of Mb/s)
- **Regional tier**: Kafka clusters + object storage (evidence), per-region analytics
- **Central tier**: federation control plane, registry, search, command centre
- Sizing math, bandwidth budget, storage tiers, HA/DR → dedicated HLD section
