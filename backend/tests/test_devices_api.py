"""POST /devices, POST /devices/{id}/configs, POST /bins/{id}/assignments."""

from datetime import datetime, timezone

import pytest

from helpers import BIN, assert_error, insert_bin, insert_gateway, run_all, send


def device_body(device_id="bin-701", **extra):
    return {"id": device_id, "hardware_model": "ESP32-C3 Super Mini", "firmware_version": "1.0.0",
            "gateway_ids": ["gw-test"],
            "sensors": [{"sensor_id": "us-1", "type": "ultrasonic", "model": "HC-SR04"}], **extra}


CONFIG = {"config_rev": 1, "empty_distance_mm": 1000, "full_distance_mm": 200,
          "sample_interval_s": 60, "report_interval_s": 21600}


@pytest.fixture
def admin(wdb, auth_as):
    insert_gateway(wdb)
    insert_bin(wdb, "WB-301")
    return auth_as("admin")


# ---------------------------------------------------------------- devices

def test_create_device(client, admin, wdb):
    response = client.post("/api/v1/devices", json=device_body(), headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["lifecycle"] == "stock" and body["enabled"] is True
    assert body["applied_config_rev"] is None
    assert body["sensors"][0]["status"] == "active"
    assert wdb.audit_logs.count_documents({"action": "device_create"}) == 1


def test_create_device_rules(client, admin, auth_as):
    assert client.post("/api/v1/devices", json=device_body(), headers=admin).status_code == 201
    assert_error(client.post("/api/v1/devices", json=device_body(), headers=admin),
                 409, "CONFLICT")
    unknown_gw = client.post("/api/v1/devices", headers=admin,
                             json=device_body("bin-702", gateway_ids=["gw-nowhere"]))
    assert_error(unknown_gw, 422, "VALIDATION")
    assert unknown_gw.json()["details"]["unknown"] == ["gw-nowhere"]
    for bad in ({"id": "sensor-1"}, {"gateway_ids": []}, {"gateway_ids": ["bad id"]},
                {"sensors": [{"sensor_id": "lid", "type": "lid_switch", "model": "reed"}]},
                {"sensors": [{"sensor_id": "us-1", "type": "ultrasonic", "model": ""}]}):
        assert_error(client.post("/api/v1/devices", json={**device_body("bin-703"), **bad},
                                 headers=admin), 422, "VALIDATION")
    assert_error(client.post("/api/v1/devices", json=device_body("bin-704"),
                             headers=auth_as("dispatcher")), 403, "FORBIDDEN")


# ---------------------------------------------------------------- configs

def test_create_config_verifies_and_applies(client, admin, wdb):
    client.post("/api/v1/devices", json=device_body(), headers=admin)
    response = client.post("/api/v1/devices/bin-701/configs", json=CONFIG, headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "verified" and body["verified_at"].endswith("Z")
    assert body["sensor_id"] == "us-1" and body["full_threshold_pct"] == 80
    assert body["requeued_messages"] == 0
    assert wdb.devices.find_one({"_id": "bin-701"})["applied_config_rev"] == 1


def test_create_config_rules(client, admin):
    client.post("/api/v1/devices", json=device_body(), headers=admin)
    assert client.post("/api/v1/devices/bin-701/configs", json=CONFIG,
                       headers=admin).status_code == 201
    assert_error(client.post("/api/v1/devices/bin-701/configs", json=CONFIG, headers=admin),
                 409, "CONFLICT")
    assert_error(client.post("/api/v1/devices/bin-999/configs", json=CONFIG, headers=admin),
                 404, "NOT_FOUND")
    for bad in ({"full_distance_mm": 1000}, {"report_interval_s": 30}, {"config_rev": 0}):
        assert_error(client.post("/api/v1/devices/bin-701/configs",
                                 json={**CONFIG, "config_rev": 2, **bad}, headers=admin),
                     422, "VALIDATION")


def test_config_requeues_blocked_telemetry(client, wdb, admin):
    """Readings blocked for an unknown calibration flow once it is declared."""
    client.post("/api/v1/devices", json=device_body("bin-555"), headers=admin)
    send(wdb, 1, fill=55.0, config_rev=2)  # helpers' device bin-555 / bin WB-T1
    assert run_all(wdb) == ["blocked"]

    response = client.post("/api/v1/devices/bin-555/configs", headers=admin,
                           json={**CONFIG, "config_rev": 2})
    assert response.json()["requeued_messages"] == 1
    assert run_all(wdb) == ["applied"]
    assert wdb.bin_state.find_one({"_id": BIN})["last_good"]["fill_pct"] == 55.0


# ------------------------------------------------------------ assignments

def test_assign_device_to_empty_bin(client, admin, wdb):
    client.post("/api/v1/devices", json=device_body(), headers=admin)
    response = client.post("/api/v1/bins/WB-301/assignments", headers=admin,
                           json={"device_id": "bin-701", "reason": "Lắp mới"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["assignment_version"] == 2  # insert_bin starts at version 1
    assert body["replaced_device_id"] is None

    state = wdb.bin_state.find_one({"_id": "WB-301"})
    assert state["device_id"] == "bin-701" and state["assignment_id"] == body["id"]
    assert state["latest_quality"] == "unknown" and state["last_good"] is None
    assert wdb.devices.find_one({"_id": "bin-701"})["lifecycle"] == "installed"
    detail = client.get("/api/v1/bins/WB-301", headers=admin).json()
    assert detail["device"]["id"] == "bin-701"


def test_replacing_device_closes_old_assignment_and_alerts(client, admin, wdb):
    for device_id in ("bin-701", "bin-702"):
        client.post("/api/v1/devices", json=device_body(device_id), headers=admin)
    client.post("/api/v1/bins/WB-301/assignments", headers=admin,
                json={"device_id": "bin-701", "reason": "Lắp mới"})
    now = datetime.now(timezone.utc)
    wdb.alerts.insert_one({
        "_id": "alr-full-test", "scope_type": "bin", "scope_id": "WB-301", "bin_id": "WB-301",
        "type": "full", "status": "open", "active": True, "severity": "warning",
        "opened_at": now, "acknowledged_at": None, "acknowledged_by": None, "resolved_at": None,
        "resolve_reason": None, "opened_message_id": None, "last_message_id": None,
        "updated_at": now,
    })

    response = client.post("/api/v1/bins/WB-301/assignments", headers=admin,
                           json={"device_id": "bin-702", "reason": "Thay thiết bị hỏng"})
    assert response.status_code == 201, response.text
    assert response.json()["replaced_device_id"] == "bin-701"

    old = wdb.device_assignments.find_one({"device_id": "bin-701"})
    assert old["active"] is False and old["removed_at"] > old["installed_at"]
    assert wdb.device_assignments.count_documents({"bin_id": "WB-301", "active": True}) == 1
    assert wdb.devices.find_one({"_id": "bin-701"})["lifecycle"] == "stock"
    alert = wdb.alerts.find_one({"_id": "alr-full-test"})
    assert alert["status"] == "resolved" and alert["resolve_reason"] == "device_replaced"
    assert wdb.bins.find_one({"_id": "WB-301"})["assignment_version"] == 3


def test_assignment_rules(client, admin, wdb, auth_as):
    insert_bin(wdb, "WB-302")
    client.post("/api/v1/devices", json=device_body(), headers=admin)
    client.post("/api/v1/bins/WB-301/assignments", headers=admin,
                json={"device_id": "bin-701", "reason": "Lắp mới"})

    busy = client.post("/api/v1/bins/WB-302/assignments", headers=admin,
                       json={"device_id": "bin-701", "reason": "x"})
    assert_error(busy, 409, "CONFLICT")
    assert busy.json()["details"]["bin_id"] == "WB-301"
    assert_error(client.post("/api/v1/bins/WB-302/assignments", headers=admin,
                             json={"device_id": "bin-999", "reason": "x"}), 404, "NOT_FOUND")
    assert_error(client.post("/api/v1/bins/WB-NOPE/assignments", headers=admin,
                             json={"device_id": "bin-701", "reason": "x"}), 404, "NOT_FOUND")
    wdb.bins.update_one({"_id": "WB-302"}, {"$set": {"status": "retired"}})
    client.post("/api/v1/devices", json=device_body("bin-702"), headers=admin)
    assert_error(client.post("/api/v1/bins/WB-302/assignments", headers=admin,
                             json={"device_id": "bin-702", "reason": "x"}), 409, "CONFLICT")
    assert_error(client.post("/api/v1/bins/WB-301/assignments", headers=auth_as("dispatcher"),
                             json={"device_id": "bin-702", "reason": "x"}), 403, "FORBIDDEN")
