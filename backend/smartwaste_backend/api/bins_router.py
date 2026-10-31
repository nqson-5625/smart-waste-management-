"""HTTP endpoints for /bins."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..core.common import Limit, naive_utc
from ..core.security import current_user, require_roles
from ..services import bins_service


router = APIRouter(prefix="/bins", tags=["bins"])

WasteType = Literal["general", "organic", "recyclable", "hazardous", "other"]
BinStatus = Literal["active", "maintenance", "retired"]


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
