"""Edge → central metadata channel.

The central tier never sees video. Edge nodes run ingest and inference locally
and push only what the command centre needs: camera metadata, plate
detections, watchlist alerts and evidence thumbnails. This is the same
"metadata flows up, video stays down" contract the HLD proposes for the
statewide rollout — the hosted deployment is a working instance of it, not a
mock of it.

Authentication is a shared API key (`SUTRA_SYNC_API_KEY`) presented as
`X-Sync-Key`, compared in constant time. The endpoint is only mounted when the
node is running as `central`.
"""

import base64
import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Alert, AuditLog, Camera, Detection, Evidence, WatchlistVehicle

log = logging.getLogger("sutra.sync")
router = APIRouter(prefix="/api/sync", tags=["sync"])


def require_sync_key(x_sync_key: str = Header(None)) -> None:
    if not settings.sync_api_key:
        raise HTTPException(503, "sync channel not configured on this node")
    if not x_sync_key or not hmac.compare_digest(x_sync_key, settings.sync_api_key):
        raise HTTPException(401, "invalid sync key")


class CameraIn(BaseModel):
    external_id: str
    name: str = ""
    location: str = ""
    department: str = "Unassigned"
    district: str = ""
    lat: float | None = None
    lon: float | None = None
    camera_type: str = ""
    ownership: str = "government"
    install_date: str = ""
    source_type: str = ""
    codec: str = ""
    container: str = ""
    health: str = "unknown"
    monitoring: bool = False
    last_frame_at: datetime | None = None
    ingest_fps: float | None = None


class DetectionIn(BaseModel):
    camera_external_id: str
    ts: datetime
    object_class: str = "vehicle"
    plate_text: str | None = None
    plate_conf: float | None = None
    det_conf: float | None = None
    bbox: str = ""
    track_id: str | None = None
    snapshot_path: str = ""
    snapshot_b64: str | None = None      # evidence thumbnail, inlined


class AlertIn(BaseModel):
    plate: str
    camera_external_id: str
    ts: datetime
    severity: str = "high"
    reason: str = "stolen"
    fir_ref: str = ""
    status: str = "new"
    snapshot_path: str = ""
    snapshot_b64: str | None = None


class SyncPayload(BaseModel):
    node: str = "edge"
    cameras: list[CameraIn] = []
    detections: list[DetectionIn] = []
    alerts: list[AlertIn] = []


def _store_evidence(db: Session, rel_path: str, b64: str | None) -> str:
    """Persist an inlined thumbnail in the database.

    Deliberately not the filesystem: the central tier's disk is ephemeral, so
    a redeploy would silently turn every alert into a broken image.
    """
    if not b64 or not rel_path:
        return rel_path or ""
    if db.query(Evidence.id).filter(Evidence.path == rel_path).first():
        return rel_path
    try:
        blob = base64.b64decode(b64)
    except Exception:
        log.warning("undecodable evidence for %s", rel_path)
        return ""
    db.add(Evidence(path=rel_path, content=blob, size_bytes=len(blob)))
    return rel_path


@router.post("/push", dependencies=[Depends(require_sync_key)])
def push(payload: SyncPayload, db: Session = Depends(get_db)):
    """Idempotent upsert of edge metadata into the central store."""
    cam_ids: dict[str, int] = {}
    cams_new = 0
    for c in payload.cameras:
        cam = db.query(Camera).filter(Camera.external_id == c.external_id).one_or_none()
        if cam is None:
            cam = Camera(external_id=c.external_id, source_url="")   # central holds no stream URLs
            db.add(cam)
            cams_new += 1
        for field, value in c.model_dump(exclude={"external_id"}).items():
            setattr(cam, field, value)
        db.flush()
        cam_ids[c.external_id] = cam.id

    def resolve(ext_id: str) -> int | None:
        if ext_id in cam_ids:
            return cam_ids[ext_id]
        cam = db.query(Camera).filter(Camera.external_id == ext_id).one_or_none()
        if cam:
            cam_ids[ext_id] = cam.id
            return cam.id
        return None

    dets_new = 0
    for d in payload.detections:
        cid = resolve(d.camera_external_id)
        if cid is None:
            continue
        exists = (
            db.query(Detection.id)
            .filter(Detection.camera_id == cid, Detection.ts == d.ts, Detection.plate_text == d.plate_text)
            .first()
        )
        if exists:
            continue
        db.add(
            Detection(
                camera_id=cid,
                ts=d.ts,
                object_class=d.object_class,
                plate_text=d.plate_text,
                plate_conf=d.plate_conf,
                det_conf=d.det_conf,
                bbox=d.bbox,
                track_id=d.track_id,
                snapshot_path=_store_evidence(db, d.snapshot_path, d.snapshot_b64),
            )
        )
        dets_new += 1

    alerts_new = 0
    for a in payload.alerts:
        cid = resolve(a.camera_external_id)
        if cid is None:
            continue
        entry = db.query(WatchlistVehicle).filter(WatchlistVehicle.plate == a.plate).one_or_none()
        if entry is None:
            entry = WatchlistVehicle(plate=a.plate, reason=a.reason, fir_ref=a.fir_ref, added_by="edge-sync")
            db.add(entry)
            db.flush()
        det = Detection(
            camera_id=cid,
            ts=a.ts,
            plate_text=a.plate,
            snapshot_path=_store_evidence(db, a.snapshot_path, a.snapshot_b64),
        )
        db.add(det)
        db.flush()
        if not db.query(Alert.id).filter(Alert.watchlist_id == entry.id, Alert.ts == a.ts).first():
            db.add(Alert(detection_id=det.id, watchlist_id=entry.id, ts=a.ts,
                         severity=a.severity, status=a.status))
            alerts_new += 1

    result = {"cameras_new": cams_new, "detections_new": dets_new, "alerts_new": alerts_new}
    db.add(AuditLog(actor=f"edge:{payload.node}", action="sync.push", detail=str(result)))
    db.commit()
    return result
