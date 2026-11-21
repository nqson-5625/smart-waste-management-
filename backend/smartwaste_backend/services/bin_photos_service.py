"""Photo of the place where a field bin stands, so collectors recognise it on site.

One photo per bin, kept in the GridFS bucket ``bin_photos`` with the bin id as filename.
GridFS keeps every upload as a revision of that filename; older revisions are deleted
after a new one is stored, so a failed upload never loses the current photo.
"""

from gridfs import GridFSBucket, NoFile

from ..core.db import get_database
from ..core.errors import ApiError
from . import audit_service


MAX_BYTES = 2 * 1024 * 1024
BUCKET = "bin_photos"


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


def _require_bin(database, bin_id):
    if not database.bins.find_one({"_id": bin_id}, {"_id": 1}):
        raise ApiError(404, "Không tìm thấy thùng", {"bin_id": bin_id})


def has_photo(database, bin_id):
    return database[f"{BUCKET}.files"].find_one({"filename": bin_id}, {"_id": 1}) is not None


def put_photo(bin_id, stream, user, request_id):
    """Store the photo and drop older ones; 413 above 2 MB, 422 if it is not an image."""
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ApiError(413, "Ảnh vượt quá 2 MB", {"max_bytes": MAX_BYTES})
    media_type = image_type(data)
    if not media_type:
        raise ApiError(422, "Chỉ nhận ảnh JPEG, PNG hoặc WebP", {"field": "photo"})

    database = get_database()
    _require_bin(database, bin_id)
    bucket = _bucket(database)
    new_id = bucket.upload_from_stream(bin_id, data, metadata={
        "content_type": media_type, "uploaded_by": user["_id"]})
    for old in bucket.find({"filename": bin_id, "_id": {"$ne": new_id}}):
        bucket.delete(old._id)

    audit_service.record(database, actor_id=user["_id"], action="bin_photo_update",
                         entity_type="bin", entity_id=bin_id,
                         summary=f"Cập nhật ảnh vị trí thùng {bin_id} ({len(data)} byte)",
                         request_id=request_id)
    return {"bin_id": bin_id, "content_type": media_type, "size_bytes": len(data)}


def get_photo(bin_id):
    """(bytes, media type) of the newest photo, or 404."""
    try:
        with _bucket(get_database()).open_download_stream_by_name(bin_id) as photo:
            return photo.read(), photo.metadata["content_type"]
    except NoFile:
        raise ApiError(404, "Thùng chưa có ảnh", {"bin_id": bin_id})


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
