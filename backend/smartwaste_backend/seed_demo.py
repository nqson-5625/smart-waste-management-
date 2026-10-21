"""Seed simulated field bins so the web map and worker have data to show.

Usage: python -m smartwaste_backend.seed_demo [count]   (default 10, max 200)

Each bin WB-1xx gets its own simulated device bin-9xxxx on gateway gw-simulator,
an active assignment and a verified calibration, so telemetry from
``MOCK_DEVICE_NUMBER=9xxxx python mock_publisher.py`` flows through the real
ingestion -> worker -> API path. Also verifies the calibration of the default
simulator device bin-900001. The real device bin-001 is left untouched: its
calibration must be measured on the physical bin first.
Re-running only adds what is missing.
"""

import sys
from datetime import datetime, timezone

from .db import get_database


GATEWAY_ID = "gw-simulator"
ACTOR = "usr-admin"
# Spread around Đại Cồ Việt, Hai Bà Trưng (same area as the web mock data).
BASE_LAT, BASE_LNG = 21.0050, 105.8442
WASTE_TYPES = ("general", "general", "organic", "recyclable", "general", "hazardous")
INSTALLED_AT = datetime(2026, 10, 1, tzinfo=timezone.utc)


def insert_if_missing(collection, document):
    collection.update_one({"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True)


def verify_config(database, device_id, now):
    database.device_configs.update_one(
        {"device_id": device_id, "config_rev": 1, "status": "draft"},
        {"$set": {"status": "verified", "verified_at": now}},
    )
    database.devices.update_one(
        {"_id": device_id, "applied_config_rev": None},
        {"$set": {"applied_config_rev": 1, "updated_at": now}},
    )


def seed_bin(database, index, now):
    number = 90100 + index
    bin_id, device_id = f"WB-{100 + index}", f"bin-{number}"
    assignment_id = f"asgn-{device_id}-1"
    lat = BASE_LAT + ((index * 7) % 23 - 11) * 0.0006
    lng = BASE_LNG + ((index * 11) % 29 - 14) * 0.0006

    insert_if_missing(database.bins, {
        "_id": bin_id, "code": bin_id, "name": f"Điểm thu gom {100 + index}",
        "address": f"Ngõ {index} Đại Cồ Việt, Hai Bà Trưng", "ward_code": "BK",
        "location": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
        "waste_type": WASTE_TYPES[index % len(WASTE_TYPES)], "capacity_l": 240,
        "status": "active", "environment": "field", "assignment_version": 1,
        "notes": "Thùng mô phỏng (seed_demo)", "created_at": now, "updated_at": now,
    })
    insert_if_missing(database.devices, {
        "_id": device_id, "hardware_model": "Simulated ESP32-C3", "serial_number": None,
        "firmware_version": "1.0.0", "gateway_ids": [GATEWAY_ID], "enabled": True,
        "lifecycle": "installed", "applied_config_rev": 1,
        "sensors": [{"sensor_id": "level-01", "type": "ultrasonic", "model": "HC-SR04",
                     "status": "active"}],
        "commissioned_at": INSTALLED_AT, "notes": "Thiết bị mô phỏng (seed_demo)",
        "created_at": now, "updated_at": now,
    })
    insert_if_missing(database.device_configs, {
        "_id": f"{device_id}:1", "device_id": device_id, "config_rev": 1,
        "sensor_id": "level-01", "empty_distance_mm": 1000, "full_distance_mm": 100,
        "sample_interval_s": 60, "report_interval_s": 21600, "full_threshold_pct": 80,
        "clear_threshold_pct": 70, "confirm_cycles": 2, "status": "verified",
        "verified_at": now, "created_by": ACTOR, "created_at": now,
        "note": "Hiệu chuẩn mô phỏng (seed_demo)",
    })
    insert_if_missing(database.device_assignments, {
        "_id": assignment_id, "device_id": device_id, "bin_id": bin_id,
        "assignment_version": 1, "active": True, "installed_at": INSTALLED_AT,
        "removed_at": None, "installed_by": ACTOR, "removed_by": None,
        "reason": "Simulated install (seed_demo)", "created_at": now,
    })
    insert_if_missing(database.bin_state, {
        "_id": bin_id, "device_id": device_id, "assignment_id": assignment_id,
        "assignment_version": 1, "latest_boot_id": 0, "latest_seq": 0,
        "latest_message_id": None, "latest_quality": "unknown", "latest_sampled_at": None,
        "latest_received_at": None, "last_contact_at": None, "last_good": None,
        "alarm_active": None, "updated_at": now,
    })
    return number


def main(count):
    database = get_database()
    if not database.gateways.find_one({"_id": GATEWAY_ID}):
        raise SystemExit("gw-simulator missing; run iot-ingestion seed_registry first")
    now = datetime.now(timezone.utc)
    verify_config(database, "bin-900001", now)
    numbers = [seed_bin(database, index, now) for index in range(1, count + 1)]
    print(f"Ready: WB-101..WB-{100 + count} on devices bin-{numbers[0]}..bin-{numbers[-1]}")


if __name__ == "__main__":
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    if not 1 <= total <= 200:
        raise SystemExit("count must be between 1 and 200")
    main(total)
