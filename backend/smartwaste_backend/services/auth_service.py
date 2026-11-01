"""Login rules and the public shape of a user."""

from datetime import datetime, timezone

from ..core.db import get_database
from ..core.errors import ApiError
from ..core.security import TOKEN_TTL, hash_password, issue_token, verify_password
from . import audit_service


def public_user(user):
    return {
        "id": user["_id"],
        "display_name": user["display_name"],
        "roles": user["roles"],
    }


def login(email, password):
    """Check credentials of an active account and issue an access token."""
    # ponytail: no login rate limit yet; add a per-IP counter before public deployment.
    database = get_database()
    user = database.users.find_one({"email_normalized": email.strip().lower()})
    if not user or user["status"] != "active" or not verify_password(password,
                                                                      user["password_hash"]):
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


def change_password(user, current_password, new_password, request_id):
    """Replace the caller's password after checking the current one.

    Wrong current password is 422, never 401: the web client treats every 401 as an
    expired session and would log the user out.
    """
    database = get_database()
    stored = database.users.find_one({"_id": user["_id"]}, {"password_hash": 1})
    if not verify_password(current_password, stored and stored["password_hash"]):
        raise ApiError(422, "Mật khẩu hiện tại không đúng", {"field": "current_password"})
    if current_password == new_password:
        raise ApiError(422, "Mật khẩu mới phải khác mật khẩu hiện tại",
                       {"field": "new_password"})

    database.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(new_password),
                  "updated_at": datetime.now(timezone.utc)}},
    )
    audit_service.record(database, actor_id=user["_id"], action="password_change",
                         entity_type="user", entity_id=user["_id"],
                         summary=f"{user['display_name']} đổi mật khẩu", request_id=request_id)
    return {"ok": True}
