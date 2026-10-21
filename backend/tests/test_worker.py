import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from smartwaste_backend import worker

DEVICE, BIN, ASSIGNMENT = "bin-555", "WB-T1", "asgn-bin-555-1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
COLLECTIONS = ("telemetry", "bin_state", "alerts", "audit_logs", "device_configs")


@pytest.fixture
def wdb(db):
    for name in COLLECTIONS:
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


def send(db, seq, reason="periodic", quality="ok", fill=50.0, alarm=False, boot=7,
         config_rev=1, mapped=True):
    """Insert one schema-valid pending telemetry document, as ingestion would."""
    ok = quality == "ok"
    rx_ms = 1_790_000_000_000 + seq * 60_000
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
    while (state := worker.process_one(db)) is not None:
        states.append(state)
    return states


def active_alerts(db, alert_type):
    return list(db.alerts.find({"type": alert_type, "active": True}))


def test_full_opens_one_alert_even_when_repeated(wdb):
    send(wdb, 1, fill=40.0)
    send(wdb, 2, reason="full", fill=85.0, alarm=True)
    send(wdb, 3, fill=88.0, alarm=True)  # still full on the next periodic report
    assert run_all(wdb) == ["applied"] * 3

    state = wdb.bin_state.find_one({"_id": BIN})
    assert state["alarm_active"] is True
    assert state["last_good"]["fill_pct"] == 88.0
    assert (state["latest_boot_id"], state["latest_seq"]) == (7, 3)
    alerts = active_alerts(wdb, "full")
    assert len(alerts) == 1 and alerts[0]["status"] == "open"
    assert alerts[0]["bin_id"] == BIN and alerts[0]["last_message_id"].endswith("00000003")
    assert wdb.audit_logs.count_documents({"action": "alert_open"}) == 1


def test_cleared_resolves_full_alert(wdb):
    send(wdb, 1, reason="full", fill=90.0, alarm=True)
    send(wdb, 2, reason="cleared", fill=10.0, alarm=False)
    run_all(wdb)
    assert active_alerts(wdb, "full") == []
    resolved = wdb.alerts.find_one({"type": "full"})
    assert resolved["status"] == "resolved" and resolved["resolve_reason"] == "sensor_cleared"
    assert wdb.bin_state.find_one({"_id": BIN})["alarm_active"] is False


def test_bad_quality_keeps_last_good_and_opens_sensor_fault(wdb):
    send(wdb, 1, fill=60.0, alarm=False)
    send(wdb, 2, reason="sensor_fault", quality="timeout", alarm=None)
    run_all(wdb)
    state = wdb.bin_state.find_one({"_id": BIN})
    assert state["latest_quality"] == "timeout"
    assert state["last_good"]["fill_pct"] == 60.0  # never replaced by a bad sample
    assert state["alarm_active"] is False  # null alarm keeps the known value
    assert len(active_alerts(wdb, "sensor_fault")) == 1

    send(wdb, 3, reason="sensor_recovered", fill=62.0, alarm=False)
    run_all(wdb)
    assert active_alerts(wdb, "sensor_fault") == []


def test_older_message_arriving_late_is_ignored(wdb):
    send(wdb, 5, fill=70.0)
    run_all(wdb)
    send(wdb, 4, reason="full", fill=95.0, alarm=True)  # older tuple, arrives after
    assert run_all(wdb) == ["ignored"]
    state = wdb.bin_state.find_one({"_id": BIN})
    assert state["latest_seq"] == 5 and state["last_good"]["fill_pct"] == 70.0
    assert active_alerts(wdb, "full") == []


def test_new_boot_is_newer_than_high_seq(wdb):
    send(wdb, 900, fill=20.0, boot=7)
    send(wdb, 1, fill=30.0, boot=8)
    assert run_all(wdb) == ["applied", "applied"]
    assert wdb.bin_state.find_one({"_id": BIN})["latest_boot_id"] == 8


def test_unverified_config_is_blocked(wdb):
    send(wdb, 1, config_rev=2)
    assert run_all(wdb) == ["blocked"]
    doc = wdb.telemetry.find_one()
    assert "not verified" in doc["processing"]["last_error"]
    assert wdb.bin_state.find_one({"_id": BIN})["latest_seq"] == 0


def test_unassigned_mapping_is_ignored(wdb):
    send(wdb, 1, mapped=False)
    assert run_all(wdb) == ["ignored"]


def test_leased_document_is_not_claimed_twice(wdb):
    message_id = send(wdb, 1)
    wdb.telemetry.update_one({"_id": message_id}, {"$set": {
        "processing.lease_owner": "other-worker",
        "processing.lease_until": datetime.now(timezone.utc) + timedelta(seconds=30),
    }})
    assert worker.process_one(wdb) is None
    wdb.telemetry.update_one({"_id": message_id}, {"$set": {
        "processing.lease_until": datetime.now(timezone.utc) - timedelta(seconds=1),
    }})
    assert worker.process_one(wdb) == "applied"  # expired lease: safe to take over
