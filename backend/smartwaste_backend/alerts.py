"""Alert list and acknowledgement."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pymongo import ReturnDocument

from .auth import require_roles
from .common import Limit, decode_cursor, encode_cursor, from_ms, iso, to_ms, utcnow
from .db import get_database
from .errors import ApiError


router = APIRouter(prefix="/alerts", tags=["alerts"])

STATUSES = {"open", "acknowledged", "resolved"}
AlertType = Literal["full", "sensor_fault", "device_stale", "gateway_offline"]
ScopeType = Literal["bin", "device", "gateway"]
any_user = require_roles("admin", "dispatcher", "collector")


def alert_view(alert):
    return {
        "id": alert["_id"], "type": alert["type"], "status": alert["status"],
        "severity": alert["severity"], "scope_type": alert["scope_type"],
        "scope_id": alert["scope_id"], "bin_id": alert["bin_id"],
        "opened_at": iso(alert["opened_at"]), "acknowledged_at": iso(alert["acknowledged_at"]),
        "acknowledged_by": alert["acknowledged_by"], "resolved_at": iso(alert["resolved_at"]),
        "resolve_reason": alert["resolve_reason"],
    }


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
    statuses = {part.strip() for part in status.split(",") if part.strip()}
    if not statuses or statuses - STATUSES:
        raise ApiError(422, "status chỉ nhận open, acknowledged, resolved", {"field": "status"})

    query = {"status": {"$in": sorted(statuses)}}
    for field, value in (("type", type), ("scope_type", scope_type), ("bin_id", bin_id)):
        if value is not None:
            query[field] = value
    if cursor:
        ms, alert_id = decode_cursor(cursor, 2)
        opened_at = from_ms(ms)
        query["$or"] = [{"opened_at": {"$lt": opened_at}},
                        {"opened_at": opened_at, "_id": {"$gt": alert_id}}]

    alerts = list(get_database().alerts.find(query)
                  .sort([("opened_at", -1), ("_id", 1)]).limit(limit + 1))
    has_more = len(alerts) > limit
    alerts = alerts[:limit]
    return {
        "items": [alert_view(alert) for alert in alerts],
        "next_cursor": (encode_cursor([to_ms(alerts[-1]["opened_at"]), alerts[-1]["_id"]])
                        if has_more else None),
    }


@router.post("/{alert_id}/ack")
def acknowledge(alert_id: str, request: Request, user=Depends(any_user)):
    database = get_database()
    now = utcnow()
    alert = database.alerts.find_one_and_update(
        {"_id": alert_id, "status": "open"},
        {"$set": {"status": "acknowledged", "acknowledged_at": now,
                  "acknowledged_by": user["_id"], "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if alert:
        database.audit_logs.insert_one({
            "_id": f"alert_ack:{alert_id}", "event_key": f"alert_ack:{alert_id}",
            "actor_id": user["_id"], "action": "alert_ack", "entity_type": "alert",
            "entity_id": alert_id, "source_message_id": None, "occurred_at": now,
            "summary": f"{user['display_name']} xác nhận đã nhận cảnh báo {alert['type']}",
            "request_id": request.state.request_id,
        })
        return alert_view(alert)

    existing = database.alerts.find_one({"_id": alert_id})
    if not existing:
        raise ApiError(404, "Không tìm thấy cảnh báo", {"alert_id": alert_id})
    if existing["status"] == "resolved":
        raise ApiError(409, "Cảnh báo đã được đóng", {"alert_id": alert_id})
    return alert_view(existing)  # already acknowledged: idempotent
