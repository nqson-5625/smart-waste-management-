"""User accounts managed by the admin: create, edit, disable, list.

Roles are admin and collector only; the team folded the dispatcher role into admin.
"""

import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.common import decode_cursor, encode_cursor, iso, utcnow
from ..core.db import get_database
from ..core.errors import ApiError
from ..core.security import hash_password
from . import audit_service


HIDE_HASH = {"password_hash": 0}


def user_view(user):
    """Full account as the admin sees it; never includes the password hash."""
    return {
        "id": user["_id"], "email": user["email_normalized"],
        "display_name": user["display_name"], "roles": user["roles"], "status": user["status"],
        "phone": user["phone"], "last_login_at": iso(user["last_login_at"]),
        "created_at": iso(user["created_at"]),
    }


def create_user(body, admin, request_id):
    """Create an active account. Emails are unique regardless of case."""
    database = get_database()
    now = utcnow()
    user = {
        "_id": f"usr-{uuid.uuid4().hex[:12]}", "email_normalized": body.email.lower(),
        "display_name": body.display_name, "password_hash": hash_password(body.password),
        "roles": body.roles, "status": "active", "phone": body.phone, "last_login_at": None,
        "created_at": now, "updated_at": now,
    }
    try:
        database.users.insert_one(user)
    except DuplicateKeyError:
        raise ApiError(409, "Email đã được dùng cho tài khoản khác",
                       {"email": user["email_normalized"]})
    audit_service.record(database, actor_id=admin["_id"], action="user_create", entity_type="user",
                         entity_id=user["_id"],
                         summary=f"Tạo tài khoản {user['email_normalized']} "
                                 f"({', '.join(body.roles)})",
                         request_id=request_id)
    return user_view(user)


def update_user(user_id, body, admin, request_id):
    """Change the fields the client sent. An admin cannot lock themself out."""
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError(422, "Không có trường nào để cập nhật")
    if user_id == admin["_id"]:
        if changes.get("status") == "disabled":
            raise ApiError(409, "Không thể tự khóa tài khoản của mình")
        if "roles" in changes and "admin" not in changes["roles"]:
            raise ApiError(409, "Không thể tự bỏ quyền admin của mình")

    database = get_database()
    if changes.get("status") == "active" and "password" not in changes:
        current = database.users.find_one({"_id": user_id}, {"password_hash": 1})
        if current and not current["password_hash"]:
            raise ApiError(422, "Tài khoản chưa có mật khẩu, cần đặt password",
                           {"field": "password"})

    fields = sorted(changes)  # for the audit summary; the password itself is never logged
    if "password" in changes:
        changes["password_hash"] = hash_password(changes.pop("password"))
    updated = database.users.find_one_and_update(
        {"_id": user_id}, {"$set": {**changes, "updated_at": utcnow()}},
        projection=HIDE_HASH, return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise ApiError(404, "Không tìm thấy tài khoản", {"user_id": user_id})
    audit_service.record(database, actor_id=admin["_id"], action="user_update", entity_type="user",
                         entity_id=user_id,
                         summary=f"Sửa tài khoản {updated['email_normalized']}: "
                                 f"{', '.join(fields)}",
                         request_id=request_id)
    return user_view(updated)


def list_users(role, status, limit, cursor):
    """Page accounts by id, e.g. role=collector&status=active to pick who gets a route."""
    query = {}
    if role is not None:
        query["roles"] = role
    if status is not None:
        query["status"] = status
    if cursor:
        query["_id"] = {"$gt": decode_cursor(cursor, 1)[0]}

    users = list(get_database().users.find(query, HIDE_HASH).sort("_id", 1).limit(limit + 1))
    has_more = len(users) > limit
    users = users[:limit]
    return {
        "items": [user_view(user) for user in users],
        "next_cursor": encode_cursor([users[-1]["_id"]]) if has_more else None,
    }
