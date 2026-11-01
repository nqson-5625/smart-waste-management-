"""GET /stats/waste-by-type."""

from datetime import datetime, timedelta, timezone

from helpers import BIN, RX_BASE_MS, assert_error, insert_bin, insert_collection, run_all, send


START = datetime.fromtimestamp(RX_BASE_MS / 1000, timezone.utc)


def window(hours=1):
    return (f"from={START.isoformat().replace('+00:00', 'Z')}"
            f"&to={(START + timedelta(hours=hours)).isoformat().replace('+00:00', 'Z')}")


def by_type(body):
    return {row["waste_type"]: row for row in body["items"]}


def test_waste_by_type(client, wdb, auth_as):
    insert_bin(wdb, BIN, waste="general")
    insert_bin(wdb, "WB-ORG", waste="organic")
    insert_bin(wdb, "WB-LAB", environment="lab", waste="organic")  # lab bins are not counted
    send(wdb, 1, fill=40.0)
    send(wdb, 2, fill=60.0)
    send(wdb, 3, reason="sensor_fault", quality="timeout", alarm=None)  # bad samples ignored
    run_all(wdb)
    inside = START + timedelta(minutes=30)
    insert_collection(wdb, "ev-1", BIN, "general", inside, weight=12.5)
    insert_collection(wdb, "ev-2", BIN, "general", inside)
    insert_collection(wdb, "ev-3", "WB-ORG", "organic", inside, weight=3.0)
    insert_collection(wdb, "ev-old", BIN, "general", START - timedelta(days=2), weight=99.0)

    response = client.get(f"/api/v1/stats/waste-by-type?{window()}", headers=auth_as("dispatcher"))
    assert response.status_code == 200, response.text
    rows = by_type(response.json())
    assert list(rows) == ["general", "organic", "recyclable", "hazardous", "other"]

    general = rows["general"]
    assert general["bin_count"] == 1 and general["avg_fill_pct"] == 50.0
    assert general["collection_count"] == 2
    assert general["known_weight_kg"] == 12.5 and general["known_weight_count"] == 1
    assert general["unknown_weight_count"] == 1

    organic = rows["organic"]
    assert organic["bin_count"] == 1 and organic["avg_fill_pct"] is None
    assert organic["known_weight_kg"] == 3.0

    empty = rows["hazardous"]
    assert empty == {"waste_type": "hazardous", "bin_count": 0, "collection_count": 0,
                     "avg_fill_pct": None, "known_weight_kg": None, "known_weight_count": 0,
                     "unknown_weight_count": 0}


def test_stats_rules(client, wdb, auth_as):
    end_before_start = (f"from={(START + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')}"
                        f"&to={START.isoformat().replace('+00:00', 'Z')}")
    admin = auth_as("admin")
    assert_error(client.get(f"/api/v1/stats/waste-by-type?{end_before_start}", headers=admin),
                 422, "VALIDATION")
    assert_error(client.get("/api/v1/stats/waste-by-type", headers=admin), 422, "VALIDATION")
    assert_error(client.get(f"/api/v1/stats/waste-by-type?{window()}",
                            headers=auth_as("collector")), 403, "FORBIDDEN")
