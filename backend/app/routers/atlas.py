"""SUTRA Atlas — camera registry & GIS API (Model 1)."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..geodata import locate
from ..models import AuditLog, Camera, User
from ..schemas import CameraCreate, CameraOut, CameraUpdate
from ..security import current_user, require_roles
from ..services.discovery import fetch_portal_cameras, upsert_cameras

router = APIRouter(prefix="/api/atlas", tags=["atlas"])


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(
    department: str | None = None,
    district: str | None = None,
    status: str | None = None,
    health: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Camera)
    # department operators only see their own department's assets
    if user.role == "operator" and user.department:
        query = query.filter(Camera.department == user.department)
    if department:
        query = query.filter(Camera.department == department)
    if district:
        query = query.filter(Camera.district == district)
    if status:
        query = query.filter(Camera.status == status)
    if health:
        query = query.filter(Camera.health == health)
    if q:
        like = f"%{q}%"
        query = query.filter(Camera.name.ilike(like) | Camera.location.ilike(like))
    return query.order_by(Camera.id).all()


@router.get("/cameras/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "camera not found")
    return cam


@router.post("/cameras", response_model=CameraOut, status_code=201)
def create_camera(
    body: CameraCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    if db.query(Camera).filter(Camera.external_id == body.external_id).first():
        raise HTTPException(409, "external_id already registered")
    data = body.model_dump()
    if data.get("lat") is None or data.get("lon") is None:
        lat, lon, district, dept = locate(data.get("location", ""))
        data.setdefault("lat", None)
        data["lat"], data["lon"] = lat, lon
        data["district"] = data.get("district") or district
        if data.get("department") in (None, "", "Unassigned"):
            data["department"] = dept
    cam = Camera(**data, onboarded_via="api")
    db.add(cam)
    db.add(AuditLog(actor=user.username, action="camera.create", detail=body.external_id))
    db.commit()
    db.refresh(cam)
    return cam


@router.patch("/cameras/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    body: CameraUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "camera not found")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(cam, k, v)
    if "lat" in changes or "lon" in changes:
        cam.coords_approx = False
    db.add(AuditLog(actor=user.username, action="camera.update", detail=f"{camera_id}: {sorted(changes)}"))
    db.commit()
    db.refresh(cam)
    return cam


@router.post("/discover")
async def discover(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    """Pull the hackathon portal's camera list and upsert into the registry."""
    portal_cams = await fetch_portal_cameras()
    result = upsert_cameras(db, portal_cams)
    db.add(AuditLog(actor=user.username, action="camera.discover", detail=str(result)))
    db.commit()
    return result


@router.post("/cameras/bulk")
async def bulk_import(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    """Bulk onboarding via CSV: external_id,name,location,department,lat,lon,source_type,source_url."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created, skipped = 0, 0
    for row in reader:
        ext_id = (row.get("external_id") or "").strip()
        if not ext_id or db.query(Camera).filter(Camera.external_id == ext_id).first():
            skipped += 1
            continue
        lat = float(row["lat"]) if row.get("lat") else None
        lon = float(row["lon"]) if row.get("lon") else None
        if lat is None or lon is None:
            lat, lon, district, dept = locate(row.get("location", ""))
        else:
            district, dept = row.get("district", ""), row.get("department", "Unassigned")
        cam = Camera(
            external_id=ext_id,
            name=row.get("name", ext_id),
            location=row.get("location", ""),
            department=row.get("department") or dept,
            district=row.get("district") or district,
            lat=lat,
            lon=lon,
            coords_approx=not (row.get("lat") and row.get("lon")),
            source_type=row.get("source_type", "rtsp"),
            source_url=row.get("source_url", ""),
            onboarded_via="bulk",
        )
        db.add(cam)
        created += 1
    db.add(AuditLog(actor=user.username, action="camera.bulk_import", detail=f"created={created} skipped={skipped}"))
    db.commit()
    return {"created": created, "skipped": skipped}


@router.get("/gap-analysis")
def gap_analysis(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Model 1 deliverable: coverage & infrastructure gaps by district/department."""
    cams = db.query(Camera).all()
    by_district: dict[str, dict] = {}
    for c in cams:
        d = by_district.setdefault(c.district or "Unknown", {"cameras": 0, "down": 0, "departments": set()})
        d["cameras"] += 1
        d["departments"].add(c.department)
        if c.health in ("down", "degraded"):
            d["down"] += 1
    return {
        "total_cameras": len(cams),
        "monitored": sum(1 for c in cams if c.monitoring),
        "healthy": sum(1 for c in cams if c.health == "ok"),
        "districts": {
            k: {"cameras": v["cameras"], "unhealthy": v["down"], "departments": sorted(v["departments"])}
            for k, v in sorted(by_district.items())
        },
    }
