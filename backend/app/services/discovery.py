"""Auto-discovery adapter: pulls the hackathon portal's camera grid into Atlas.

One concrete adapter of the Bridge connector framework. The Sentinel Camera
Grid publishes a JSON catalogue at `/cameras.json` (id + display name only —
no coordinates, codec or resolution, so those come from geocoding the name
and from the decoder once a stream is open). Every camera is then reachable
over three transports:

  * RTSP  `rtsp://<ip>:8554/stream/<id>` — mediamtx on a public IP, credentials
    in the URL. Real live loop with monotonic PTS; what ingest uses.
  * HLS   `https://cctv.corp8.cloud/<id>/index.m3u8` — cookie-gated, AES-128,
    served as a finished ~12 h recording. Fallback for networks where 8554 is
    blocked; the operator's browser wall also plays it.
  * WHEP  `http://<ip>:8889/stream/<id>/whep` — browser preview only.

Onboarding stays fully API-driven (Model 1 'API-based onboarding'), and the
registry never stores credentials: URLs are credential-free here and the
portal module injects them when a stream is opened.
"""

import asyncio
import logging
import re

from sqlalchemy.orm import Session

from ..config import settings
from ..geodata import locate
from ..models import Camera
from . import portal

log = logging.getLogger("sutra.discovery")

# external_id prefix is stable across portal moves so a rehost updates the
# existing registry rows (and keeps their detection history) instead of
# duplicating the whole inventory. The grid's "cam07" is the same camera the
# first portal called id 7, so the numeric part is what the id is built from.
EXT_PREFIX = "sentinel"
_CAM_ID = re.compile(r"^cam0*(\d+)$", re.I)
_LEADING_NUMBER = re.compile(r"^\s*\d+\s+")


async def fetch_portal_cameras() -> list[dict]:
    """The grid's catalogue. Raises PortalAuthError when the portal cannot be
    logged into, and httpx errors when it is unreachable."""
    r = await asyncio.to_thread(portal.get, "/cameras.json")
    payload = r.json()
    return payload.get("cameras", payload) if isinstance(payload, dict) else payload


def external_id_for(portal_id: str) -> str:
    m = _CAM_ID.match(str(portal_id))
    return f"{EXT_PREFIX}-{int(m.group(1))}" if m else f"{EXT_PREFIX}-{portal_id}"


def _metadata(pc: dict) -> dict:
    """Map a catalogue record onto registry columns."""
    cam_id = str(pc["id"])
    label = (pc.get("name") or cam_id).strip()
    # "04 Paldi Circle" -> name "Paldi Circle"; the numbered label is kept as
    # the location string because that is how operators know these feeds
    name = _LEADING_NUMBER.sub("", label) or label
    rtsp = f"rtsp://{settings.portal_rtsp_host}:{settings.portal_rtsp_port}/stream/{cam_id}"
    return {
        "name": name,
        "location": label,
        "status": pc.get("status", "live"),
        "source_type": "rtsp",
        "source_url": rtsp,
        "alt_rtsp_url": rtsp,
        "alt_hls_url": f"{settings.portal_base}/{cam_id}/index.m3u8",
        # the catalogue carries no stream properties; keep whatever an earlier
        # record or the decoder already established
        "codec": pc.get("codec") or None,
        "container": pc.get("container") or None,
        "resolution": pc.get("resolution") or None,
    }


def upsert_cameras(db: Session, portal_cams: list[dict]) -> dict:
    created = updated = 0
    seen: set[str] = set()

    for pc in portal_cams:
        if not pc.get("id"):
            continue
        ext_id = external_id_for(pc["id"])
        seen.add(ext_id)
        meta = {k: v for k, v in _metadata(pc).items() if v is not None}
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
            if cam.status == "offline":
                cam.health_detail = ""
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
