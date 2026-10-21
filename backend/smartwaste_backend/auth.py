"""Password hashing, JWT access tokens and role checks."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .db import get_database
from .errors import ApiError


TOKEN_TTL = timedelta(hours=8)
ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72

router = APIRouter(prefix="/auth", tags=["auth"])


def _secret():
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, password_hash):
    raw = password.encode()
    if not password_hash or len(raw) > BCRYPT_MAX_BYTES:
        return False
    return bcrypt.checkpw(raw, password_hash.encode())


def issue_token(user_id):
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def public_user(user):
    return {
        "id": user["_id"],
        "display_name": user["display_name"],
        "roles": user["roles"],
    }


def current_user(request: Request):
    """Resolve the bearer token to an active user; re-read status every request."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "Chưa đăng nhập")
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise ApiError(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")

    user = get_database().users.find_one(
        {"_id": claims["sub"]},
        {"password_hash": 0},
    )
    if not user or user["status"] != "active":
        raise ApiError(401, "Tài khoản không còn hoạt động")
    return user


def require_roles(*roles):
    """Dependency allowing users holding at least one of ``roles``."""

    def check(user=Depends(current_user)):
        if not set(roles) & set(user["roles"]):
            raise ApiError(403, "Không đủ quyền thực hiện thao tác này")
        return user

    return check


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn):
    # ponytail: no login rate limit yet; add a per-IP counter before public deployment.
    database = get_database()
    user = database.users.find_one({"email_normalized": body.email.strip().lower()})
    if (
        not user
        or user["status"] != "active"
        or not verify_password(body.password, user["password_hash"])
    ):
        raise ApiError(401, "Email hoặc mật khẩu không đúng, hoặc tài khoản chưa kích hoạt")

    database.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc)}},
    )
    return {
        "access_token": issue_token(user["_id"]),
        "token_type": "bearer",
        "expires_in": int(TOKEN_TTL.total_seconds()),
        "user": public_user(user),
    }


@router.get("/me")
def me(user=Depends(current_user)):
    return public_user(user)
