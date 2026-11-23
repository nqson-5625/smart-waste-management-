"""HTTP endpoints for /routes: generate now, list, change status."""

from fastapi import APIRouter, Depends, Query, Request

from ..core.common import Limit
from ..core.security import require_roles
from ..schemas.routes_schemas import DATE_PATTERN, RouteStatus, RouteStatusChange
from ..services import routes_service


router = APIRouter(prefix="/routes", tags=["routes"])
admin_only = require_roles("admin")
any_user = require_roles("admin", "collector")


@router.post("/generate")
def generate_routes(request: Request, user=Depends(admin_only)):
    """Run the shift algorithm now for bins not yet in a route ("Tạo tuyến ngay")."""
    return routes_service.generate_now(user, request.state.request_id)


@router.get("")
def list_routes(
    service_date: str | None = Query(None, pattern=DATE_PATTERN),
    status: RouteStatus | None = None,
    assigned_worker_id: str | None = None,
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(any_user),
):
    """Newest first; a collector only gets the routes assigned to them."""
    return routes_service.list_routes(user, service_date, status, assigned_worker_id, limit,
                                      cursor)


@router.patch("/{route_id}/status")
def change_status(route_id: str, body: RouteStatusChange, request: Request,
                  user=Depends(any_user)):
    return routes_service.change_status(route_id, body, user, request.state.request_id)
