"""Authentication & RBAC: PBKDF2 password hashing + JWT bearer tokens.

Roles:
- admin     — full control (users, cameras, watchlist, ingest)
- operator  — department-scoped operations (sees own department's cameras,
              manages watchlist, acknowledges alerts)
- viewer    — read-only access
"""

import hashlib
import os
import time

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _ITERATIONS)
    return digest.hex() == digest_hex


def create_token(user: User) -> str:
    payload = {
        "uid": user.id,
        "sub": user.username,
        "role": user.role,
        "dept": user.department,
        "exp": int(time.time()) + settings.token_ttl_s,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_media_token(user: User) -> str:
    """Scoped token for media/WS delivered as an HttpOnly cookie: <img> tags and
    WebSocket handshakes can't set Authorization headers, and an HttpOnly cookie
    is invisible to page scripts (XSS can't exfiltrate it)."""
    payload = {
        "uid": user.id,
        "scope": "media",
        "exp": int(time.time()) + settings.media_token_ttl_s,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_media_access(request_or_ws) -> bool:
    """Accept the media cookie or a bearer token on media/WS endpoints."""
    token = request_or_ws.cookies.get("sutra_media")
    if not token:
        auth = request_or_ws.headers.get("authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        return False
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")


def current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "not authenticated")
    payload = decode_token(authorization[7:])
    user = db.get(User, payload["uid"])
    if user is None or not user.active:
        raise HTTPException(401, "unknown or deactivated user")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"requires role: {' or '.join(roles)}")
        return user

    return dep


def seed_default_users(db: Session) -> None:
    """Create initial users on first boot.

    Passwords come from SUTRA_SEED_*_PW env vars when set; the documented
    sandbox defaults are used otherwise, with a loud warning — a hosted or
    production instance must never run on published credentials.
    """
    import logging

    if db.query(User).count():
        return
    demo = [
        ("admin", settings.seed_admin_pw or "SutraAdmin@26", "admin", ""),
        ("operator_police", settings.seed_operator_pw or "Operator@26", "operator", "Police"),
        ("viewer", settings.seed_viewer_pw or "Viewer@26", "viewer", ""),
    ]
    if not (settings.seed_admin_pw and settings.seed_operator_pw and settings.seed_viewer_pw):
        logging.getLogger("sutra.security").warning(
            "seeding with DOCUMENTED SANDBOX PASSWORDS — set SUTRA_SEED_*_PW env vars before hosting publicly"
        )
    for username, password, role, dept in demo:
        db.add(User(username=username, password_hash=hash_password(password), role=role, department=dept))
    db.commit()
