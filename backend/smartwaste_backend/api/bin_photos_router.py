"""HTTP endpoints for /bins/{id}/photo: the photo of where a bin stands."""

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from ..core.security import require_roles
from ..services import bin_photos_service


router = APIRouter(prefix="/bins", tags=["bins"])
admin_only = require_roles("admin")


@router.put("/{bin_id}/photo")
def put_photo(bin_id: str, request: Request, photo: UploadFile = File(),
              user=Depends(admin_only)):
    """Upload as multipart field ``photo`` (JPEG/PNG/WebP, max 2 MB); replaces the old one."""
    return bin_photos_service.put_photo(bin_id, photo.file, user, request.state.request_id)


@router.get("/{bin_id}/photo", response_class=Response)
def get_photo(bin_id: str, user=Depends(require_roles("admin", "collector"))):
    data, media_type = bin_photos_service.get_photo(bin_id)
    return Response(data, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{bin_id}/photo", status_code=204)
def delete_photo(bin_id: str, request: Request, user=Depends(admin_only)):
    bin_photos_service.delete_photo(bin_id, user, request.state.request_id)
