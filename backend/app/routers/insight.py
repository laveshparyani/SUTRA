"""SUTRA Insight API — detections, vehicle route reconstruction, pipeline stats."""

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Camera, Detection, User
from ..schemas import DetectionOut
from ..security import current_user
from ..services import anpr
from ..services.insight import engine

router = APIRouter(prefix="/api/insight", tags=["insight"])


@router.get("/stats")
def stats(user: User = Depends(current_user)):
    return engine.stats()


@router.get("/detections", response_model=list[DetectionOut])
def list_detections(
    plate: str | None = None,
    camera_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = db.query(Detection).order_by(Detection.ts.desc())
    if plate:
        q = q.filter(Detection.plate_text == anpr.normalise_plate(plate)[0])
    if camera_id:
        q = q.filter(Detection.camera_id == camera_id)
    return q.limit(min(limit, 1000)).all()


@router.get("/route/{plate}")
def route(plate: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """The evaluation feature: full movement history of a registration number.

    Groups consecutive detections per camera into 'sightings' and returns them
    time-ordered with coordinates — the Command UI draws this as a route
    polyline + timeline.
    """
    normalised, _ = anpr.normalise_plate(plate)
    dets = (
        db.query(Detection)
        .filter(Detection.plate_text == normalised)
        .order_by(Detection.ts.asc())
        .all()
    )
    if not dets:
        return {"plate": normalised, "sightings": [], "cameras_seen": 0, "total_detections": 0}

    cams = {c.id: c for c in db.query(Camera).all()}
    sightings: list[dict] = []
    for d in dets:
        cam = cams.get(d.camera_id)
        if sightings and sightings[-1]["camera_id"] == d.camera_id:
            s = sightings[-1]
            s["last_seen"] = d.ts
            s["detections"] += 1
            s["best_conf"] = max(s["best_conf"], d.plate_conf or 0)
        else:
            sightings.append(
                {
                    "camera_id": d.camera_id,
                    "camera_name": cam.name if cam else "",
                    "location": cam.location if cam else "",
                    "district": cam.district if cam else "",
                    "lat": cam.lat if cam else None,
                    "lon": cam.lon if cam else None,
                    "first_seen": d.ts,
                    "last_seen": d.ts,
                    "detections": 1,
                    "best_conf": d.plate_conf or 0,
                    "snapshot": f"/data/{d.snapshot_path}" if d.snapshot_path else None,
                }
            )
    return {
        "plate": normalised,
        "sightings": sightings,
        "cameras_seen": len({s["camera_id"] for s in sightings}),
        "total_detections": len(dets),
    }


@router.post("/analyse")
async def analyse_upload(file: UploadFile, user: User = Depends(current_user)):
    """Run ANPR on an uploaded image — used for testing and the demo video."""
    data = await file.read()
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "not a decodable image")
    hits = anpr.analyse_frame(frame)
    return {
        "plates": [
            {
                "raw": h.text,
                "plate": h.normalised,
                "valid_format": h.valid_format,
                "ocr_conf": h.ocr_conf,
                "det_conf": h.det_conf,
                "bbox": h.bbox,
            }
            for h in hits
        ]
    }
