"""Login rules and the public shape of a user."""

from datetime import datetime, timezone

from ..core.db import get_database
from ..core.errors import ApiError
from ..core.security import TOKEN_TTL, issue_token, verify_password


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
