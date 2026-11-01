from datetime import datetime, timedelta, timezone

import pytest

from helpers import BIN, DEVICE, RX_BASE_MS, assert_error, insert_bin, run_all, send


@pytest.fixture
def full_bin(wdb):
    """BIN in the field with one good sample then a confirmed full report."""
    insert_bin(wdb, BIN)
    send(wdb, 1, fill=40.0)
    send(wdb, 2, reason="full", fill=85.0, alarm=True)
    run_all(wdb)
    return wdb


# ------------------------------------------------------------------ /bins

def test_bins_requires_login(client, wdb):
    assert_error(client.get("/api/v1/bins"), 401, "UNAUTHORIZED")


def test_list_bins_shows_state_and_hides_lab_bins(client, full_bin, auth_as):
    insert_bin(full_bin, "WB-LAB", environment="lab")
    insert_bin(full_bin, "WB-T2")  # field bin without device or data
    body = client.get("/api/v1/bins", headers=auth_as("collector")).json()

    assert [item["id"] for item in body["items"]] == [BIN, "WB-T2"]
    first, second = body["items"]
    assert (first["lat"], first["lng"]) == (21.005, 105.8442)
    assert first["state"]["fill_pct"] == 85.0 and first["state"]["alarm_active"] is True
    assert first["state"]["latest_quality"] == "ok" and first["state"]["device_id"] == DEVICE
    assert first["state"]["sampled_at"].endswith("Z")
    assert first["state"]["fresh"] is False  # fixture samples are weeks old
    assert second["state"] is None
    assert body["next_cursor"] is None


def test_list_bins_filters_full_and_fresh(client, full_bin, auth_as):
    insert_bin(full_bin, "WB-T2")
    headers = auth_as("dispatcher")
    assert [b["id"] for b in client.get("/api/v1/bins?full=true", headers=headers)
            .json()["items"]] == [BIN]
    assert [b["id"] for b in client.get("/api/v1/bins?full=false", headers=headers)
            .json()["items"]] == ["WB-T2"]
    assert client.get("/api/v1/bins?fresh=true", headers=headers).json()["items"] == []

    full_bin.bin_state.update_one({"_id": BIN}, {"$set": {
        "last_good.sampled_at": datetime.now(timezone.utc) - timedelta(minutes=10)}})
    fresh = client.get("/api/v1/bins?fresh=true", headers=headers).json()["items"]
    assert [b["id"] for b in fresh] == [BIN] and fresh[0]["state"]["fresh"] is True


def test_list_bins_pages_with_cursor(client, wdb, auth_as):
    for bin_id in ("WB-A", "WB-B", "WB-C"):
        insert_bin(wdb, bin_id)
    headers = auth_as("admin")
    page1 = client.get("/api/v1/bins?limit=2", headers=headers).json()
    assert [b["id"] for b in page1["items"]] == ["WB-A", "WB-B"]
    page2 = client.get(f"/api/v1/bins?limit=2&cursor={page1['next_cursor']}",
                       headers=headers).json()
    assert [b["id"] for b in page2["items"]] == ["WB-C"] and page2["next_cursor"] is None
    assert_error(client.get("/api/v1/bins?cursor=@@bad", headers=headers), 422, "VALIDATION")
    assert_error(client.get("/api/v1/bins?limit=101", headers=headers), 422, "VALIDATION")


def test_bin_detail_has_open_alerts(client, full_bin, auth_as):
    body = client.get(f"/api/v1/bins/{BIN}", headers=auth_as("collector")).json()
    assert body["id"] == BIN and body["notes"] is None
    assert body["device"] is None  # no devices document in this fixture
    assert [a["type"] for a in body["open_alerts"]] == ["full"]
    assert_error(client.get("/api/v1/bins/WB-NOPE", headers=auth_as("admin")), 404, "NOT_FOUND")


# -------------------------------------------------------------- telemetry

def window():
    start = datetime.fromtimestamp(RX_BASE_MS / 1000, timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), (start + timedelta(hours=1)).isoformat() \
        .replace("+00:00", "Z")


def test_telemetry_history_newest_first_with_paging(client, full_bin, auth_as):
    start, end = window()
    headers = auth_as("dispatcher")
    url = f"/api/v1/bins/{BIN}/telemetry?from={start}&to={end}&limit=1"
    page1 = client.get(url, headers=headers).json()
    assert [row["reason"] for row in page1["items"]] == ["full"]
    page2 = client.get(f"{url}&cursor={page1['next_cursor']}", headers=headers).json()
    assert [row["fill_pct"] for row in page2["items"]] == [40.0]
    assert page2["next_cursor"] is None


def test_telemetry_rules(client, full_bin, auth_as):
    start, end = window()
    assert_error(client.get(f"/api/v1/bins/{BIN}/telemetry?from={start}&to={end}",
                            headers=auth_as("collector")), 403, "FORBIDDEN")
    admin = auth_as("admin")
    assert_error(client.get(f"/api/v1/bins/{BIN}/telemetry?from={end}&to={start}",
                            headers=admin), 422, "VALIDATION")
    assert_error(client.get(f"/api/v1/bins/{BIN}/telemetry", headers=admin), 422, "VALIDATION")
    assert_error(client.get(f"/api/v1/bins/WB-NOPE/telemetry?from={start}&to={end}",
                            headers=admin), 404, "NOT_FOUND")


# ----------------------------------------------------------------- alerts

def test_alert_list_and_ack_flow(client, full_bin, auth_as):
    headers = auth_as("collector")
    alerts = client.get("/api/v1/alerts", headers=headers).json()["items"]
    assert [(a["type"], a["status"]) for a in alerts] == [("full", "open")]
    alert_id = alerts[0]["id"]

    acked = client.post(f"/api/v1/alerts/{alert_id}/ack", headers=headers)
    assert acked.status_code == 200
    assert acked.json()["status"] == "acknowledged"
    assert acked.json()["acknowledged_by"] == "usr-collector"
    again = client.post(f"/api/v1/alerts/{alert_id}/ack", headers=headers)
    assert again.status_code == 200 and again.json()["status"] == "acknowledged"

    assert client.get("/api/v1/alerts", headers=headers).json()["items"] == []
    both = client.get("/api/v1/alerts?status=open,acknowledged", headers=headers).json()
    assert [a["id"] for a in both["items"]] == [alert_id]
    assert full_bin.audit_logs.count_documents({"action": "alert_ack"}) == 1


def test_ack_errors(client, full_bin, auth_as):
    headers = auth_as("dispatcher")
    alert_id = client.get("/api/v1/alerts", headers=headers).json()["items"][0]["id"]
    send(full_bin, 3, reason="cleared", fill=5.0, alarm=False)
    run_all(full_bin)  # sensor clears -> alert resolved
    assert_error(client.post(f"/api/v1/alerts/{alert_id}/ack", headers=headers), 409, "CONFLICT")
    assert_error(client.post("/api/v1/alerts/nope/ack", headers=headers), 404, "NOT_FOUND")
    assert_error(client.get("/api/v1/alerts?status=bogus", headers=headers), 422, "VALIDATION")


def test_alert_filters_and_paging(client, wdb, auth_as):
    insert_bin(wdb, BIN)
    send(wdb, 1, reason="full", fill=90.0, alarm=True)
    send(wdb, 2, reason="sensor_fault", quality="timeout", alarm=None)
    run_all(wdb)
    headers = auth_as("admin")
    assert [a["type"] for a in client.get("/api/v1/alerts?type=sensor_fault", headers=headers)
            .json()["items"]] == ["sensor_fault"]
    page1 = client.get("/api/v1/alerts?limit=1", headers=headers).json()
    page2 = client.get(f"/api/v1/alerts?limit=1&cursor={page1['next_cursor']}",
                       headers=headers).json()
    assert {page1["items"][0]["type"], page2["items"][0]["type"]} == {"full", "sensor_fault"}
    assert page2["next_cursor"] is None
