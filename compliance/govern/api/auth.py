from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from govern.config import get_settings
from govern.db import get_db
from govern.models import ROLES, User
from govern.security.auth import (
    _DUMMY_HASH, COOKIE_NAME, audit, check_password_strength, current_user, hash_password, issue_token,
    require_role, verify_password,
)
from govern.timeutil import utcnow

router = APIRouter()


class LoginBody(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    active: bool
    last_login_at: str | None = None

    @classmethod
    def of(cls, u: User) -> "UserOut":
        return cls(id=u.id, email=u.email, name=u.name, role=u.role, active=u.active,
                   last_login_at=u.last_login_at.isoformat() if u.last_login_at else None)


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    s = get_settings()
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    now = utcnow()
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        audit(db, request, None, "login.failed", "user", email=email, reason="unknown")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is wrong")
    if user.locked_until and user.locked_until > now:
        audit(db, request, user, "login.locked", "user", user.id)
        db.commit()
        minutes = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed attempts; try again in {minutes} minutes")
    if not verify_password(body.password, user.password_hash) or not user.active:
        user.failed_logins += 1
        if user.failed_logins >= s.LOGIN_MAX_FAILURES:
            user.locked_until = now + timedelta(minutes=s.LOGIN_LOCKOUT_MINUTES)
            user.failed_logins = 0
        audit(db, request, user, "login.failed", "user", user.id,
              reason="inactive" if user.active is False else "password")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is wrong")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    audit(db, request, user, "login", "user", user.id)
    db.commit()
    response.set_cookie(COOKIE_NAME, issue_token(user), max_age=s.SESSION_MINUTES * 60, httponly=True,
                        secure=s.COOKIE_SECURE, samesite="strict", path="/")
    return UserOut.of(user)


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.of(user)


class PasswordChange(BaseModel):
    current: str
    new: str


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordChange, request: Request, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> None:
    if not verify_password(body.current, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong")
    check_password_strength(body.new)
    user.password_hash = hash_password(body.new)
    audit(db, request, user, "user.password_changed", "user", user.id)
    db.commit()


# ─── user administration ──────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    name: str = ""
    role: str = "viewer"
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = None


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise HTTPException(422, f"role must be one of {', '.join(ROLES)}")


@router.get("/users")
def list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> list[UserOut]:
    return [UserOut.of(u) for u in db.scalars(select(User).order_by(User.email))]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, admin: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)) -> UserOut:
    _check_role(body.role)
    check_password_strength(body.password)
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    audit(db, request, admin, "user.created", "user", user.id, email=email, role=body.role)
    db.commit()
    return UserOut.of(user)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, admin: User = Depends(require_role("admin")),
                db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user")
    changes = body.model_dump(exclude_none=True)
    if "role" in changes:
        _check_role(body.role)
    if user.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("active") is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't demote or deactivate yourself")
    if user.role == "admin" and (changes.get("role", "admin") != "admin" or changes.get("active") is False):
        others = db.scalar(select(func.count(User.id)).where(User.role == "admin", User.active.is_(True),
                                                              User.id != user.id))
        if not others:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one active admin must remain")
    if body.password is not None:
        check_password_strength(body.password)
        user.password_hash = hash_password(body.password)
        user.failed_logins = 0
        user.locked_until = None
    for key in ("name", "role", "active"):
        if key in changes:
            setattr(user, key, changes[key])
    audit(db, request, admin, "user.updated", "user", user.id,
          fields=sorted(k if k != "password" else "password(reset)" for k in changes))
    db.commit()
    return UserOut.of(user)


def ensure_bootstrap_admin(db: Session) -> None:
    s = get_settings()
    if db.scalar(select(func.count(User.id))):
        return
    if not (s.BOOTSTRAP_ADMIN_EMAIL and s.BOOTSTRAP_ADMIN_PASSWORD):
        return
    check_password_strength(s.BOOTSTRAP_ADMIN_PASSWORD)
    db.add(User(email=s.BOOTSTRAP_ADMIN_EMAIL.lower(), name="Administrator", role="admin",
                password_hash=hash_password(s.BOOTSTRAP_ADMIN_PASSWORD)))
    audit(db, None, None, "user.bootstrap_admin", "user", email=s.BOOTSTRAP_ADMIN_EMAIL.lower())
    db.commit()
