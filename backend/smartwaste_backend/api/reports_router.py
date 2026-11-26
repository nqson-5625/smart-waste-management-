"""HTTP endpoints for /reports."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from ..core.security import require_roles
from ..services import routes_service


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/routes")
def route_report(from_: date = Query(alias="from"), to: date = Query(),
                 user=Depends(require_roles("admin"))):
    """Km and trips of completed routes per day against the fixed schedule (Vietnam dates)."""
    return routes_service.route_report(from_.isoformat(), to.isoformat())
