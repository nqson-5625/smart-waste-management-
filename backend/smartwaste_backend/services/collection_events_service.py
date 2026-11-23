"""Collections confirmed by workers, optionally as a stop of their route (docs/05 5.2).

A collection never touches bin_state: the bin only shows empty once its sensor says so.
"""

import hashlib
import json
import uuid

from pymongo.errors import DuplicateKeyError

from ..core.common import (
    CLOCK_SKEW, decode_cursor, encode_cursor, from_ms, iso, naive_utc, to_ms, utcnow,
)
from ..core.db import get_database, run_transaction
from ..core.errors import ApiError
from . import audit_service, users_service


def event_view(event, worker_name):
    return {
        "id": event["_id"], "bin_id": event["bin_id"], "worker_id": event["worker_id"],
        "worker_name": worker_name, "route_id": event["route_id"],
        "stop_order": event["stop_order"], "completed_at": iso(event["completed_at"]),
        "recorded_at": iso(event["recorded_at"]), "waste_type": event["waste_type_snapshot"],
        "measured_weight_kg": event["measured_weight_kg"], "weight_source": event["weight_source"],
        "fill_before_pct": event["fill_before_pct"], "fill_after_pct": event["fill_after_pct"],
        "note": event["note"],
    }


def request_hash(body, worker_id):
    """Fingerprint of what the client asked for, so a reused Idempotency-Key is detected."""
    payload = body.model_dump(mode="json")
    payload["completed_at"] = to_ms(body.completed_at)  # same instant, any timezone notation
    payload["worker_id"] = worker_id
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _replay(database, event, digest):
    """Same key again: the stored result if the request matches, otherwise 409."""
    if event["request_hash"] != digest:
        raise ApiError(409, "Idempotency-Key đã được dùng cho một yêu cầu khác",
                       {"event_id": event["_id"]})
    names = users_service.display_names(database, [event["worker_id"]])
    return event_view(event, names.get(event["worker_id"]))


def _collect_stop(database, session, body, user, completed_at, event_id, now):
    """Mark the route stop collected; the route must be this worker's and in progress."""
    route = database.routes.find_one({"_id": body.route_id}, session=session)
    if not route:
        raise ApiError(404, "Không tìm thấy tuyến", {"route_id": body.route_id})
    if route["assigned_worker_id"] != user["_id"]:
        raise ApiError(403, "Tuyến này không được giao cho bạn", {"route_id": body.route_id})
    if route["status"] != "in_progress":
        raise ApiError(409, "Tuyến chưa bắt đầu hoặc đã kết thúc", {"status": route["status"]})
    if route["started_at"] and completed_at < route["started_at"]:
        raise ApiError(422, "completed_at trước thời điểm bắt đầu tuyến",
                       {"field": "completed_at"})
    stop = next((s for s in route["stops"] if s["stop_order"] == body.stop_order), None)
    if not stop or stop["bin_id"] != body.bin_id:
        raise ApiError(422, "Điểm dừng không khớp với thùng", {"field": "stop_order"})
    if stop["status"] != "pending":
        raise ApiError(409, "Điểm dừng này đã được xử lý", {"stop_status": stop["status"]})

    database.routes.update_one(
        {"_id": route["_id"], "stops.stop_order": body.stop_order},
        {"$set": {"stops.$.status": "collected", "stops.$.completed_at": completed_at,
                  "stops.$.collection_event_id": event_id, "updated_at": now}},
        session=session,
    )


def create_event(body, idempotency_key, user, request_id):
    """Record one collection. Returns (event, created); a replay returns created=False."""
    database = get_database()
    digest = request_hash(body, user["_id"])
    existing = database.collection_events.find_one({"idempotency_key": idempotency_key})
    if existing:
        return _replay(database, existing, digest), False

    now = utcnow()
    completed_at = naive_utc(body.completed_at)
    if completed_at > now + CLOCK_SKEW:
        raise ApiError(422, "completed_at không được ở tương lai", {"field": "completed_at"})
    event_id = f"col-{uuid.uuid4().hex}"

    def work(database, session):
        bin_doc = database.bins.find_one({"_id": body.bin_id}, {"waste_type": 1, "status": 1},
                                         session=session)
        if not bin_doc:
            raise ApiError(404, "Không tìm thấy thùng", {"bin_id": body.bin_id})
        if bin_doc["status"] == "retired":
            raise ApiError(409, "Thùng đã ngừng sử dụng", {"bin_id": body.bin_id})
        if body.route_id:
            _collect_stop(database, session, body, user, completed_at, event_id, now)

        event = {
            "_id": event_id, "idempotency_key": idempotency_key, "request_hash": digest,
            "bin_id": body.bin_id, "worker_id": user["_id"], "route_id": body.route_id,
            "stop_order": body.stop_order, "completed_at": completed_at, "recorded_at": now,
            "waste_type_snapshot": bin_doc["waste_type"],
            "measured_weight_kg": body.measured_weight_kg, "weight_source": body.weight_source,
            "fill_before_pct": body.fill_before_pct, "fill_after_pct": body.fill_after_pct,
            "note": body.note,
        }
        database.collection_events.insert_one(event, session=session)
        audit_service.record(database, actor_id=user["_id"], action="collection_create",
                             entity_type="collection_event", entity_id=event_id,
                             summary=f"{user['display_name']} thu gom thùng {body.bin_id}",
                             request_id=request_id, occurred_at=now, session=session)
        return event

    try:
        event = run_transaction(work)
    except DuplicateKeyError:
        # Lost a race: either the same key was just stored, or the stop was collected.
        again = database.collection_events.find_one({"idempotency_key": idempotency_key})
        if again:
            return _replay(database, again, digest), False
        raise ApiError(409, "Điểm dừng này đã được ghi nhận thu gom",
                       {"route_id": body.route_id, "stop_order": body.stop_order})
    return event_view(event, user["display_name"]), True


def list_events(viewer, bin_id, worker_id, route_id, start, end, limit, cursor):
    """Newest first, paged on (completed_at, _id). Collectors only see their own."""
    if "admin" not in viewer["roles"]:
        worker_id = viewer["_id"]
    if start and end and start > end:
        raise ApiError(422, "from phải nhỏ hơn hoặc bằng to", {"field": "from"})

    conditions = []
    for field, value in (("bin_id", bin_id), ("worker_id", worker_id), ("route_id", route_id)):
        if value is not None:
            conditions.append({field: value})
    if start:
        conditions.append({"completed_at": {"$gte": start}})
    if end:
        conditions.append({"completed_at": {"$lte": end}})
    if cursor:
        ms, event_id = decode_cursor(cursor, 2)
        done = from_ms(ms)
        conditions.append({"$or": [{"completed_at": {"$lt": done}},
                                   {"completed_at": done, "_id": {"$gt": event_id}}]})

    database = get_database()
    events = list(database.collection_events.find({"$and": conditions} if conditions else {})
                  .sort([("completed_at", -1), ("_id", 1)]).limit(limit + 1))
    has_more = len(events) > limit
    events = events[:limit]
    names = users_service.display_names(database, {event["worker_id"] for event in events})
    return {
        "items": [event_view(event, names.get(event["worker_id"])) for event in events],
        "next_cursor": (encode_cursor([to_ms(events[-1]["completed_at"]), events[-1]["_id"]])
                        if has_more else None),
    }
