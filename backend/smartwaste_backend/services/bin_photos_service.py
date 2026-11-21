"""Photo of the place where a field bin stands, so collectors recognise it on site.

One photo per bin, kept in the GridFS bucket ``bin_photos`` with the bin id as filename.
GridFS keeps every upload as a revision of that filename; older revisions are deleted
after a new one is stored, so a failed upload never loses the current photo.

Bin responses carry ``photo_url``: a signed link that works in ``<img src>`` without a
bearer token. It names the stored file, so replacing the photo changes the link and
browsers never show a cached old photo.
"""

import time

from bson import ObjectId
from bson.errors import InvalidId
from gridfs import GridFSBucket, NoFile

from ..core.db import get_database
from ..core.errors import ApiError
from ..core.security import sign, signature_ok
from . import audit_service


MAX_BYTES = 2 * 1024 * 1024
BUCKET = "bin_photos"
LINK_STEP_S = 6 * 3600  # links last 6 to 12 hours and stay identical within a step

# Newest photo id per bin, joined onto bin queries; served by GridFS's filename index.
JOIN_PHOTO = {
    "$lookup": {
        "from": f"{BUCKET}.files",
        "localField": "_id",
        "foreignField": "filename",
        "pipeline": [{"$sort": {"uploadDate": -1}}, {"$limit": 1}, {"$project": {"_id": 1}}],
        "as": "photo",
    }
}


def _bucket(database):
    return GridFSBucket(database, bucket_name=BUCKET)


def image_type(data):
    """Media type read from the file's first bytes; the client's name and type are not trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def photo_url(bin_id, file_id, now_s=None):
    """Signed link to one stored photo, or None when the bin has none."""
    if file_id is None:
        return None
    exp = ((int(now_s or time.time()) // LINK_STEP_S) + 2) * LINK_STEP_S
    return (f"/api/v1/bins/{bin_id}/photo?v={file_id}&exp={exp}"
            f"&sig={sign(f'{bin_id}:{file_id}:{exp}')}")


def put_photo(bin_id, stream, user, request_id):
    """Store the photo and drop older ones; 413 above 2 MB, 422 if it is not an image."""
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ApiError(413, "Ảnh vượt quá 2 MB", {"max_bytes": MAX_BYTES})
    media_type = image_type(data)
    if not media_type:
        raise ApiError(422, "Chỉ nhận ảnh JPEG, PNG hoặc WebP", {"field": "photo"})

    database = get_database()
    if not database.bins.find_one({"_id": bin_id}, {"_id": 1}):
        raise ApiError(404, "Không tìm thấy thùng", {"bin_id": bin_id})
    bucket = _bucket(database)
    new_id = bucket.upload_from_stream(bin_id, data, metadata={
        "content_type": media_type, "uploaded_by": user["_id"]})
    for old in bucket.find({"filename": bin_id, "_id": {"$ne": new_id}}):
        bucket.delete(old._id)

    audit_service.record(database, actor_id=user["_id"], action="bin_photo_update",
                         entity_type="bin", entity_id=bin_id,
                         summary=f"Cập nhật ảnh vị trí thùng {bin_id} ({len(data)} byte)",
                         request_id=request_id)
    return {"bin_id": bin_id, "content_type": media_type, "size_bytes": len(data),
            "photo_url": photo_url(bin_id, new_id)}


def get_photo(bin_id, file_id, exp, sig):
    """(bytes, media type) for a signed link; 403 if forged or expired, 404 if replaced."""
    if exp < time.time() or not signature_ok(f"{bin_id}:{file_id}:{exp}", sig):
        raise ApiError(403, "Link ảnh không hợp lệ hoặc đã hết hạn")
    try:
        with _bucket(get_database()).open_download_stream(ObjectId(file_id)) as photo:
            return photo.read(), photo.metadata["content_type"]
    except (NoFile, InvalidId):
        raise ApiError(404, "Ảnh đã bị thay hoặc xóa", {"bin_id": bin_id})


def delete_photo(bin_id, user, request_id):
    database = get_database()
    bucket = _bucket(database)
    files = list(bucket.find({"filename": bin_id}))
    if not files:
        raise ApiError(404, "Thùng chưa có ảnh", {"bin_id": bin_id})
    for photo in files:
        bucket.delete(photo._id)
    audit_service.record(database, actor_id=user["_id"], action="bin_photo_delete",
                         entity_type="bin", entity_id=bin_id,
                         summary=f"Xóa ảnh vị trí thùng {bin_id}", request_id=request_id)
