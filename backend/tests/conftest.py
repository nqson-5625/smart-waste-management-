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

from helpers import ASSIGNMENT, BIN, DEVICE  # noqa: E402


PASSWORD = "correct-horse-9"
PIPELINE_COLLECTIONS = ("telemetry", "bin_state", "alerts", "audit_logs", "device_configs",
                        "bins", "devices", "collection_events")


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


@pytest.fixture
def auth_as(make_user, login):
    """Return Authorization headers for a fresh user holding ``role``."""
    def headers(role):
        token = login(make_user(f"usr-{role}", [role])).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def wdb(db):
    """Empty pipeline collections plus one verified device whose state belongs to BIN."""
    for name in PIPELINE_COLLECTIONS:
        db[name].delete_many({})
    now = datetime.now(timezone.utc)
    db.device_configs.insert_one({
        "_id": f"{DEVICE}:1", "device_id": DEVICE, "config_rev": 1, "sensor_id": "level-01",
        "empty_distance_mm": 1000, "full_distance_mm": 100, "sample_interval_s": 60,
        "report_interval_s": 21600, "full_threshold_pct": 80, "clear_threshold_pct": 70,
        "confirm_cycles": 2, "status": "verified", "verified_at": now, "created_by": "usr-t",
        "created_at": now, "note": None,
    })
    db.bin_state.insert_one({
        "_id": BIN, "device_id": DEVICE, "assignment_id": ASSIGNMENT, "assignment_version": 1,
        "latest_boot_id": 0, "latest_seq": 0, "latest_message_id": None,
        "latest_quality": "unknown", "latest_sampled_at": None, "latest_received_at": None,
        "last_contact_at": None, "last_good": None, "alarm_active": None, "updated_at": now,
    })
    return db
