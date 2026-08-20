"""Auto-discovery adapter: pulls the hackathon portal's camera list into Atlas.

This is one concrete adapter of the Bridge connector framework — the portal
exposes `/api/cameras` (JSON) and `/stream/{id}` (progressive HTTP), so
discovery + onboarding is fully API-driven (Model 1 'API-based onboarding').
"""

import logging

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..geodata import locate
from ..models import Camera

log = logging.getLogger("sutra.discovery")


async def fetch_portal_cameras() -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{settings.portal_base}/api/cameras")
        r.raise_for_status()
        payload = r.json()
    return payload.get("cameras", payload if isinstance(payload, list) else [])


def upsert_cameras(db: Session, portal_cams: list[dict]) -> dict:
    created, updated = 0, 0
    for pc in portal_cams:
        ext_id = f"sentinel-{pc['id']}"
        cam = db.query(Camera).filter(Camera.external_id == ext_id).one_or_none()
        stream_url = f"{settings.portal_base}/stream/{pc['id']}"
        if cam is None:
            lat, lon, district, dept = locate(pc.get("location", ""))
            cam = Camera(
                external_id=ext_id,
                name=pc.get("name", f"Camera {pc['id']}"),
                location=pc.get("location", ""),
                department=dept,
                district=district,
                lat=lat,
                lon=lon,
                coords_approx=True,
                source_type="http-progressive",
                source_url=stream_url,
                codec=pc.get("codec", ""),
                container=pc.get("container", ""),
                status=pc.get("status", "unknown"),
                onboarded_via="discovery",
            )
            db.add(cam)
            created += 1
        else:
            cam.status = pc.get("status", cam.status)
            cam.codec = pc.get("codec", cam.codec)
            cam.container = pc.get("container", cam.container)
            cam.source_url = stream_url
            updated += 1
    db.commit()
    log.info("discovery: %d created, %d updated", created, updated)
    return {"created": created, "updated": updated, "total_from_portal": len(portal_cams)}
