"""SUTRA Watch — watchlist registry, alerts, real-time WebSocket push."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, AuditLog, User, WatchlistVehicle
from ..schemas import AlertOut, WatchlistCreate, WatchlistOut
from ..security import current_user, require_roles

log = logging.getLogger("sutra.watch")
router = APIRouter(prefix="/api/watch", tags=["watch"])

_ws_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None


def normalise_plate(plate: str) -> str:
    """Uppercase, strip separators — 'GJ 01 AB 1234' -> 'GJ01AB1234'."""
    return "".join(ch for ch in plate.upper() if ch.isalnum())


@router.get("/vehicles", response_model=list[WatchlistOut])
def list_watchlist(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.query(WatchlistVehicle).order_by(WatchlistVehicle.created_at.desc()).all()


@router.post("/vehicles", response_model=WatchlistOut, status_code=201)
def add_watchlist(
    body: WatchlistCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    plate = normalise_plate(body.plate)
    if db.query(WatchlistVehicle).filter(WatchlistVehicle.plate == plate).first():
        raise HTTPException(409, "plate already on watchlist")
    entry = WatchlistVehicle(**{**body.model_dump(), "plate": plate}, added_by=user.username)
    db.add(entry)
    db.add(AuditLog(actor=user.username, action="watchlist.add", detail=plate))
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/vehicles/{entry_id}")
def remove_watchlist(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    entry = db.get(WatchlistVehicle, entry_id)
    if not entry:
        raise HTTPException(404, "not found")
    entry.active = False
    db.add(AuditLog(actor=user.username, action="watchlist.deactivate", detail=entry.plate))
    db.commit()
    return {"deactivated": entry.plate}


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = db.query(Alert).order_by(Alert.ts.desc())
    if status:
        q = q.filter(Alert.status == status)
    return q.limit(min(limit, 500)).all()


@router.get("/alerts/episodes")
def alert_episodes(
    hours: int = 168,
    status: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Alerts collapsed into *episodes*.

    One watchlisted vehicle parked in a camera's view fires an alert every
    cooldown window. Fifty identical rows tell an operator nothing that one row
    saying "seen 50 times over 3 hours, 12 still unacknowledged" does not say
    better. Consecutive alerts for the same plate on the same camera are
    grouped; individual alerts remain available via /alerts.
    """
    from datetime import datetime, timedelta, timezone

    from ..models import Camera, Detection

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(Alert).filter(Alert.ts >= since)
    if status:
        q = q.filter(Alert.status == status)
    alerts = q.order_by(Alert.ts.desc()).limit(4000).all()

    dets = {d.id: d for d in db.query(Detection).all()}
    entries = {w.id: w for w in db.query(WatchlistVehicle).all()}
    cams = {c.id: c for c in db.query(Camera).all()}
    SEV_RANK = {"low": 0, "medium": 1, "high": 2}

    episodes: list[dict] = []
    index: dict[tuple, dict] = {}
    for a in alerts:
        det = dets.get(a.detection_id)
        entry = entries.get(a.watchlist_id)
        if det is None or entry is None:
            continue
        cam = cams.get(det.camera_id)
        ts = a.ts if a.ts.tzinfo else a.ts.replace(tzinfo=timezone.utc)
        key = (entry.plate, det.camera_id)
        ep = index.get(key)
        # one row per vehicle per camera for the whole window: splitting a
        # recurring vehicle into time slices is the repetition operators
        # complained about, and the window itself carries the timing
        if ep:
            ep["first_seen"] = min(ep["first_seen"], ts)
            ep["count"] += 1
            ep["unacknowledged"] += 1 if a.status == "new" else 0
            if SEV_RANK.get(a.severity, 0) > SEV_RANK.get(ep["severity"], 0):
                ep["severity"] = a.severity
            ep["alert_ids"].append(a.id)
            continue
        ep = {
            "plate": entry.plate,
            "reason": entry.reason,
            "fir_ref": entry.fir_ref,
            "priority": entry.priority,
            "camera_id": det.camera_id,
            "camera_name": cam.name if cam else f"#{det.camera_id}",
            "location": cam.location if cam else "",
            "district": cam.district if cam else "",
            "first_seen": ts,
            "last_seen": ts,
            "count": 1,
            "unacknowledged": 1 if a.status == "new" else 0,
            "severity": a.severity,
            "latest_alert_id": a.id,
            "alert_ids": [a.id],
            "snapshot": f"/data/{det.snapshot_path}" if det.snapshot_path else None,
        }
        index[key] = ep
        episodes.append(ep)

    return episodes[: min(limit, 500)]


@router.post("/alerts/episodes/ack")
def ack_episode(
    alert_ids: list[int],
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    """Acknowledge every alert in an episode in one action."""
    rows = db.query(Alert).filter(Alert.id.in_(alert_ids[:2000]), Alert.status == "new").all()
    for a in rows:
        a.status = "acknowledged"
        a.acked_by = user.username
    db.add(AuditLog(actor=user.username, action="alert.ack_episode", detail=f"{len(rows)} alerts"))
    db.commit()
    return {"acknowledged": len(rows)}


@router.post("/alerts/{alert_id}/ack")
def ack_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "not found")
    alert.status = "acknowledged"
    alert.acked_by = user.username
    db.add(AuditLog(actor=user.username, action="alert.ack", detail=str(alert_id)))
    db.commit()
    return {"acknowledged": alert_id}


@router.get("/vehicle-info/{plate}")
def vehicle_info(plate: str, user: User = Depends(current_user)):
    """Government-DB correlation: vehicle details by registration number.

    Served by the connector framework (representative VAHAN dataset in the
    sandbox; the production NIC endpoint is a connector swap).
    """
    from ..connectors.vahan import vahan

    info = vahan.lookup(normalise_plate(plate))
    if info is None:
        raise HTTPException(404, "no record in connected government databases")
    return info


@router.websocket("/ws")
async def alerts_ws(ws: WebSocket):
    """Real-time alert push for the Command UI. Authenticated via the HttpOnly
    media cookie (sent automatically on same-origin WS handshakes)."""
    from ..security import verify_media_access

    global _loop
    if not verify_media_access(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    _loop = asyncio.get_running_loop()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ignore client messages
    except WebSocketDisconnect:
        _ws_clients.discard(ws)


def broadcast_alert(payload: dict) -> None:
    """Thread-safe alert fan-out — callable from Insight worker threads."""
    if _loop is None:
        return
    message = json.dumps(payload, default=str)

    async def _send():
        dead = []
        for client in list(_ws_clients):
            try:
                await client.send_text(message)
            except Exception:
                dead.append(client)
        for d in dead:
            _ws_clients.discard(d)

    asyncio.run_coroutine_threadsafe(_send(), _loop)
