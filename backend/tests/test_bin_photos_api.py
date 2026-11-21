"""PUT and DELETE /bins/{id}/photo, and the signed photo_url in bin responses."""

import time

from helpers import BIN, assert_error, insert_bin
from smartwaste_backend.core.security import sign


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG = b"\xff\xd8\xff\xe0" + b"\x01" * 300_000  # spans more than one GridFS chunk
URL = f"/api/v1/bins/{BIN}/photo"


def upload(client, headers, data, name="photo.jpg", url=URL):
    return client.put(url, headers=headers, files={"photo": (name, data, "image/jpeg")})


def photo_url(client, headers):
    return client.get(f"/api/v1/bins/{BIN}", headers=headers).json()["photo_url"]


def test_upload_replace_show_and_delete(client, wdb, auth_as):
    insert_bin(wdb, BIN)
    admin, collector = auth_as("admin"), auth_as("collector")
    assert photo_url(client, admin) is None

    first = upload(client, admin, PNG, name="lies.jpg")  # type comes from the bytes, not the name
    assert first.status_code == 200, first.text
    assert first.json()["content_type"] == "image/png"
    old_link = first.json()["photo_url"]
    assert photo_url(client, collector) == old_link

    assert upload(client, admin, JPEG).status_code == 200
    assert wdb["bin_photos.files"].count_documents({"filename": BIN}) == 1  # old one dropped
    link = photo_url(client, collector)
    assert link != old_link  # a new photo gets a new link, so caches never show the old one
    shown = client.get(link)  # no bearer token: <img src> cannot send one
    assert shown.status_code == 200
    assert shown.content == JPEG and shown.headers["content-type"] == "image/jpeg"
    assert_error(client.get(old_link), 404, "NOT_FOUND")

    listed = client.get("/api/v1/bins", headers=collector).json()["items"]
    assert [b["photo_url"] for b in listed] == [link]  # the map popup gets it too

    assert client.delete(URL, headers=admin).status_code == 204
    assert photo_url(client, admin) is None
    assert_error(client.get(link), 404, "NOT_FOUND")
    assert wdb["bin_photos.chunks"].count_documents({}) == 0
    actions = [a["action"] for a in wdb.audit_logs.find({"entity_id": BIN})]
    assert sorted(actions) == ["bin_photo_delete", "bin_photo_update", "bin_photo_update"]


def test_link_cannot_be_forged_or_reused(client, wdb, auth_as):
    insert_bin(wdb, BIN)
    insert_bin(wdb, "WB-OTHER")
    link = upload(client, auth_as("admin"), PNG).json()["photo_url"]
    file_id = wdb["bin_photos.files"].find_one()["_id"]

    assert_error(client.get(link[:-1] + ("0" if link[-1] != "0" else "1")), 403, "FORBIDDEN")
    assert_error(client.get(link.replace(BIN, "WB-OTHER")), 403, "FORBIDDEN")
    past = int(time.time()) - 1
    expired = f"{URL}?v={file_id}&exp={past}&sig={sign(f'{BIN}:{file_id}:{past}')}"
    assert_error(client.get(expired), 403, "FORBIDDEN")
    non_ascii = f"{URL}?v={file_id}&exp=9999999999&sig=ừ"
    assert_error(client.get(non_ascii), 403, "FORBIDDEN")
    assert_error(client.get(URL), 422, "VALIDATION")


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
    assert_error(upload(client, {}, PNG), 401, "UNAUTHORIZED")
    assert wdb["bin_photos.files"].count_documents({}) == 0
