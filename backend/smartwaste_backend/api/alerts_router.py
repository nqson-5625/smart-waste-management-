"""HTTP endpoints for /alerts."""

from typing import Literal

from fastapi import APIRouter, Depends, Request

from ..core.common import Limit
from ..core.security import require_roles
from ..services import alerts_service


router = APIRouter(prefix="/alerts", tags=["alerts"])

AlertType = Literal["full", "sensor_fault", "device_stale", "gateway_offline"]
ScopeType = Literal["bin", "device", "gateway"]
any_user = require_roles("admin", "dispatcher", "collector")


@router.get("")
def list_alerts(
    status: str = "open",
    type: AlertType | None = None,
    scope_type: ScopeType | None = None,
    bin_id: str | None = None,
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(any_user),
):
    return alerts_service.list_alerts(status, type, scope_type, bin_id, limit, cursor)


@router.post("/{alert_id}/ack")
def acknowledge(alert_id: str, request: Request, user=Depends(any_user)):
    return alerts_service.acknowledge(alert_id, user, request.state.request_id)
