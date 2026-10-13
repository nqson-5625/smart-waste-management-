"""Seed schema-v2 development identities and their required relationships."""

import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.write_concern import WriteConcern


DATABASE_NAME = os.environ.get("MONGO_DB", "smartwaste_v2")
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017/?directConnection=true",
)

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
database = mongo_client.get_database(
    DATABASE_NAME,
    write_concern=WriteConcern(w="majority", j=True),
)

if not database.schema_migrations.find_one({"_id": "schema-v2_0_0"}):
    raise RuntimeError("MongoDB schema v2 is missing; run mql/01_schema.js first")

now = datetime.now(timezone.utc)
# The simulator replays samples seven minutes in the past.
installed_at = now - timedelta(minutes=10)


def insert_if_missing(collection_name, document, session):
    """Insert one seed document idempotently."""
    database[collection_name].update_one(
        {"_id": document["_id"]},
        {"$setOnInsert": document},
        upsert=True,
        session=session,
    )


def seed(session):
    """Create a complete, internally consistent schema-v2 development seed."""
    insert_if_missing(
        "users",
        {
            "_id": "usr-dev-admin",
            "email_normalized": "admin@example.invalid",
            "display_name": "Development Admin",
            "password_hash": None,
            "roles": ["admin"],
            "status": "pending",
            "phone": None,
            "last_login_at": None,
            "created_at": now,
            "updated_at": now,
        },
        session,
    )

    registry_entries = (
        ("bin-001", "WB-001", "gw-001"),
        ("bin-900001", "WB-SIMULATOR", "gw-simulator"),
    )
    for device_id, bin_id, gateway_id in registry_entries:
        insert_if_missing(
            "gateways",
            {
                "_id": gateway_id,
                "name": f"Development {gateway_id}",
                "location": None,
                "enabled": True,
                "firmware_version": "1.0.0",
                "status": "unknown",
                "status_reported_at": None,
                "last_received_at": None,
                "boot_id": None,
                "queue_depth": None,
                "queue_capacity": 32,
                "invalid_packets": None,
                "queue_full_events": None,
                "storage_errors": None,
                "wifi_rssi_dbm": None,
                "created_at": now,
                "updated_at": now,
            },
            session,
        )
        insert_if_missing(
            "bins",
            {
                "_id": bin_id,
                "code": bin_id,
                "name": f"Development {bin_id}",
                "address": "CHUA LAP DAT",
                "ward_code": "DEV",
                "location": None,
                "waste_type": "general",
                "capacity_l": None,
                "status": "active",
                "environment": "lab",
                "assignment_version": 1,
                "notes": "Du lieu phat trien; can nhap vi tri va hieu chuan thuc te.",
                "created_at": now,
                "updated_at": now,
            },
            session,
        )
        insert_if_missing(
            "devices",
            {
                "_id": device_id,
                "hardware_model": "ESP32-C3 Super Mini",
                "serial_number": None,
                "firmware_version": "1.0.0",
                "gateway_ids": [gateway_id],
                "enabled": True,
                "lifecycle": "installed",
                "applied_config_rev": None,
                "sensors": [
                    {
                        "sensor_id": "level-01",
                        "type": "ultrasonic",
                        "model": "HC-SR04",
                        "status": "active",
                    }
                ],
                "commissioned_at": installed_at,
                "notes": "Development provision; config is not verified yet.",
                "created_at": now,
                "updated_at": now,
            },
            session,
        )
        insert_if_missing(
            "device_configs",
            {
                "_id": f"{device_id}:1",
                "device_id": device_id,
                "config_rev": 1,
                "sensor_id": "level-01",
                "empty_distance_mm": 1000,
                "full_distance_mm": 100,
                "sample_interval_s": 60,
                "report_interval_s": 21600,
                "full_threshold_pct": 80,
                "clear_threshold_pct": 70,
                "confirm_cycles": 2,
                "status": "draft",
                "verified_at": None,
                "created_by": "usr-dev-admin",
                "created_at": now,
                "note": "Example values; measure and verify before field use.",
            },
            session,
        )

        assignment_id = f"asgn-{device_id}-1"
        insert_if_missing(
            "device_assignments",
            {
                "_id": assignment_id,
                "device_id": device_id,
                "bin_id": bin_id,
                "assignment_version": 1,
                "active": True,
                "installed_at": installed_at,
                "removed_at": None,
                "installed_by": "usr-dev-admin",
                "removed_by": None,
                "reason": "Initial development seed",
                "created_at": now,
            },
            session,
        )
        insert_if_missing(
            "bin_state",
            {
                "_id": bin_id,
                "device_id": device_id,
                "assignment_id": assignment_id,
                "assignment_version": 1,
                "latest_boot_id": 0,
                "latest_seq": 0,
                "latest_message_id": None,
                "latest_quality": "unknown",
                "latest_sampled_at": None,
                "latest_received_at": None,
                "last_contact_at": None,
                "last_good": None,
                "alarm_active": None,
                "updated_at": now,
            },
            session,
        )


with mongo_client.start_session() as mongo_session:
    mongo_session.with_transaction(seed)

print("Schema-v2 development registry is ready; no telemetry was inserted.")
