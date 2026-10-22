"""Builders for schema-valid documents shared by the test modules."""

import hashlib
from datetime import datetime, timedelta, timezone

from smartwaste_backend.jobs import projection_worker

DEVICE, BIN, ASSIGNMENT = "bin-555", "WB-T1", "asgn-bin-555-1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
RX_BASE_MS = 1_790_000_000_000


def send(db, seq, reason="periodic", quality="ok", fill=50.0, alarm=False, boot=7,
         config_rev=1, mapped=True, rx_ms=None):
    """Insert one pending telemetry document exactly as ingestion would store it."""
    ok = quality == "ok"
    rx_ms = rx_ms or RX_BASE_MS + seq * 60_000
    message_id = f"{DEVICE}-{boot:08x}-{seq:08x}"
    db.telemetry.insert_one({
        "_id": message_id, "schema_version": 1, "message_id": message_id, "device_id": DEVICE,
        "gateway_id": "gw-t", "boot_id": boot, "seq": seq, "node_uptime_s": seq * 60,
        "sample_age_at_rx_s": 2, "reason": reason, "quality": quality,
        "distance_mm": int(1000 - fill * 9) if ok else None, "fill_pct": fill if ok else None,
        "battery_mv": None, "alarm_active": alarm, "lid_open": quality == "lid_open" or None,
        "valid_samples": 7 if ok else 2, "config_rev": config_rev, "dropped_reports": 0,
        "node_fw": "1.0.0", "gateway_fw": "1.0.0", "rssi_dbm": -90, "snr_db": 7.5,
        "gateway_boot_id": 1, "gateway_rx_uptime_ms": seq * 60_000,
        "gateway_received_at_ms": rx_ms, "sampled_at_ms": rx_ms - 2000,
        "time_quality": "gateway_estimated", "db_schema_version": 2,
        "bin_id": BIN if mapped else None, "assignment_id": ASSIGNMENT if mapped else None,
        "mapping_status": "resolved" if mapped else "unassigned",
        "sampled_at": EPOCH + timedelta(milliseconds=rx_ms - 2000),
        "gateway_received_at": EPOCH + timedelta(milliseconds=rx_ms),
        "received_at": EPOCH + timedelta(milliseconds=rx_ms + 500),
        "content_hash": hashlib.sha256(message_id.encode()).hexdigest(),
        "processing": {"state": "pending", "attempts": 0, "lease_owner": None,
                       "lease_until": None, "next_retry_at": EPOCH, "processed_at": None,
                       "last_error": None},
    })
    return message_id


def run_all(db):
    states = []
    while (state := projection_worker.process_one(db)) is not None:
        states.append(state)
    return states


def insert_bin(db, bin_id, environment="field", lng=105.8442, lat=21.005, waste="general"):
    now = datetime.now(timezone.utc)
    db.bins.insert_one({
        "_id": bin_id, "code": bin_id, "name": f"Thùng {bin_id}", "address": "Đại Cồ Việt",
        "ward_code": "BK", "location": {"type": "Point", "coordinates": [lng, lat]},
        "waste_type": waste, "capacity_l": 240, "status": "active", "environment": environment,
        "assignment_version": 1, "notes": None, "created_at": now, "updated_at": now,
    })
