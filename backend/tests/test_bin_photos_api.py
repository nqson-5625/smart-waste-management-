"""PUT, GET and DELETE /bins/{id}/photo."""

from helpers import BIN, assert_error, insert_bin


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG = b"\xff\xd8\xff\xe0" + b"\x01" * 300_000  # spans more than one GridFS chunk
URL = f"/api/v1/bins/{BIN}/photo"


def upload(client, headers, data, name="photo.jpg", url=URL):
    return client.put(url, headers=headers, files={"photo": (name, data, "image/jpeg")})


def test_upload_replace_read_and_delete(client, wdb, auth_as):
    insert_bin(wdb, BIN)
    admin, collector = auth_as("admin"), auth_as("collector")
    assert client.get(f"/api/v1/bins/{BIN}", headers=admin).json()["has_photo"] is False

    first = upload(client, admin, PNG, name="lies.jpg")  # type comes from the bytes, not the name
    assert first.status_code == 200, first.text
    assert first.json() == {"bin_id": BIN, "content_type": "image/png", "size_bytes": len(PNG)}

    assert upload(client, admin, JPEG).status_code == 200
    assert wdb["bin_photos.files"].count_documents({"filename": BIN}) == 1  # old one dropped
    shown = client.get(URL, headers=collector)  # collectors use it to find the bin
    assert shown.status_code == 200
    assert shown.content == JPEG and shown.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/v1/bins/{BIN}", headers=collector).json()["has_photo"] is True

    assert client.delete(URL, headers=admin).status_code == 204
    assert_error(client.get(URL, headers=admin), 404, "NOT_FOUND")
    assert wdb["bin_photos.chunks"].count_documents({}) == 0
    actions = [a["action"] for a in wdb.audit_logs.find({"entity_id": BIN})]
    assert sorted(actions) == ["bin_photo_delete", "bin_photo_update", "bin_photo_update"]


def test_photo_rules(client, wdb, auth_as):
    insert_bin(wdb, BIN)
    admin = auth_as("admin")
    assert_error(upload(client, admin, b"GIF89a not allowed"), 422, "VALIDATION")
    assert_error(upload(client, admin, b""), 422, "VALIDATION")
    assert_error(upload(client, admin, JPEG + b"\x00" * (2 * 1024 * 1024)), 413, "TOO_LARGE")
    assert_error(client.put(URL, headers=admin), 422, "VALIDATION")  # no file field
    assert_error(upload(client, admin, PNG, url="/api/v1/bins/WB-NOPE/photo"), 404, "NOT_FOUND")
    assert_error(client.delete(URL, headers=admin), 404, "NOT_FOUND")

    collector = auth_as("collector")
    assert_error(upload(client, collector, PNG), 403, "FORBIDDEN")
    assert_error(client.delete(URL, headers=collector), 403, "FORBIDDEN")
    assert_error(client.get(URL), 401, "UNAUTHORIZED")
    assert wdb["bin_photos.files"].count_documents({}) == 0
