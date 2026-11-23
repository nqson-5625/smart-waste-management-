"""Routes: automatic generation (job and "generate now"), status changes, report."""

from datetime import datetime, timedelta

import pytest

from helpers import ASSIGNMENT, BIN, DEVICE, assert_error, insert_bin, insert_collection, send
from smartwaste_backend.core.common import to_ms, utcnow
from smartwaste_backend.jobs import route_worker
from smartwaste_backend.services import osrm_service, routes_service
from smartwaste_backend.services import route_planner_service as rp


def ready_bin(db, bin_id, fill, now, lng=105.845, lat=21.006, alarm=False, quality="ok",
              age=timedelta(minutes=30), device=None, assignment=None):
    """A field bin with a device whose last good reading is ``fill`` % taken ``age`` ago."""
    if not db.bins.find_one({"_id": bin_id}):
        insert_bin(db, bin_id, lng=lng, lat=lat)
    sampled = now - age
    db.bin_state.replace_one({"_id": bin_id}, {
        "_id": bin_id, "device_id": device or f"dev-{bin_id}",
        "assignment_id": assignment or f"asgn-{bin_id}", "assignment_version": 1,
        "latest_boot_id": 1, "latest_seq": 1, "latest_message_id": f"m-{bin_id}",
        "latest_quality": quality, "latest_sampled_at": sampled, "latest_received_at": sampled,
        "last_contact_at": sampled,
        "last_good": {"message_id": f"m-{bin_id}", "fill_pct": fill, "distance_mm": 500,
                      "sampled_at": sampled, "received_at": sampled,
                      "time_quality": "gateway_estimated"},
        "alarm_active": alarm, "updated_at": now,
    }, upsert=True)


@pytest.fixture
def team(make_user, login):
    """Admin plus collectors c1, c2 (active) and c3 (disabled); returns auth headers."""
    def headers(user_id, roles, status="active"):
        email = make_user(user_id, roles, status)
        if status != "active":
            return None
        return {"Authorization": f"Bearer {login(email).json()['access_token']}"}
    return {"admin": headers("usr-admin", ["admin"]),
            "c1": headers("usr-c1", ["collector"]), "c2": headers("usr-c2", ["collector"]),
            "c3": headers("usr-c3", ["collector"], status="disabled")}


def generate(client, headers):
    response = client.post("/api/v1/routes/generate", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_generate_picks_full_fresh_bins_and_splits_them(client, wdb, team):
    now = utcnow()
    ready_bin(wdb, "WB-A", 90, now, lng=105.850, lat=21.010)
    ready_bin(wdb, "WB-B", 60, now, lng=105.836, lat=21.000, alarm=True)  # firmware says full
    ready_bin(wdb, "WB-C", 50, now)                                         # not full
    ready_bin(wdb, "WB-D", 95, now, age=timedelta(hours=10))                # stale reading
    ready_bin(wdb, "WB-E", 95, now, quality="lid_open")                    # sensor in doubt
    ready_bin(wdb, "WB-F", 95, now)
    insert_collection(wdb, "ev-f", "WB-F", "general", now)  # emptied after its last reading

    routes = generate(client, team["admin"])
    assert sorted(s["bin_id"] for r in routes for s in r["stops"]) == ["WB-A", "WB-B"]
    assert sorted(r["assigned_worker_id"] for r in routes) == ["usr-c1", "usr-c2"]  # not c3
    assert {r["status"] for r in routes} == {"assigned"}
    route = routes[0]
    assert route["stops"][0]["status"] == "pending" and route["stops"][0]["lat"] is not None
    assert route["planned_distance_m"] > 0 and route["trip_count"] == 1
    # baseline: every active field bin (A-F) by code; far longer than either route
    assert route["baseline_distance_m"] > sum(r["planned_distance_m"] for r in routes)
    assert route["created_by"] == "usr-admin" and route["assigned_worker_name"]

    assert generate(client, team["admin"]) == []  # bins already in an unfinished route
    mine = client.get("/api/v1/routes", headers=team["c1"]).json()["items"]
    assert [r["assigned_worker_id"] for r in mine] == ["usr-c1"]  # collectors see their own
    assert wdb.audit_logs.count_documents({"action": "route_create"}) == 2


def test_forecast_picks_a_bin_that_will_overflow_before_next_shift(wdb):
    now = datetime(2026, 9, 21, 23, 0)  # 06:00 in Vietnam; next shift 14:00, 8 h away
    insert_bin(wdb, BIN)
    ready_bin(wdb, BIN, 70, now, age=timedelta(hours=1), device=DEVICE, assignment=ASSIGNMENT)
    # +30 % in 9 h = 3.3 %/h: 70 + 1.3 x 3.3 x 8 = 105 % before 14:00
    send(wdb, 1, fill=40.0, rx_ms=to_ms(now - timedelta(hours=10)) + 2000)
    send(wdb, 2, fill=70.0, rx_ms=to_ms(now - timedelta(hours=1)) + 2000)
    ready_bin(wdb, "WB-SLOW", 70, now, age=timedelta(hours=1))  # no history: threshold only

    routes = routes_service.generate(now, "usr-admin", "rt-test")
    assert [s["bin_id"] for r in routes for s in r["stops"]] == [BIN]
    assert routes[0]["status"] == "planned"  # no collector at all: admin assigns by hand


def test_shift_job_runs_once_and_replaces_unstarted_routes(wdb, make_user):
    make_user("usr-c1", ["collector"])
    morning = datetime(2026, 11, 20, 23, 5)  # 06:05 on 21/11 in Vietnam
    ready_bin(wdb, "WB-A", 90, morning, age=timedelta(0))
    assert route_worker.run_due_shift(datetime(2026, 11, 20, 21, 0)) is None  # 04:00: no shift

    first = route_worker.run_due_shift(morning)
    assert [r["id"] for r in first] == ["rt-20261121-0600-1"]
    assert first[0]["service_date"] == "2026-11-21"
    assert route_worker.run_due_shift(morning + timedelta(minutes=30)) is None  # once per shift

    afternoon = datetime(2026, 11, 21, 7, 0)  # 14:00: the morning route was never started
    second = route_worker.run_due_shift(afternoon)
    assert [r["id"] for r in second] == ["rt-20261121-1400-1"]
    assert wdb.routes.find_one({"_id": "rt-20261121-0600-1"})["status"] == "cancelled"
    assert second[0]["stops"][0]["bin_id"] == "WB-A" and second[0]["created_by"] == \
        "system:route-worker"


def test_collector_runs_a_route_and_the_report_counts_it(client, wdb, team):
    now = utcnow()
    ready_bin(wdb, "WB-A", 90, now, lng=105.850, lat=21.010)
    ready_bin(wdb, "WB-B", 85, now, lng=105.851, lat=21.011)
    ready_bin(wdb, "WB-C", 10, now, lng=105.830, lat=20.995)  # only in the baseline
    wdb.users.update_one({"_id": "usr-c2"}, {"$set": {"status": "disabled"}})
    [route] = generate(client, team["admin"])
    rid, url = route["id"], f"/api/v1/routes/{route['id']}/status"
    assert route["assigned_worker_id"] == "usr-c1" and route["stop_count"] == 2

    assert_error(client.patch(url, json={"status": "in_progress"}, headers=team["admin"]),
                 403, "FORBIDDEN")  # only the assigned collector starts it
    started = client.patch(url, json={"status": "in_progress"}, headers=team["c1"])
    assert started.status_code == 200 and started.json()["started_at"]

    first = route["stops"][0]
    collected = client.post("/api/v1/collection-events", headers={
        **team["c1"], "Idempotency-Key": "k-1"}, json={
        "bin_id": first["bin_id"], "completed_at": utcnow().isoformat() + "Z",
        "route_id": rid, "stop_order": first["stop_order"]})
    assert collected.status_code == 201, collected.text

    assert_error(client.patch(url, json={"status": "completed"}, headers=team["c1"]),
                 422, "VALIDATION")  # one stop still pending: say why
    done = client.patch(url, headers=team["c1"], json={
        "status": "completed", "skip_reason": "Xe chắn lối vào",
        "actual_distance_m": 2500, "actual_distance_source": "odometer"})
    assert done.status_code == 200, done.text
    body = done.json()
    assert [s["status"] for s in body["stops"]] == ["collected", "skipped"]
    assert body["stops"][1]["skip_reason"] == "Xe chắn lối vào" and body["completed_at"]
    assert_error(client.patch(url, json={"status": "in_progress"}, headers=team["c1"]),
                 409, "CONFLICT")
    assert_error(client.patch(url, json={"status": "cancelled"}, headers=team["admin"]),
                 409, "CONFLICT")

    day = route["service_date"]
    report = client.get(f"/api/v1/reports/routes?from={day}&to={day}", headers=team["admin"])
    assert report.status_code == 200, report.text
    [row] = report.json()["items"]
    assert (row["route_count"], row["stop_count"], row["collected_count"]) == (1, 2, 1)
    assert row["planned_distance_m"] == route["planned_distance_m"]
    assert row["actual_distance_m"] == 2500 and row["baseline_trips"] == 1
    expected = (row["baseline_distance_m"] - row["planned_distance_m"]) \
        / row["baseline_distance_m"] * 100
    assert row["planned_reduction_pct"] == round(expected, 1)
    summary = report.json()["summary"]
    assert summary["route_count"] == 1 and summary["actual_distance_m"] == 2500


def test_admin_assigns_reassigns_and_cancels(client, wdb, team):
    wdb.users.update_many({"roles": "collector"}, {"$set": {"status": "disabled"}})
    ready_bin(wdb, "WB-A", 90, utcnow())
    [route] = generate(client, team["admin"])
    assert route["status"] == "planned" and route["assigned_worker_id"] is None
    url = f"/api/v1/routes/{route['id']}/status"
    wdb.users.update_many({"_id": {"$in": ["usr-c1", "usr-c2"]}}, {"$set": {"status": "active"}})

    for bad in ({"status": "assigned"}, {"status": "planned"},
                {"status": "completed", "actual_distance_m": 10}):
        assert_error(client.patch(url, json=bad, headers=team["admin"]), 422, "VALIDATION")
    assert_error(client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-c3"},
                              headers=team["admin"]), 422, "VALIDATION")  # disabled
    assert_error(client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-admin"},
                              headers=team["admin"]), 422, "VALIDATION")  # not a collector
    assert_error(client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-c1"},
                              headers=team["c1"]), 403, "FORBIDDEN")
    assigned = client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-c1"},
                            headers=team["admin"])
    assert assigned.json()["assigned_worker_id"] == "usr-c1"
    moved = client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-c2"},
                         headers=team["admin"])  # c1 called in sick: give it to c2
    assert moved.json()["assigned_worker_name"] == "usr-c2"
    assert client.get("/api/v1/routes", headers=team["c1"]).json()["items"] == []

    assert_error(client.patch(url, json={"status": "cancelled"}, headers=team["c2"]),
                 403, "FORBIDDEN")
    assert client.patch(url, json={"status": "cancelled"},
                        headers=team["admin"]).json()["status"] == "cancelled"
    assert_error(client.patch(url, json={"status": "assigned", "assigned_worker_id": "usr-c1"},
                              headers=team["admin"]), 409, "CONFLICT")
    assert_error(client.patch("/api/v1/routes/rt-nope/status", json={"status": "cancelled"},
                              headers=team["admin"]), 404, "NOT_FOUND")
    # cancelled routes free their bins again
    assert [s["bin_id"] for r in generate(client, team["admin"]) for s in r["stops"]] == ["WB-A"]


def test_list_filters_paging_and_permissions(client, wdb, team):
    now = utcnow()
    for code, lng in (("WB-A", 105.85), ("WB-B", 105.83)):
        ready_bin(wdb, code, 90, now, lng=lng)
    generate(client, team["admin"])
    admin = team["admin"]
    page = client.get("/api/v1/routes?limit=1", headers=admin).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    rest = client.get(f"/api/v1/routes?limit=1&cursor={page['next_cursor']}",
                      headers=admin).json()
    assert rest["next_cursor"] is None and rest["items"][0]["id"] != page["items"][0]["id"]
    assert len(client.get("/api/v1/routes?assigned_worker_id=usr-c2",
                          headers=admin).json()["items"]) == 1
    assert client.get("/api/v1/routes?status=completed", headers=admin).json()["items"] == []
    assert_error(client.get("/api/v1/routes?service_date=21-11-2026", headers=admin),
                 422, "VALIDATION")

    assert_error(client.post("/api/v1/routes/generate", headers=team["c1"]), 403, "FORBIDDEN")
    assert_error(client.get("/api/v1/reports/routes?from=2026-11-01&to=2026-11-02",
                            headers=team["c1"]), 403, "FORBIDDEN")
    assert_error(client.get("/api/v1/reports/routes?from=2026-11-02&to=2026-11-01",
                            headers=admin), 422, "VALIDATION")
    assert_error(client.get("/api/v1/routes"), 401, "UNAUTHORIZED")


def test_road_distances_from_osrm(client, wdb, team, monkeypatch):
    """With OSRM up, routes and baseline use its road matrix (faked: 1.5x straight)."""
    def fake_matrix(points):
        return [[1.5 * rp.distance_m(p, q) for q in points] for p in points]
    monkeypatch.setattr(osrm_service, "distance_matrix", fake_matrix)
    now = utcnow()
    ready_bin(wdb, "WB-A", 90, now, lng=105.850, lat=21.010)
    ready_bin(wdb, "WB-B", 10, now, lng=105.830, lat=20.995)
    wdb.users.update_one({"_id": "usr-c2"}, {"$set": {"status": "disabled"}})
    [route] = generate(client, team["admin"])
    depot = {"lat": route["depot"]["lat"], "lng": route["depot"]["lng"]}
    stop = route["stops"][0]
    assert route["distance_method"] == "road"
    assert route["planned_distance_m"] == round(3 * rp.distance_m(depot, stop))
    assert wdb.routes.find_one()["baseline_method"].startswith("road ")


def test_route_geometry(client, wdb, team, monkeypatch):
    now = utcnow()
    ready_bin(wdb, "WB-A", 90, now, lng=105.850, lat=21.010)
    wdb.users.update_one({"_id": "usr-c2"}, {"$set": {"status": "disabled"}})
    [route] = generate(client, team["admin"])
    assert route["distance_method"] == "straight"  # OSRM off in tests
    url = f"/api/v1/routes/{route['id']}/geometry"
    depot = [route["depot"]["lng"], route["depot"]["lat"]]

    straight = client.get(url, headers=team["c1"]).json()
    assert straight["type"] == "LineString" and straight["source"] == "straight"
    assert straight["coordinates"] == [depot, [105.850, 21.010], depot]

    street = [depot, [105.846, 21.007], [105.850, 21.010], depot]
    monkeypatch.setattr(osrm_service, "road_path", lambda points: street)
    road = client.get(url, headers=team["admin"]).json()
    assert road["source"] == "road" and road["coordinates"] == street

    assert_error(client.get(url, headers=team["c2"]), 401, "UNAUTHORIZED")  # disabled
    wdb.users.update_one({"_id": "usr-c2"}, {"$set": {"status": "active"}})
    assert_error(client.get(url, headers=team["c2"]), 403, "FORBIDDEN")  # not their route
    assert_error(client.get("/api/v1/routes/rt-nope/geometry", headers=team["admin"]),
                 404, "NOT_FOUND")