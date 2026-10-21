"""Tests run against a separate MongoDB database that already has schema v2.

Prepare it once with:
    docker compose run --rm -e SW_DB=smartwaste_test db-schema
"""

import os
from datetime import datetime, timezone

import pytest

os.environ["MONGO_DB"] = "smartwaste_test"
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-0123456789")

from fastapi.testclient import TestClient  # noqa: E402

from smartwaste_backend.app import app  # noqa: E402
from smartwaste_backend.auth import hash_password  # noqa: E402
from smartwaste_backend.db import get_database  # noqa: E402


PASSWORD = "correct-horse-9"


@pytest.fixture
def db():
    database = get_database()
    if not database.schema_migrations.find_one({"_id": "schema-v2_0_0"}):
        pytest.exit("Test DB has no schema; see tests/conftest.py docstring")
    database.users.delete_many({})
    return database


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user(db):
    def make(user_id, roles, status="active"):
        now = datetime.now(timezone.utc)
        db.users.insert_one({
            "_id": user_id,
            "email_normalized": f"{user_id}@test.local",
            "display_name": user_id,
            "password_hash": hash_password(PASSWORD),
            "roles": roles,
            "status": status,
            "phone": None,
            "last_login_at": None,
            "created_at": now,
            "updated_at": now,
        })
        return f"{user_id}@test.local"

    return make


@pytest.fixture
def login(client):
    def do(email, password=PASSWORD):
        return client.post("/api/v1/auth/login", json={"email": email, "password": password})

    return do
