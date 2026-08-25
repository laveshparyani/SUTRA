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
# Total inlined evidence per request. Without this, a batch of 200 detections
# each carrying a ~7 KB thumbnail is a multi-megabyte POST that the central
# tier (512 MB, free instance) answers with a 500 — and because the cursor only
# advances on success, the same oversized batch is retried forever. Rows beyond
# the budget simply wait for the next tick; the cursor advances to the last row
# actually sent.
_MAX_BATCH_EVIDENCE_BYTES = 600_000


class Syncer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="edge-syncer")
        self.stop_flag = threading.Event()
        # The cursor survives restarts. It used to live only in memory, so
        # every backend restart reset it to 0 and the syncer re-sent the entire
        # detection history — hundreds of evidence-bearing rows straight into
        # the batch-size failure above, as a 500 crash-loop every 30 s.
        self.last_detection_id, self.last_alert_id = self._load_cursor()
        self.pushed = {"detections": 0, "alerts": 0}
        self.last_error = ""
        self.last_success_at: float | None = None

    # ---------------------------------------------------------------- cursor

    @property
    def _cursor_file(self):
        return settings.data_dir / ".sync_cursor"

    def _load_cursor(self) -> tuple[int, int]:
        try:
            det, al = self._cursor_file.read_text().split()
            return int(det), int(al)
        except (OSError, ValueError):
            return 0, 0

    def _save_cursor(self) -> None:
        try:
            self._cursor_file.write_text(f"{self.last_detection_id} {self.last_alert_id}")
        except OSError:
            log.warning("could not persist sync cursor")

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

            evidence_budget = _MAX_BATCH_EVIDENCE_BYTES

            det_rows = (
                db.query(Detection)
                .filter(Detection.id > self.last_detection_id)
                .order_by(Detection.id)
                .limit(_MAX_BATCH)
                .all()
            )
            detections, det_sent = [], []
            for d in det_rows:
                if not cam_ext.get(d.camera_id):
                    det_sent.append(d)   # unroutable rows never become sendable; skip past them
                    continue
                b64 = self._evidence(d.snapshot_path)
                if b64 and len(b64) > evidence_budget:
                    break                # budget spent — this row leads the next tick's batch
                if b64:
                    evidence_budget -= len(b64)
                det_sent.append(d)
                detections.append({
                    "camera_external_id": cam_ext[d.camera_id],
                    "ts": d.ts.isoformat(), "object_class": d.object_class,
                    "plate_text": d.plate_text, "plate_conf": d.plate_conf,
                    "det_conf": d.det_conf, "bbox": d.bbox, "track_id": d.track_id,
                    "snapshot_path": d.snapshot_path,
                    "snapshot_b64": b64,
                })

            alert_rows = (
                db.query(Alert).filter(Alert.id > self.last_alert_id).order_by(Alert.id).limit(_MAX_BATCH).all()
            )
            alerts, alert_sent = [], []
            for a in alert_rows:
                det = db.get(Detection, a.detection_id)
                entry = db.get(WatchlistVehicle, a.watchlist_id)
                if not det or not entry or not cam_ext.get(det.camera_id):
                    alert_sent.append(a)
                    continue
                b64 = self._evidence(det.snapshot_path)
                if b64 and len(b64) > evidence_budget:
                    break
                if b64:
                    evidence_budget -= len(b64)
                alert_sent.append(a)
                alerts.append({
                    "plate": entry.plate, "camera_external_id": cam_ext[det.camera_id],
                    "ts": a.ts.isoformat(), "severity": a.severity, "reason": entry.reason,
                    "fir_ref": entry.fir_ref, "status": a.status,
                    "snapshot_path": det.snapshot_path,
                    "snapshot_b64": b64,
                })
        finally:
            db.close()

        if not detections and not alerts and self.last_success_at:
            # nothing sendable — but rows skipped as unroutable still advance
            # the cursor, or they would be re-queried on every tick forever
            if det_sent:
                self.last_detection_id = det_sent[-1].id
            if alert_sent:
                self.last_alert_id = alert_sent[-1].id
            if det_sent or alert_sent:
                self._save_cursor()
            return None

        r = httpx.post(
            f"{settings.central_url.rstrip('/')}/api/sync/push",
            json={"node": "edge-1", "cameras": cameras, "detections": detections, "alerts": alerts},
            headers={"X-Sync-Key": settings.sync_api_key},
            timeout=60,
        )
        r.raise_for_status()
        # advance only past what was actually in this request, not the whole
        # query window — budget-deferred rows must lead the next batch
        if det_sent:
            self.last_detection_id = det_sent[-1].id
        if alert_sent:
            self.last_alert_id = alert_sent[-1].id
        self._save_cursor()
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
