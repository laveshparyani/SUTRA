"""Edge-side uploader: pushes new metadata to the central tier.

Runs on `edge` (and optionally `full`) nodes. Every `sync_interval_s` it sends
cameras plus any detections/alerts created since the last successful push,
with evidence thumbnails inlined. Bandwidth is a few KB per detection — the
same ~500x reduction over shipping video that the scaling plan claims.

Failures are non-fatal and retried on the next tick: the edge keeps working
(and keeps its own copy) whether or not the centre is reachable.
"""

import base64
import logging
import threading
import time

import httpx

from ..config import settings
from ..db import SessionLocal
from ..models import Alert, Camera, Detection, WatchlistVehicle

log = logging.getLogger("sutra.syncer")

_MAX_BATCH = 200
_MAX_EVIDENCE_BYTES = 400_000     # skip inlining anything unusually large


class Syncer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="edge-syncer")
        self.stop_flag = threading.Event()
        self.last_detection_id = 0
        self.last_alert_id = 0
        self.pushed = {"detections": 0, "alerts": 0}
        self.last_error = ""
        self.last_success_at: float | None = None

    def run(self) -> None:
        log.info("edge syncer started -> %s every %.0fs", settings.central_url, settings.sync_interval_s)
        while not self.stop_flag.wait(settings.sync_interval_s):
            try:
                self.tick()
            except Exception as e:  # never let the uploader kill the edge
                self.last_error = str(e)
                log.warning("sync failed: %s", e)

    # ------------------------------------------------------------------ push

    def _evidence(self, rel_path: str) -> str | None:
        if not rel_path:
            return None
        path = settings.data_dir / rel_path
        try:
            if path.is_file() and path.stat().st_size <= _MAX_EVIDENCE_BYTES:
                return base64.b64encode(path.read_bytes()).decode()
        except OSError:
            pass
        return None

    def tick(self) -> dict | None:
        db = SessionLocal()
        try:
            cameras = [
                {
                    "external_id": c.external_id, "name": c.name, "location": c.location,
                    "department": c.department, "district": c.district, "lat": c.lat, "lon": c.lon,
                    "camera_type": c.camera_type, "ownership": c.ownership,
                    "install_date": c.install_date, "source_type": c.source_type,
                    "codec": c.codec, "container": c.container, "health": c.health,
                    "monitoring": c.monitoring,
                    "last_frame_at": c.last_frame_at.isoformat() if c.last_frame_at else None,
                    "ingest_fps": c.ingest_fps,
                }
                for c in db.query(Camera).all()
            ]

            cam_ext = {c.id: c.external_id for c in db.query(Camera).all()}

            det_rows = (
                db.query(Detection)
                .filter(Detection.id > self.last_detection_id)
                .order_by(Detection.id)
                .limit(_MAX_BATCH)
                .all()
            )
            detections = [
                {
                    "camera_external_id": cam_ext.get(d.camera_id, ""),
                    "ts": d.ts.isoformat(), "object_class": d.object_class,
                    "plate_text": d.plate_text, "plate_conf": d.plate_conf,
                    "det_conf": d.det_conf, "bbox": d.bbox, "track_id": d.track_id,
                    "snapshot_path": d.snapshot_path,
                    "snapshot_b64": self._evidence(d.snapshot_path),
                }
                for d in det_rows
                if cam_ext.get(d.camera_id)
            ]

            alert_rows = (
                db.query(Alert).filter(Alert.id > self.last_alert_id).order_by(Alert.id).limit(_MAX_BATCH).all()
            )
            alerts = []
            for a in alert_rows:
                det = db.get(Detection, a.detection_id)
                entry = db.get(WatchlistVehicle, a.watchlist_id)
                if not det or not entry or not cam_ext.get(det.camera_id):
                    continue
                alerts.append({
                    "plate": entry.plate, "camera_external_id": cam_ext[det.camera_id],
                    "ts": a.ts.isoformat(), "severity": a.severity, "reason": entry.reason,
                    "fir_ref": entry.fir_ref, "status": a.status,
                    "snapshot_path": det.snapshot_path,
                    "snapshot_b64": self._evidence(det.snapshot_path),
                })
        finally:
            db.close()

        if not detections and not alerts and self.last_success_at:
            return None  # nothing new; camera health resyncs on the next change

        r = httpx.post(
            f"{settings.central_url.rstrip('/')}/api/sync/push",
            json={"node": "edge-1", "cameras": cameras, "detections": detections, "alerts": alerts},
            headers={"X-Sync-Key": settings.sync_api_key},
            timeout=60,
        )
        r.raise_for_status()
        if det_rows:
            self.last_detection_id = det_rows[-1].id
        if alert_rows:
            self.last_alert_id = alert_rows[-1].id
        self.pushed["detections"] += len(detections)
        self.pushed["alerts"] += len(alerts)
        self.last_success_at = time.time()
        self.last_error = ""
        result = r.json()
        if any(result.values()):
            log.info("synced -> central: %s", result)
        return result

    def status(self) -> dict:
        return {
            "enabled": True,
            "central_url": settings.central_url,
            "pushed_total": self.pushed,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
        }


syncer = Syncer()
