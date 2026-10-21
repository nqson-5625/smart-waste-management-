from fastapi import Depends

from smartwaste_backend.app import app
from smartwaste_backend.auth import require_roles


@app.get("/api/v1/_test/admin-only")
def admin_only(user=Depends(require_roles("admin"))):
    return {"ok": True}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code
    assert body["request_id"].startswith("req-")
    assert set(body) == {"code", "message", "request_id", "details"}


def test_health(client, db):
    assert client.get("/api/v1/health").json() == {"status": "ok", "mongo": "ok"}


def test_login_then_me(client, make_user, login):
    email = make_user("usr-a", ["dispatcher"])
    response = login(email.upper())  # email is case-insensitive
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 8 * 3600
    assert body["user"] == {"id": "usr-a", "display_name": "usr-a", "roles": ["dispatcher"]}

    me = client.get("/api/v1/auth/me", headers=bearer(body["access_token"]))
    assert me.json() == body["user"]


def test_wrong_password_and_unknown_email(make_user, login):
    email = make_user("usr-a", ["admin"])
    assert_error(login(email, "wrong-password"), 401, "UNAUTHORIZED")
    assert_error(login("nobody@test.local"), 401, "UNAUTHORIZED")


def test_inactive_accounts_cannot_login(make_user, login):
    assert_error(login(make_user("usr-p", ["admin"], status="pending")), 401, "UNAUTHORIZED")
    assert_error(login(make_user("usr-d", ["admin"], status="disabled")), 401, "UNAUTHORIZED")


def test_disabling_account_revokes_existing_token(client, db, make_user, login):
    token = login(make_user("usr-a", ["admin"])).json()["access_token"]
    db.users.update_one({"_id": "usr-a"}, {"$set": {"status": "disabled"}})
    assert_error(client.get("/api/v1/auth/me", headers=bearer(token)), 401, "UNAUTHORIZED")


def test_missing_or_bad_token(client, db):
    assert_error(client.get("/api/v1/auth/me"), 401, "UNAUTHORIZED")
    assert_error(client.get("/api/v1/auth/me", headers=bearer("garbage")), 401, "UNAUTHORIZED")


def test_role_check(client, make_user, login):
    admin = login(make_user("usr-a", ["admin"])).json()["access_token"]
    collector = login(make_user("usr-c", ["collector"])).json()["access_token"]
    assert client.get("/api/v1/_test/admin-only", headers=bearer(admin)).status_code == 200
    assert_error(
        client.get("/api/v1/_test/admin-only", headers=bearer(collector)), 403, "FORBIDDEN"
    )


def test_validation_error_format(client, db):
    response = client.post("/api/v1/auth/login", json={"email": "x"})
    assert_error(response, 422, "VALIDATION")
    fields = {error["field"] for error in response.json()["details"]["errors"]}
    assert "body.password" in fields
