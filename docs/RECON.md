# Recon: live.sentinelgujarat.in (as of 18 Aug 2026)

Findings from probing the hackathon's live feed portal.

## Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /api/cameras` | `{"cameras": [...]}` — id, number, name, location, codec, container, status, delivery |
| `GET /api/prepare/status` | `{"done": bool, "cameras": [...]}` — server-side prep state (`waiting → remuxing/transcoding → hls → done`) |
| `GET /stream/{id}` | **Progressive HTTP video stream** (the `<video src>` used by their player) |
| `GET /camera/{id}` | Player page for one camera (loads `hls.min.js`, so HLS is a fallback path) |

## Camera inventory (31 live today; portal promises ~50 for evaluation)

- Mostly `h264/mp4`, some `h264/mkv` (cams 13–16), some `avi` (cams 6, 22) — **deliberate container heterogeneity** to test our adapter layer.
- All `delivery: "progressive"`, `status: "live"`.
- Locations span Ahmedabad (Chiman bhai Bridge, Janpath, Paldi, Visat), Junagadh (5+ cams), Gir Somnath, Rajkot, Navsari (gram panchayat), Patan, Dehgam, Bilimora, Gandhidham — matches the "5 departments, geographically dispersed" story.

## Implications for SUTRA Bridge

1. Ingestion is straightforward: `ffmpeg -i https://live.sentinelgujarat.in/stream/{id}` (or OpenCV `VideoCapture` on the URL) works for progressive HTTP.
2. Build the adapter interface around *source types*: `http-progressive`, `hls`, `rtsp`, `onvif`, `file`. The evaluation may add RTSP sources — Model 3's adapter/plugin story requires supporting more than what's live today.
3. `container`/`codec` fields per camera let us demo "heterogeneous onboarding" — normalize everything to one internal format (e.g., raw frames or fMP4) at the Bridge boundary.
4. Poll `/api/cameras` for auto-discovery → bulk-onboard into Atlas registry via API (Model 1 deliverable: "API-based camera onboarding").

## Ingest test results (18 Aug, SUTRA Bridge v0.1)

- **mp4 cameras (1, 2, 4): flowing.** Progressive HTTP opens in OpenCV/FFmpeg after ~15–40 s
  of probing; occasional `read failed` → auto-reconnect works, frames resume.
- **mkv camera (13): flowing** — no special handling needed.
- **avi camera (6): portal returns HTTP 5XX on `/stream/6`** — their side (`/api/prepare/status`
  reports `done: false`). Our worker retries every 5 s and will self-heal when they fix it.
  Re-test avi cameras (6, 22) before the evaluation.
- Streamed footage is timestamped June 2026 — recorded feeds replayed as simulated live.
  Camera 1 overlay: `Chiman bhai Bridge CSITMS-32_PTZ2` (Ahmedabad ITMS PTZ camera, 1080p).
- Night footage on several cameras → ANPR must be tuned for low-light/headlight-glare plates.

## Stress test (18 Aug, 31 concurrent streams)

- Commanded all 31 cameras simultaneously: only ~9 ever flowed; the rest got
  connection failures/EOFs. Meanwhile our machine sat at 25% CPU / 3.6 Mbps down,
  and a fresh single-stream fetch ALSO failed during the load.
- **Conclusion: the portal caps out at roughly 8–10 concurrent streams** (their
  Python middleware, not our stack, is the limit). At 8 cameras everything is
  stable and healthy.
- Evaluation-day implication: assume constrained concurrency. Build/present an
  **adaptive ingest scheduler**: connect in staggered batches, time-multiplex
  cameras beyond the concurrency budget, prioritise cameras near recent
  watchlist hits. This doubles as the bandwidth-optimisation bonus story.
- Our per-stream ingest+ANPR cost is trivial (i7 at 25% with 9 streams + UI +
  inference) — CPU sizing for the HLD can safely claim ~25-40 cameras per
  commodity core-heavy node at 1 fps sampling.

## Local sample dataset

`CCTV Control Room/` — 3 MP4s (~1.4–11 GB): Chinman Bridge, Janpath, Paldi Circle.
Use for offline ANPR development so we don't hammer the live portal.
