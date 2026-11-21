"""POST/GET /collection-events."""

from datetime import datetime, timedelta, timezone

import pytest

from helpers import BIN, assert_error, insert_bin, insert_collection


URL = "/api/v1/collection-events"


def at(minutes_ago=10):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def post(client, headers, key="key-1", **body):
    return client.post(URL, json={"bin_id": BIN, "completed_at": at(), **body},
                       headers={**headers, "Idempotency-Key": key})


def insert_route(db, status="in_progress", worker="usr-collector"):
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1) if status == "in_progress" else None

    def stop(order, bin_id):
        return {"stop_order": order, "bin_id": bin_id,
                "location_snapshot": {"type": "Point", "coordinates": [105.84, 21.0]},
                "planned_fill_pct": 85.0, "planned_sampled_at": None, "status": "pending",
                "completed_at": None, "collection_event_id": None, "skip_reason": None}

    db.routes.insert_one({
        "_id": "rt-1", "service_date": now.strftime("%Y-%m-%d"), "assigned_worker_id": worker,
        "status": status, "depot": {"type": "Point", "coordinates": [105.84, 21.0]},
        "stops": [stop(1, BIN), stop(2, "WB-T2")], "planned_distance_m": 1200.0,
        "actual_distance_m": None, "baseline_distance_m": None, "actual_distance_source": None,
        "baseline_method": None, "started_at": started, "completed_at": None,
        "created_by": "usr-admin", "created_at": now, "updated_at": now,
    })


@pytest.fixture
def collector(wdb, auth_as):
    insert_bin(wdb, BIN)
    insert_bin(wdb, "WB-T2", waste="organic")
    return auth_as("collector")


def test_collect_off_route(client, wdb, collector):
    response = post(client, collector, note="Đầy tràn ra ngoài")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["worker_id"] == "usr-collector" and body["worker_name"] == "usr-collector"
    assert body["waste_type"] == "general" and body["route_id"] is None
    assert body["weight_source"] == "unknown" and body["measured_weight_kg"] is None
    assert wdb.audit_logs.count_documents({"action": "collection_create"}) == 1
    # confirming a collection never rewrites what the sensor reported
    assert wdb.bin_state.find_one({"_id": BIN})["last_good"] is None

    weighed = post(client, collector, key="key-2", measured_weight_kg=12.5)
    assert weighed.json()["weight_source"] == "manual"


def test_retry_with_same_key_returns_first_result(client, wdb, collector):
    body = {"completed_at": "2026-11-01T03:00:00Z"}
    first = post(client, collector, **body)
    assert first.status_code == 201
    # same instant written with another timezone is the same request
    again = post(client, collector, completed_at="2026-11-01T10:00:00+07:00")
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert wdb.collection_events.count_documents({}) == 1
    assert_error(post(client, collector, note="khác", **body), 409, "CONFLICT")


def test_collection_rules(client, wdb, collector, auth_as):
    missing_key = client.post(URL, json={"bin_id": BIN, "completed_at": at()}, headers=collector)
    assert_error(missing_key, 422, "VALIDATION")
    assert_error(post(client, collector, completed_at=at(-30)), 422, "VALIDATION")  # future
    assert_error(post(client, collector, bin_id="WB-NOPE"), 404, "NOT_FOUND")
    for bad in ({"weight_source": "scale"}, {"measured_weight_kg": 3, "weight_source": "unknown"},
                {"route_id": "rt-1"}, {"fill_before_pct": 120}):
        assert_error(post(client, collector, key="bad", **bad), 422, "VALIDATION")
    assert_error(client.post(URL, json={"bin_id": BIN, "completed_at": at()},
                             headers={"Idempotency-Key": "anon"}), 401, "UNAUTHORIZED")
    wdb.bins.update_one({"_id": BIN}, {"$set": {"status": "retired"}})
    assert_error(post(client, collector, key="retired"), 409, "CONFLICT")


def test_collect_route_stop(client, wdb, collector):
    insert_route(wdb)
    response = post(client, collector, route_id="rt-1", stop_order=1)
    assert response.status_code == 201, response.text
    stops = wdb.routes.find_one({"_id": "rt-1"})["stops"]
    assert stops[0]["status"] == "collected"
    assert stops[0]["collection_event_id"] == response.json()["id"]
    assert stops[1]["status"] == "pending"

    assert_error(post(client, collector, key="key-2", route_id="rt-1", stop_order=1),
                 409, "CONFLICT")  # already collected
    assert_error(post(client, collector, key="key-3", route_id="rt-1", stop_order=2),
                 422, "VALIDATION")  # stop 2 is another bin


def test_route_stop_needs_own_started_route(client, wdb, collector, auth_as):
    insert_route(wdb)
    assert_error(post(client, auth_as("admin"), route_id="rt-1", stop_order=1), 403, "FORBIDDEN")
    assert_error(post(client, collector, key="k-early", completed_at=at(120), route_id="rt-1",
                      stop_order=2, bin_id="WB-T2"), 422, "VALIDATION")  # before route start
    wdb.routes.update_one({"_id": "rt-1"}, {"$set": {"status": "assigned", "started_at": None}})
    assert_error(post(client, collector, key="k-assigned", route_id="rt-1", stop_order=1),
                 409, "CONFLICT")
    assert_error(post(client, collector, key="k-none", route_id="rt-x", stop_order=1),
                 404, "NOT_FOUND")


def test_list_collections(client, wdb, collector, auth_as):
    now = datetime.now(timezone.utc)
    insert_collection(wdb, "ev-mine-old", BIN, "general", now - timedelta(hours=3))
    insert_collection(wdb, "ev-mine-new", BIN, "general", now - timedelta(hours=1))
    insert_collection(wdb, "ev-other", "WB-T2", "organic", now - timedelta(hours=2))
    wdb.collection_events.update_one({"_id": "ev-other"}, {"$set": {"worker_id": "usr-x"}})

    own = client.get(f"{URL}?worker_id=usr-x", headers=collector).json()  # filter overridden
    assert [e["id"] for e in own["items"]] == ["ev-mine-new", "ev-mine-old"]

    admin = auth_as("admin")
    page1 = client.get(f"{URL}?limit=2", headers=admin).json()
    assert [e["id"] for e in page1["items"]] == ["ev-mine-new", "ev-other"]
    page2 = client.get(f"{URL}?limit=2&cursor={page1['next_cursor']}", headers=admin).json()
    assert [e["id"] for e in page2["items"]] == ["ev-mine-old"] and page2["next_cursor"] is None
    assert [e["id"] for e in client.get(f"{URL}?bin_id=WB-T2", headers=admin)
            .json()["items"]] == ["ev-other"]

    since = (now - timedelta(minutes=150)).isoformat().replace("+00:00", "Z")
    recent = client.get(f"{URL}?from={since}", headers=admin).json()["items"]
    assert [e["id"] for e in recent] == ["ev-mine-new", "ev-other"]
    assert_error(client.get(f"{URL}?from={since}&to=2020-01-01T00:00:00Z", headers=admin),
                 422, "VALIDATION")
