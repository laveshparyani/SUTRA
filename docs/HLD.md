# SUTRA — High-Level Design (Technical Proposal)

**Statewide Unified Tracking, Registry & Analytics**
Gujarat Police CCTV Integration Hackathon 2026 · Category 1 (Individual) · Lavesh Paryani
Working platform: https://github.com/laveshparyani/SUTRA (all open-source)

---

## 1. Solution model and justification

**Hybrid: Model 1 (Registry & GIS Foundation) + Model 3 (Federation Middleware),**
with metadata-first analytics in the spirit of Model 2 and selective Model 4
capabilities (central analytics, tiered evidence storage) where they earn their cost.

Why this hybrid:

- **Model 1 is mandatory** and is genuinely load-bearing here: every downstream
  function (scheduling, alerts, route reconstruction, gap analysis) keys off
  registry metadata.
- **Model 3 over Model 2** because 26 departments will never converge on one
  VMS: an adapter/connector layer that federates *sources* (RTSP, ONVIF,
  HTTP/HLS, vendor SDKs, files) and *databases* (VAHAN, eGujCop…) behind stable
  interfaces is the only architecture that survives vendor churn. Departments
  keep their infrastructure and control.
- **Not Model 4** as the primary posture: centralising 80,000 video streams is
  a bandwidth and cost trap (see section 8). SUTRA centralises *metadata and
  evidence*, not video. Recording stays at the department/edge tier; the centre
  stores detections, alerts, thumbnails and audit — kilobytes per camera-minute
  instead of megabits per second.

## 2. Architecture

```
+--------------------------------------------------------------------+
|                     SUTRA COMMAND  (React + Leaflet)               |
|  overview map · video wall · vehicle trace · alerts · registry ·   |
|  coverage/gap analysis · watchlist · audit                         |
+--------------^-----------------------------^-----------------------+
               | REST (JWT, RBAC)            | WebSocket (alerts)
+--------------+-----------+  +--------------+-----------------------+
|       SUTRA ATLAS        |  |            SUTRA WATCH               |
| registry · GIS · health  |  | watchlist · fuzzy matcher · alerts   |
| gap/ageing analysis ·    |  | gov-DB connectors (VAHAN/SARTHI/     |
| bulk/API onboarding ·    |  | eGujCop/AFIS — adapter interface)    |
| CSV export · audit trail |  +--------------^-----------------------+
+--------------^-----------+                 | detections
               | metadata    +---------------+-----------------------+
               |             |           SUTRA INSIGHT               |
               |             | ANPR: plate det (YOLOv9-t ONNX) ->    |
               |             | OCR (CCT ONNX) -> temporal voting ->  |
               |             | Indian-plate normalisation/state-code |
               |             | repair · scene analytics (YOLOX-nano) |
               |             | · route reconstruction                |
               |             +---------------^-----------------------+
               |                             | sampled frames
+--------------+-----------------------------+-----------------------+
|                        SUTRA BRIDGE                                |
| source adapters: http-progressive · RTSP(TCP) · file · HLS/ONVIF   |
| adaptive ingest scheduler (concurrency budget, dwell rotation,     |
| pinning, alert-boost) · health probes · MJPEG relay (shared)       |
+--------------^-----------------------------------------------------+
               |
   26 departments' cameras/VMS/NVRs · private/society feeds (RTSP)
```

**Verified in the working platform (not proposed — running):** every box above
exists and was demonstrated on the hackathon portal's live feeds and local
footage. Detection at 30–75 ms/frame and scene analytics at 43 ms/frame on a
single CPU (no GPU present in the build machine).

## 3. Heterogeneous integration approach

- **Source adapters.** One ingest worker abstraction over FFmpeg
  (`http-progressive`, `rtsp` — forced TCP transport after field-testing showed
  RTP-over-UDP silently dropped by firewalls — `file`, HLS-ready). Container and
  codec heterogeneity (mp4/mkv/avi, H.264/HEVC) is handled by the decode layer;
  workers discard mid-GOP joins (HEVC corruption), auto-reconnect with backoff,
  and report per-camera health honestly (`connecting` is not `ok`;
  `last_frame_at` advances only on decoded frames).
- **VMS federation.** Vendor VMS/NVR systems integrate through the same adapter
  contract (discover / probe / open_stream / health); ONVIF Profile S/T and
  vendor SDK adapters are additive modules, no core change. The hackathon
  dataset itself carries Genetec VMS provenance — consumed without any Genetec
  software.
- **Onboarding paths (Model 1):** portal API auto-discovery, single-camera API,
  bulk CSV (tested with private/society cameras), manual UI. All audited.

## 4. Geographic dispersion and the ingest scheduler

Statewide links are constrained and shared. SUTRA treats stream concurrency as
a budgeted resource:

- **Adaptive ingest scheduler:** live connections are capped by a per-node
  budget; cameras beyond it rotate through slots (dwell timer,
  least-recently-served fairness, staggered connects). Operators **pin**
  cameras; a watchlist hit **boosts** the alert camera *and its nearest
  neighbours* to resident slots — coverage tightens around a sighting instead
  of rotating away from it.
- Field-measured on the hackathon portal (which sustains ~8–10 concurrent
  streams): budget respected, rotation verified, boost verified end-to-end.
- Viewing is relayed (one ingest connection serves all viewers via MJPEG/WebRTC
  relay), never fanned out to sources.

## 5. AI-powered video analytics

| Capability | Implementation (all open-source, CPU-proven) |
|---|---|
| Plate detection | YOLOv9-tiny 640 (ONNX), 8 MB |
| Plate OCR | CCT-S v2 (ONNX), 5 MB, per-character probabilities |
| Accuracy layer | **Temporal voting** (per-vehicle track, char-level probability vote) + **Indian-plate normalisation** (structure-aware confusion repair, state-code validation against the official code list) + fuzzy watchlist matching (confusion-fold + edit distance) |
| Scene analytics | YOLOX-nano (ONNX): person/vehicle counts per camera (crowd and intrusion rules build on this) |
| Route reconstruction | Detections grouped into sightings per camera, time-ordered, rendered as GIS polyline + timeline with evidence |
| FRS (roadmap) | Same sidecar pattern: face detection (SCRFD) + embedding (ArcFace ONNX) matched against eGujCop/AFIS-fed galleries; flagged-candidate → human-confirmation workflow, never automatic identification |

Honest performance characterisation from real footage: close-range cameras
(toll gates, showroom approaches) read at 0.81–0.98 confidence; wide-angle
intersection PTZs yield partial reads (50–90 px plates) that the voting and
fuzzy layers absorb. Two-line commercial plates produce OCR variants — the
watchlist supports investigator-registered variants under one FIR.

## 6. Watchlist correlation and alerting

- Representative watchlist DB (stolen / blacklisted / suspect / wanted) with
  FIR references and priorities; production sources map 1:1 from eGujCop/CCTNS.
- Every finalised read is matched (exact → entry's priority severity; fuzzy
  "probable" → one severity lower). Alert → DB row + **WebSocket push** to all
  operators (toast + alert centre), annotated evidence frame, VAHAN-connector
  vehicle details, acknowledge workflow, 15-minute per-plate/camera cooldown,
  full audit.
- An alert also triggers the scheduler boost (section 4) — the system reacts
  operationally, not just visually.

## 7. Cybersecurity, privacy, auditability

- JWT auth (PBKDF2-hashed credentials); RBAC: admin / department operator
  (department-scoped data visibility, enforced server-side) / viewer.
- Append-only audit trail of logins, onboarding, exports, watchlist changes,
  acknowledgements — surfaced in the UI.
- Privacy by design: no continuous central video recording;
  watchlist-match-only alerting; evidence retention policy; owner names masked
  in connector responses.
- Production hardening (documented; partially relaxed in the sandbox): TLS
  everywhere, mTLS on federation links, media endpoints behind signed URLs,
  secrets in a vault, network segmentation (ingest DMZ / analytics / data
  planes), SIEM export.

## 8. Scalability to ~80,000 cameras

**Design principle: video stays at the edge; metadata flows up.**

- **Edge tier (district/zone, ~150 nodes):** ingest + ANPR on commodity
  servers. Measured: 30–75 ms/frame/core CPU-only ⇒ a 32-core node handles
  **300–500 cameras at 1 fps sampling**; one mid-range GPU (T4-class) raises
  that to ~1,500–2,500. 80k cameras ⇒ ~160–260 CPU nodes *or* ~40–60 GPU nodes.
- **Uplink per camera ≈ 2–6 KB/s** (detections + thumbnails) versus 2–4 Mb/s
  for video — a **~500× bandwidth reduction**; a district of 500 cameras
  federates over ~25 Mb/s. Full-video recall stays departmental (existing NVR
  retention: 7–15+ days as today).
- **Regional tier (6–8):** Kafka event bus, PostgreSQL + PostGIS (partitioned /
  Timescale), S3-compatible object store for evidence (hot 30 d / warm 180 d /
  cold archive per retention policy).
- **Central tier:** federation control plane, registry, search, command centre,
  gov-DB connectors. Kubernetes; horizontal scale-out; HA per tier; DR by
  cross-region replication of metadata + evidence (video DR remains
  departmental).
- **Load and health:** the prototype's scheduler/health model is the same
  control loop that governs edge nodes at scale; Prometheus/Grafana monitoring,
  structured logging, per-camera health as first-class data.
- **Indicative cost (edge CPU option):** ~₹2.4–3.6 L/node × 160–260 nodes ≈
  **₹40–75 Cr capex** + network; GPU option ≈ ₹55–90 Cr with 4× analytics
  headroom — an order of magnitude under centralised-video designs, because the
  state pays for inference, not for hauling video.

## 9. Department prerequisites (integration feasibility)

Per department: camera/NVR inventory with RTSP/ONVIF endpoints or VMS API +
credentials; network reachability to the district edge node (or a 4G/leased
uplink); storage/retention declaration for the registry; a nodal officer for
credential rotation. For databases: NIC/SCRB API access to VAHAN / SARTHI /
eGujCop with IP allow-listing (connector contract in docs/CONNECTORS.md).

## 10. Roadmap

- **Phase 1 (now):** this platform.
- **Phase 2:** FRS + AFIS confirmation loop, ONVIF auto-discovery, Kafka bus,
  PostGIS migration.
- **Phase 3:** statewide rollout per section 8 tiers, eGujCop-fed watchlists,
  public/private feed onboarding portal.
