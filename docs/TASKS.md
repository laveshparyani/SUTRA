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
| D3 | HLD document | ✅ drafted | docs/HLD.md — all required sections incl. measured numbers, 80k sizing, costs; convert to PDF at submission |
| D4 | Record own-feed demo video (2-3 min) | ⬜ pending | Lavesh records per script; system stays demo-ready |
| D5 | Record government-feed demo video | ⬜ pending | record around Camera 7 while portal healthy |
| D6 | Solution Presentation (PPT/PDF) | ⬜ pending | build from HLD §1-2 + demo assets |
| D7 | Scalability plan doc | ✅ folded into HLD §8 | expand to standalone if guidelines require |
| D8 | Hosting + judge credentials (Cloudflare Tunnel) | ⬜ pending | free tier; admin/operator/viewer creds ready |
| D9 | Final submission package (links, YouTube unlisted, repo public) | ⬜ pending | checklist in official Step 5 |
