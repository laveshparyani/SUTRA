"""SUTRA Bridge — ingest control, snapshots, MJPEG relay (Model 3 adapter layer)."""

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from fastapi import Request

from ..db import get_db
from ..models import Camera, User
from ..security import current_user, require_roles, verify_media_access
from ..services import sampler
from ..services.scheduler import engine as scheduler

router = APIRouter(prefix="/api/bridge", tags=["bridge"])


@router.get("/status")
def ingest_status(user: User = Depends(current_user)):
    return {"workers": sampler.worker_status(), "scheduler": scheduler.status()}


@router.get("/scheduler")
def scheduler_status(user: User = Depends(current_user)):
    return scheduler.status()


@router.post("/cameras/{camera_id}/start")
def start_monitoring(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    """Add a camera to the sampling pool; the scheduler assigns it a slot."""
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "camera not found")
    if not cam.source_url:
        raise HTTPException(400, "camera has no source_url")
    cam.monitoring = True
    db.commit()
    return {"camera_id": camera_id, "pooled": True}


@router.post("/cameras/{camera_id}/stop")
def stop_monitoring(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "camera not found")
    cam.monitoring = False
    db.commit()
    sampler.stop_worker(camera_id)  # immediate; scheduler would also catch it next tick
    scheduler.unpin(camera_id)
    return {"camera_id": camera_id, "pooled": False}


@router.post("/cameras/{camera_id}/pin")
def pin_camera(camera_id: int, user: User = Depends(require_roles("admin", "operator"))):
    scheduler.pin(camera_id)
    return {"camera_id": camera_id, "pinned": True}


@router.post("/cameras/{camera_id}/unpin")
def unpin_camera(camera_id: int, user: User = Depends(require_roles("admin", "operator"))):
    scheduler.unpin(camera_id)
    return {"camera_id": camera_id, "pinned": False}


@router.post("/start-all")
def start_all(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    """Pool every camera with a source; the scheduler multiplexes within budget."""
    cams = db.query(Camera).filter(Camera.source_url != "").all()
    for cam in cams:
        cam.monitoring = True
    db.commit()
    return {"pooled": len(cams), "budget": scheduler.status()["budget"]}


@router.get("/cameras/{camera_id}/snapshot")
def snapshot(camera_id: int, request: Request, preview: bool = False):
    if not verify_media_access(request):
        raise HTTPException(401, "not authenticated")
    latest = sampler.get_latest_frame(camera_id, preview=preview)
    if latest is None:
        raise HTTPException(404, "no frame available yet — is monitoring started?")
    jpg, _ts = latest
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/cameras/{camera_id}/mjpeg")
async def mjpeg(camera_id: int, request: Request, preview: bool = False):
    """Lightweight live preview: multipart MJPEG built from the sampler's frame cache.

    Serves the video wall without per-viewer transcoding — many viewers share
    one ingest connection per camera.
    """
    if not verify_media_access(request):
        raise HTTPException(401, "not authenticated")

    async def gen():
        last_sent = 0.0
        while True:
            latest = sampler.get_latest_frame(camera_id, preview=preview)
            if latest and latest[1] != last_sent:
                jpg, last_sent = latest
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
