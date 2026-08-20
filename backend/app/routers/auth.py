"""Auth endpoints: login → JWT, current-user introspection."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..security import create_token, current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    db.add(AuditLog(actor=user.username, action="auth.login"))
    db.commit()
    return {
        "token": create_token(user),
        "username": user.username,
        "role": user.role,
        "department": user.department,
    }


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "role": user.role, "department": user.department}
