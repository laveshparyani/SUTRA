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


@router.websocket("/ws")
async def alerts_ws(ws: WebSocket):
    """Real-time alert push for the Command UI."""
    global _loop
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
