"""Auto-discovery adapter: pulls the hackathon portal's camera list into Atlas.

One concrete adapter of the Bridge connector framework. The portal publishes a
JSON inventory at `/api/cameras` and offers each camera over several
transports; discovery records them all and picks the one that is actually
reachable, so onboarding stays fully API-driven (Model 1 'API-based
onboarding').

Transport notes, measured against the portal rather than assumed:
  * `/stream/{id}` progressive HTTP over 443 — works, and is what ingest uses.
  * `rtsp://…:8554/stream/{id}` — advertised, but port 8554 is blocked on many
    operator networks (ours included), so it is stored for documentation and
    used only when explicitly preferred.
  * `/live/stream/{id}/index.m3u8` — HLS behind a browser cookie handshake,
    which a headless decoder cannot complete; recorded, not used.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..geodata import locate
from ..models import Camera

log = logging.getLogger("sutra.discovery")

# external_id prefix is stable across portal moves so a rehost updates the
# existing registry rows instead of duplicating the whole inventory
EXT_PREFIX = "sentinel"


async def fetch_portal_cameras() -> list[dict]:
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        r = await client.get(f"{settings.portal_base}/api/cameras")
        r.raise_for_status()
        payload = r.json()
    return payload.get("cameras", payload if isinstance(payload, list) else [])


def _absolute(url: str) -> str:
    """Portal HLS paths are relative; make them addressable."""
    if not url:
        return ""
    return url if url.startswith(("http://", "https://", "rtsp://")) else f"{settings.portal_base}{url}"


def _metadata(pc: dict) -> dict:
    """Map a portal record onto registry columns."""
    w, h = pc.get("width") or 0, pc.get("height") or 0
    return {
        "name": pc.get("name") or f"Camera {pc['id']}",
        "location": pc.get("location", ""),
        "codec": pc.get("codec") or "",
        "container": pc.get("container") or "",
        "resolution": f"{w}x{h}" if w and h else "",
        "source_fps": pc.get("fps") or None,
        "bitrate_kbps": pc.get("bitrate_kbps") or None,
        "alt_rtsp_url": pc.get("rtsp_url", "") or "",
        "alt_hls_url": _absolute(pc.get("hls_live_url", "") or ""),
        "status": pc.get("status", "unknown"),
        # progressive HTTP is the transport that actually reaches us
        "source_type": "http-progressive",
        "source_url": f"{settings.portal_base}/stream/{pc['id']}",
    }


def upsert_cameras(db: Session, portal_cams: list[dict]) -> dict:
    created = updated = 0
    seen: set[str] = set()

    for pc in portal_cams:
        ext_id = f"{EXT_PREFIX}-{pc['id']}"
        seen.add(ext_id)
        meta = _metadata(pc)
        cam = db.query(Camera).filter(Camera.external_id == ext_id).one_or_none()
        if cam is None:
            lat, lon, district, dept = locate(meta["location"])
            cam = Camera(
                external_id=ext_id,
                department=dept,
                district=district,
                lat=lat,
                lon=lon,
                coords_approx=True,
                onboarded_via="discovery",
                **meta,
            )
            db.add(cam)
            created += 1
        else:
            # a rehosted portal changes URLs but not identity: refresh the
            # transport details and leave operator-curated fields alone
            for field, value in meta.items():
                setattr(cam, field, value)
            updated += 1

    # cameras the portal no longer lists are marked offline rather than left
    # advertising a dead endpoint
    retired = 0
    for cam in db.query(Camera).filter(Camera.external_id.like(f"{EXT_PREFIX}-%")).all():
        if cam.external_id not in seen and cam.status != "offline":
            cam.status = "offline"
            cam.monitoring = False
            cam.health_detail = "no longer published by the portal"
            retired += 1

    db.commit()
    result = {
        "created": created,
        "updated": updated,
        "retired": retired,
        "total_from_portal": len(portal_cams),
    }
    log.info("discovery: %s", result)
    return result
