from fastapi import Depends

from helpers import PASSWORD, assert_error
from smartwaste_backend.app import app
from smartwaste_backend.core.security import require_roles


@app.get("/api/v1/_test/admin-only")
def admin_only(user=Depends(require_roles("admin"))):
    return {"ok": True}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


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


def test_unknown_path_error_is_translated(client, db):
    response = client.get("/api/v1/does-not-exist")
    assert_error(response, 404, "NOT_FOUND")
    assert response.json()["message"] == "Không tìm thấy đường dẫn API"


# ------------------------------------------------------------ change-password

def change(client, token, current, new):
    return client.post("/api/v1/auth/change-password", headers=bearer(token),
                       json={"current_password": current, "new_password": new})


def test_change_password(client, db, make_user, login):
    email = make_user("usr-a", ["collector"])
    token = login(email).json()["access_token"]
    response = change(client, token, PASSWORD, "brand-new-pass-1")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert login(email).status_code == 401
    assert login(email, "brand-new-pass-1").status_code == 200
    assert db.audit_logs.count_documents({"action": "password_change", "actor_id": "usr-a"}) == 1


def test_change_password_rules(client, db, make_user, login):
    token = login(make_user("usr-a", ["admin"])).json()["access_token"]
    wrong = change(client, token, "not-my-password", "brand-new-pass-1")
    assert_error(wrong, 422, "VALIDATION")  # 422, never 401: the web would log the user out
    assert wrong.json()["details"] == {"field": "current_password"}
    assert_error(change(client, token, PASSWORD, "short"), 422, "VALIDATION")
    assert_error(change(client, token, PASSWORD, PASSWORD), 422, "VALIDATION")
    assert_error(client.post("/api/v1/auth/change-password",
                             json={"current_password": PASSWORD, "new_password": "x" * 10}),
                 401, "UNAUTHORIZED")
