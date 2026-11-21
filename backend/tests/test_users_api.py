"""POST/PATCH/GET /users."""

import pytest

from helpers import assert_error


NEW_USER = {"email": "Thu.Gom@Smartwaste.local", "display_name": "Nguyễn Văn Gom",
            "password": "gom-password-1", "roles": ["collector"], "phone": "0901234567"}


@pytest.fixture
def admin(auth_as):
    return auth_as("admin")


def create(client, admin, **extra):
    return client.post("/api/v1/users", json={**NEW_USER, **extra}, headers=admin)


def test_admin_creates_collector_who_can_login(client, db, admin, login):
    response = create(client, admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "thu.gom@smartwaste.local"  # stored lower-case
    assert body["roles"] == ["collector"] and body["status"] == "active"
    assert body["last_login_at"] is None and "password_hash" not in body
    assert login("thu.gom@smartwaste.local", "gom-password-1").status_code == 200
    assert db.audit_logs.count_documents({"action": "user_create", "entity_id": body["id"]}) == 1


def test_create_user_rules(client, admin, auth_as):
    assert create(client, admin).status_code == 201
    assert_error(create(client, admin, email="THU.GOM@smartwaste.local"), 409, "CONFLICT")
    for bad in ({"roles": ["boss"]}, {"roles": []}, {"roles": ["collector", "collector"]},
                {"roles": ["dispatcher"]},  # role dropped by the team, admin does it now
                {"password": "short"}, {"email": "not-an-email"}, {"display_name": ""}):
        assert_error(create(client, admin, **{"email": "x@y.vn", **bad}), 422, "VALIDATION")
    assert_error(create(client, auth_as("collector"), email="x@y.vn"), 403, "FORBIDDEN")


def test_update_user_and_reset_password(client, db, admin, login):
    user_id = create(client, admin).json()["id"]
    response = client.patch(f"/api/v1/users/{user_id}", headers=admin, json={
        "display_name": "Trần Văn Gom", "roles": ["collector", "admin"], "phone": None,
        "password": "reset-by-admin-1",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "Trần Văn Gom" and body["phone"] is None
    assert sorted(body["roles"]) == ["admin", "collector"]
    assert login("thu.gom@smartwaste.local", "gom-password-1").status_code == 401
    assert login("thu.gom@smartwaste.local", "reset-by-admin-1").status_code == 200
    audit = db.audit_logs.find_one({"action": "user_update"})
    assert "password" in audit["summary"] and "reset-by-admin-1" not in audit["summary"]


def test_disabling_user_revokes_token_at_once(client, admin, login):
    user_id = create(client, admin).json()["id"]
    token = login("thu.gom@smartwaste.local", "gom-password-1").json()["access_token"]
    mine = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=mine).status_code == 200
    client.patch(f"/api/v1/users/{user_id}", json={"status": "disabled"}, headers=admin)
    assert_error(client.get("/api/v1/auth/me", headers=mine), 401, "UNAUTHORIZED")
    assert login("thu.gom@smartwaste.local", "gom-password-1").status_code == 401


def test_update_user_rules(client, db, admin):
    user_id = create(client, admin).json()["id"]
    assert_error(client.patch("/api/v1/users/usr-admin", json={"status": "disabled"},
                              headers=admin), 409, "CONFLICT")
    assert_error(client.patch("/api/v1/users/usr-admin", json={"roles": ["collector"]},
                              headers=admin), 409, "CONFLICT")
    assert_error(client.patch("/api/v1/users/usr-nope", json={"display_name": "x"},
                              headers=admin), 404, "NOT_FOUND")
    assert_error(client.patch(f"/api/v1/users/{user_id}", json={}, headers=admin),
                 422, "VALIDATION")
    assert_error(client.patch(f"/api/v1/users/{user_id}", json={"display_name": None},
                              headers=admin), 422, "VALIDATION")
    assert_error(client.patch(f"/api/v1/users/{user_id}", json={"status": "pending"},
                              headers=admin), 422, "VALIDATION")

    # a pending account without a password can only be activated together with one
    db.users.update_one({"_id": user_id}, {"$set": {"status": "pending", "password_hash": None}})
    no_password = client.patch(f"/api/v1/users/{user_id}", json={"status": "active"},
                               headers=admin)
    assert_error(no_password, 422, "VALIDATION")
    assert no_password.json()["details"] == {"field": "password"}
    assert client.patch(f"/api/v1/users/{user_id}", headers=admin, json={
        "status": "active", "password": "first-password-1"}).status_code == 200


def test_list_users_by_role(client, admin, auth_as, make_user):
    make_user("usr-c1", ["collector"])
    make_user("usr-c2", ["collector"], status="disabled")
    make_user("usr-x1", ["admin"])

    everyone = client.get("/api/v1/users", headers=admin).json()
    assert [u["id"] for u in everyone["items"]] == ["usr-admin", "usr-c1", "usr-c2", "usr-x1"]
    assert everyone["items"][1]["email"] == "usr-c1@test.local"
    collectors = client.get("/api/v1/users?role=collector&status=active", headers=admin).json()
    assert [u["id"] for u in collectors["items"]] == ["usr-c1"]

    page1 = client.get("/api/v1/users?limit=2", headers=admin).json()
    page2 = client.get(f"/api/v1/users?limit=2&cursor={page1['next_cursor']}",
                       headers=admin).json()
    assert [u["id"] for u in page1["items"] + page2["items"]] == [
        "usr-admin", "usr-c1", "usr-c2", "usr-x1"]


def test_only_admin_lists_users(client, auth_as):
    assert_error(client.get("/api/v1/users", headers=auth_as("collector")), 403, "FORBIDDEN")
    assert_error(client.get("/api/v1/users?role=dispatcher", headers=auth_as("admin")),
                 422, "VALIDATION")
