from datetime import datetime, timedelta, timezone

from helpers import BIN, run_all, send
from smartwaste_backend import worker


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
