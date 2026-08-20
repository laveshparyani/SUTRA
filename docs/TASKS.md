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
