"""Create demo accounts (admin, dispatcher, collector) once.

Usage: DEMO_PASSWORD=... python -m smartwaste_backend.scripts.seed_users
Existing accounts are left untouched, so re-running never resets passwords.
"""

import os
from datetime import datetime, timezone

from ..core.db import get_database
from ..core.security import hash_password


DEMO_USERS = (
    ("usr-admin", "admin@smartwaste.local", "Quản trị viên", ["admin"]),
    ("usr-dispatcher", "dispatcher@smartwaste.local", "Điều phối viên", ["dispatcher"]),
    ("usr-collector", "collector@smartwaste.local", "Nhân viên thu gom", ["collector"]),
)


def main():
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 8:
        raise SystemExit("Set DEMO_PASSWORD (at least 8 characters) before seeding")

    users = get_database().users
    now = datetime.now(timezone.utc)
    for user_id, email, display_name, roles in DEMO_USERS:
        result = users.update_one(
            {"_id": user_id},
            {
                "$setOnInsert": {
                    "email_normalized": email,
                    "display_name": display_name,
                    "password_hash": hash_password(password),
                    "roles": roles,
                    "status": "active",
                    "phone": None,
                    "last_login_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        print(("CREATED " if result.upserted_id else "EXISTS  ") + email)


if __name__ == "__main__":
    main()
