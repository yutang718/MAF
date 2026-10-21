"""Passwords, session tokens, and the role gate used by every route."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from govern.config import get_settings
from govern.db import get_db
from govern.models import AuditEntry, User

COOKIE_NAME = "govern_session"
ROLE_RANK = {"viewer": 0, "auditor": 1, "admin": 2}
MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# Spent on unknown emails so a login doesn't reveal which accounts exist by timing.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(422,
                            f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


def _jwt_secret() -> str:
    secret = get_settings().JWT_SECRET
    if not secret:
        raise RuntimeError("GOVERN_JWT_SECRET is not set")
    return secret


def issue_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().SESSION_MINUTES),
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        claims = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired; sign in again")
    user = db.get(User, int(claims["sub"]))
    # Re-read the role from the database so a demotion or deactivation applies at once.
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
    return user


def require_role(minimum: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires the {minimum} role")
        return user
    return dependency


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def audit(db: Session, request: Request | None, user: User | None, action: str,
          target_type: str = "", target_id: str | int = "", **detail) -> None:
    """Add a platform audit record to the session; the caller's commit persists it."""
    db.add(AuditEntry(
        user_id=user.id if user else None,
        user_email=user.email if user else detail.pop("email", ""),
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        detail=detail,
        ip=client_ip(request) if request else "",
    ))
