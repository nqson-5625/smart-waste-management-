"""HTTP endpoints for /stats."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..core.common import naive_utc
from ..core.security import require_roles
from ..schemas.stats_schemas import WasteStatsOut
from ..services import stats_service


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/waste-by-type", response_model=WasteStatsOut)
def waste_by_type(
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    user=Depends(require_roles("admin", "dispatcher")),
):
    return stats_service.waste_by_type(naive_utc(from_), naive_utc(to))
