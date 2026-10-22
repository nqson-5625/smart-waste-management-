"""Alert queries and acknowledgement rules."""

from pymongo import ReturnDocument

from ..core.common import decode_cursor, encode_cursor, from_ms, iso, to_ms, utcnow
from ..core.db import get_database
from ..core.errors import ApiError


STATUSES = {"open", "acknowledged", "resolved"}


def alert_view(alert):
    return {
        "id": alert["_id"], "type": alert["type"], "status": alert["status"],
        "severity": alert["severity"], "scope_type": alert["scope_type"],
        "scope_id": alert["scope_id"], "bin_id": alert["bin_id"],
        "opened_at": iso(alert["opened_at"]), "acknowledged_at": iso(alert["acknowledged_at"]),
        "acknowledged_by": alert["acknowledged_by"], "resolved_at": iso(alert["resolved_at"]),
        "resolve_reason": alert["resolve_reason"],
    }


def active_for_bin(bin_id):
    """Alerts still in force for a bin (open or acknowledged), newest first."""
    alerts = get_database().alerts.find({"bin_id": bin_id, "active": True}).sort("opened_at", -1)
    return [alert_view(alert) for alert in alerts]


def list_alerts(status, alert_type, scope_type, bin_id, limit, cursor):
    """Page alerts newest first; ``status`` is a comma-separated list."""
    statuses = {part.strip() for part in status.split(",") if part.strip()}
    if not statuses or statuses - STATUSES:
        raise ApiError(422, "status chỉ nhận open, acknowledged, resolved", {"field": "status"})

    query = {"status": {"$in": sorted(statuses)}}
    for field, value in (("type", alert_type), ("scope_type", scope_type), ("bin_id", bin_id)):
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


def acknowledge(alert_id, user, request_id):
    """Mark an open alert as taken in hand. Idempotent; resolved alerts cannot be acked."""
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
            "request_id": request_id,
        })
        return alert_view(alert)

    existing = database.alerts.find_one({"_id": alert_id})
    if not existing:
        raise ApiError(404, "Không tìm thấy cảnh báo", {"alert_id": alert_id})
    if existing["status"] == "resolved":
        raise ApiError(409, "Cảnh báo đã được đóng", {"alert_id": alert_id})
    return alert_view(existing)
