"""HTTP endpoints for /collection-events: workers confirm what they collected."""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..core.common import Limit, naive_utc
from ..core.security import require_roles
from ..schemas.collection_events_schemas import CollectionCreate, CollectionOut
from ..services import collection_events_service


router = APIRouter(prefix="/collection-events", tags=["collection-events"])


@router.post("", status_code=201, response_model=CollectionOut)
def create_event(
    body: CollectionCreate,
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    user=Depends(require_roles("collector", "admin")),
):
    """Resend with the same Idempotency-Key after a timeout: the stored event comes back (200)."""
    event, created = collection_events_service.create_event(body, idempotency_key, user,
                                                            request.state.request_id)
    if not created:
        response.status_code = 200
    return event


@router.get("")
def list_events(
    bin_id: str | None = None,
    worker_id: str | None = None,
    route_id: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(require_roles("admin", "collector")),
):
    return collection_events_service.list_events(
        user, bin_id, worker_id, route_id, from_ and naive_utc(from_), to and naive_utc(to),
        limit, cursor,
    )
