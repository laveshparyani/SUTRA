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

_ALLOWED_SCHEMES = ("rtsp://", "http://", "https://")


def _validate_source(source_type: str, source_url: str) -> None:
    """Onboarding cannot point the ingest engine at arbitrary targets:
    network sources are restricted to camera protocols, and file sources are
    confined to the media directory (no reading arbitrary server paths)."""
    if not source_url:
        return
    from pathlib import Path

    from ..config import settings

    if source_type == "file":
        target = Path(source_url).resolve()
        root = Path(settings.data_dir).resolve()
        if root not in target.parents:
            raise HTTPException(422, "file sources must live under the media data directory")
    elif not source_url.lower().startswith(_ALLOWED_SCHEMES):
        raise HTTPException(422, f"source_url must use one of: {', '.join(_ALLOWED_SCHEMES)}")


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
    _validate_source(body.source_type, body.source_url)
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
    if "source_url" in changes or "source_type" in changes:
        _validate_source(changes.get("source_type", cam.source_type), changes.get("source_url", cam.source_url))
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
        try:
            _validate_source(row.get("source_type", "rtsp"), row.get("source_url", ""))
        except HTTPException:
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
            camera_type=row.get("camera_type", ""),
            ownership=row.get("ownership") or "government",
            install_date=row.get("install_date", ""),
            source_type=row.get("source_type", "rtsp"),
            source_url=row.get("source_url", ""),
            storage_type=row.get("storage_type", "unknown"),
            retention_days=int(row["retention_days"]) if row.get("retention_days") else None,
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
    from datetime import date

    ageing_cutoff = str(date(date.today().year - 5, date.today().month, 1))
    cams = db.query(Camera).all()
    by_district: dict[str, dict] = {}
    for c in cams:
        d = by_district.setdefault(
            c.district or "Unknown", {"cameras": 0, "down": 0, "ageing": 0, "departments": set()}
        )
        d["cameras"] += 1
        d["departments"].add(c.department)
        if c.health in ("down", "degraded"):
            d["down"] += 1
        if c.install_date and c.install_date < ageing_cutoff:
            d["ageing"] += 1
    return {
        "total_cameras": len(cams),
        "monitored": sum(1 for c in cams if c.monitoring),
        "healthy": sum(1 for c in cams if c.health == "ok"),
        "ageing_cutoff": ageing_cutoff,
        "districts": {
            k: {
                "cameras": v["cameras"],
                "unhealthy": v["down"],
                "ageing": v["ageing"],
                "departments": sorted(v["departments"]),
            }
            for k, v in sorted(by_district.items())
        },
    }


@router.get("/export")
def export_registry(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Model 1 'export': full registry as CSV (respects operator dept scoping)."""
    import csv
    import io

    from fastapi.responses import Response

    q = db.query(Camera)
    if user.role == "operator" and user.department:
        q = q.filter(Camera.department == user.department)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["external_id", "name", "location", "department", "district", "lat", "lon",
                "camera_type", "ownership", "install_date", "source_type", "codec", "container",
                "resolution", "source_fps", "bitrate_kbps", "alt_rtsp_url",
                "storage_type", "retention_days", "status", "health", "monitoring", "onboarded_via"])
    for c in q.order_by(Camera.id).all():
        w.writerow([c.external_id, c.name, c.location, c.department, c.district, c.lat, c.lon,
                    c.camera_type, c.ownership, c.install_date, c.source_type, c.codec, c.container,
                    c.resolution, c.source_fps, c.bitrate_kbps, c.alt_rtsp_url,
                    c.storage_type, c.retention_days, c.status, c.health, c.monitoring, c.onboarded_via])
    db.add(AuditLog(actor=user.username, action="registry.export", detail=f"{q.count()} rows"))
    db.commit()
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sutra_camera_registry.csv"},
    )


@router.get("/audit")
def audit_trail(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Metadata audit trail (Model 1) — who did what, most recent first."""
    rows = db.query(AuditLog).order_by(AuditLog.ts.desc()).limit(min(limit, 500)).all()
    return [{"ts": r.ts, "actor": r.actor, "action": r.action, "detail": r.detail} for r in rows]
