"""POST /bins and PATCH /bins/{id}."""

import pytest


NEW_BIN = {
    "code": "WB-201", "name": "Cổng Parabol", "address": "Số 1 Đại Cồ Việt", "ward_code": "BK",
    "waste_type": "recyclable", "capacity_l": 240,
    "location": {"type": "Point", "coordinates": [105.8431, 21.0047]},
}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["code"] == code


@pytest.fixture
def admin(wdb, auth_as):
    return auth_as("admin")


def test_create_bin_as_admin(client, admin, wdb):
    response = client.post("/api/v1/bins", json=NEW_BIN, headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == body["code"] == "WB-201"
    assert (body["lat"], body["lng"]) == (21.0047, 105.8431)
    assert body["status"] == "active" and body["state"] is None
    stored = wdb.bins.find_one({"_id": "WB-201"})
    assert stored["environment"] == "field" and stored["assignment_version"] == 0
    assert wdb.audit_logs.count_documents({"action": "bin_create", "actor_id": "usr-admin"}) == 1

    listed = client.get("/api/v1/bins?status=active", headers=admin).json()["items"]
    assert [b["id"] for b in listed] == ["WB-201"]


def test_create_bin_accepts_lat_lng(client, admin):
    body = {**NEW_BIN, "location": None, "lat": 21.0, "lng": 105.8}
    response = client.post("/api/v1/bins", json=body, headers=admin)
    assert response.status_code == 201
    assert response.json()["location"]["coordinates"] == [105.8, 21.0]


def test_create_bin_rules(client, admin, auth_as):
    assert client.post("/api/v1/bins", json=NEW_BIN, headers=admin).status_code == 201
    assert_error(client.post("/api/v1/bins", json=NEW_BIN, headers=admin), 409, "CONFLICT")
    assert_error(client.post("/api/v1/bins", json={**NEW_BIN, "code": "WB-9"},
                             headers=auth_as("dispatcher")), 403, "FORBIDDEN")
    for bad in ({"waste_type": "plastic"}, {"capacity_l": 0}, {"code": "WB 9"},
                {"location": {"type": "Point", "coordinates": [200, 21]}},
                {"location": None, "lat": 21.0}):
        assert_error(client.post("/api/v1/bins", json={**NEW_BIN, "code": "WB-9", **bad},
                                 headers=admin), 422, "VALIDATION")


def test_update_bin_fields_and_retire(client, admin, wdb):
    client.post("/api/v1/bins", json=NEW_BIN, headers=admin)
    response = client.patch("/api/v1/bins/WB-201", headers=admin, json={
        "name": "Cổng Parabol mới", "capacity_l": None,
        "location": {"type": "Point", "coordinates": [105.85, 21.01]},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Cổng Parabol mới" and body["capacity_l"] is None
    assert (body["lat"], body["lng"]) == (21.01, 105.85)
    assert body["address"] == NEW_BIN["address"]  # untouched fields stay

    retired = client.patch("/api/v1/bins/WB-201", json={"status": "retired"}, headers=admin)
    assert retired.json()["status"] == "retired"
    assert client.get("/api/v1/bins?status=active", headers=admin).json()["items"] == []
    assert wdb.audit_logs.count_documents({"action": "bin_update"}) == 2


def test_update_bin_rules(client, admin, auth_as):
    client.post("/api/v1/bins", json=NEW_BIN, headers=admin)
    assert_error(client.patch("/api/v1/bins/WB-NOPE", json={"name": "x"}, headers=admin),
                 404, "NOT_FOUND")
    assert_error(client.patch("/api/v1/bins/WB-201", json={}, headers=admin), 422, "VALIDATION")
    assert_error(client.patch("/api/v1/bins/WB-201", json={"name": None}, headers=admin),
                 422, "VALIDATION")
    assert_error(client.patch("/api/v1/bins/WB-201", json={"status": "gone"}, headers=admin),
                 422, "VALIDATION")
    assert_error(client.patch("/api/v1/bins/WB-201", json={"name": "x"},
                              headers=auth_as("collector")), 403, "FORBIDDEN")
    # code and environment are not editable: unknown fields are ignored
    unchanged = client.patch("/api/v1/bins/WB-201", json={"code": "HACK", "name": "y"},
                             headers=admin).json()
    assert unchanged["code"] == "WB-201"
