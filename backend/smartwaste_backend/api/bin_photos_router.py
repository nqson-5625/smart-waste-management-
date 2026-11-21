"""HTTP endpoints for /bins/{id}/photo: the photo of where a bin stands."""

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from ..core.security import require_roles
from ..services import bin_photos_service


router = APIRouter(prefix="/bins", tags=["bins"])
admin_only = require_roles("admin")


@router.put("/{bin_id}/photo")
def put_photo(bin_id: str, request: Request, photo: UploadFile = File(),
              user=Depends(admin_only)):
    """Upload as multipart field ``photo`` (JPEG/PNG/WebP, max 2 MB); replaces the old one.
    Responds with the new ``photo_url``."""
    return bin_photos_service.put_photo(bin_id, photo.file, user, request.state.request_id)


@router.get("/{bin_id}/photo", response_class=Response)
def get_photo(bin_id: str, v: str, exp: int, sig: str):
    """Open the ``photo_url`` of a bin response; the signature replaces the bearer token
    so the link works in ``<img src>``. A link always shows the same file, so it is cached."""
    data, media_type = bin_photos_service.get_photo(bin_id, v, exp, sig)
    return Response(data, media_type=media_type, headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=21600"})


@router.delete("/{bin_id}/photo", status_code=204)
def delete_photo(bin_id: str, request: Request, user=Depends(admin_only)):
    bin_photos_service.delete_photo(bin_id, user, request.state.request_id)
