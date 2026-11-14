"""HTTP endpoints for /bins."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from ..core.common import Limit, naive_utc
from ..core.security import current_user, require_roles
from ..schemas.bins_schemas import BinCreate, BinOut, BinStatus, BinUpdate, WasteType
from ..services import bins_service


router = APIRouter(prefix="/bins", tags=["bins"])
admin_only = require_roles("admin")


@router.post("", status_code=201, response_model=BinOut)
def create_bin(body: BinCreate, request: Request, user=Depends(admin_only)):
    return bins_service.create_bin(body, user, request.state.request_id)


@router.patch("/{bin_id}", response_model=BinOut)
def update_bin(bin_id: str, body: BinUpdate, request: Request, user=Depends(admin_only)):
    """Partial update. Deleting a bin is done by setting status to retired."""
    return bins_service.update_bin(bin_id, body, user, request.state.request_id)


@router.get("")
def list_bins(
    ward_code: str | None = None,
    waste_type: WasteType | None = None,
    status: BinStatus | None = None,
    full: bool | None = None,
    fresh: bool | None = None,
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(current_user),
):
    return bins_service.list_bins(ward_code, waste_type, status, full, fresh, limit, cursor)


@router.get("/{bin_id}")
def get_bin(bin_id: str, user=Depends(current_user)):
    return bins_service.get_bin(bin_id)


@router.get("/{bin_id}/telemetry")
def bin_telemetry(
    bin_id: str,
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(require_roles("admin", "dispatcher")),
):
    return bins_service.bin_telemetry(bin_id, naive_utc(from_), naive_utc(to), limit, cursor)
