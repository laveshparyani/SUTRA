"""Auth endpoints: login → JWT + HttpOnly media cookie, current-user introspection."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AuditLog, User
from ..security import create_media_token, create_token, current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# brute-force guard: sliding window of failed attempts per client address
_MAX_FAILS, _WINDOW_S = 5, 300
_fails: dict[str, deque] = defaultdict(deque)


def _throttled(ip: str) -> bool:
    q = _fails[ip]
    now = time.time()
    while q and now - q[0] > _WINDOW_S:
        q.popleft()
    return len(q) >= _MAX_FAILS


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if _throttled(ip):
        raise HTTPException(429, "too many failed attempts — try again later")
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        _fails[ip].append(time.time())
        db.add(AuditLog(actor=body.username[:40], action="auth.login_failed", detail=f"from {ip}"))
        db.commit()
        raise HTTPException(401, "invalid credentials")
    _fails.pop(ip, None)
    db.add(AuditLog(actor=user.username, action="auth.login"))
    db.commit()
    # media/WS auth rides an HttpOnly cookie: img tags and WebSocket handshakes
    # can't send Authorization headers, and page scripts can't read this cookie
    response.set_cookie(
        "sutra_media",
        create_media_token(user),
        max_age=settings.media_token_ttl_s,
        httponly=True,
        samesite="lax",
    )
    return {
        "token": create_token(user),
        "username": user.username,
        "role": user.role,
        "department": user.department,
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("sutra_media")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role, "department": user.department}
