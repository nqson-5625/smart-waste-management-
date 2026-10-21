"""Bin read endpoints: list with current state, detail, telemetry history."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query

from .alerts import alert_view
from .auth import current_user, require_roles
from .common import (
    CLOCK_SKEW, STALE_AFTER, Limit, decode_cursor, encode_cursor, from_ms, iso, is_fresh,
    naive_utc, to_ms, utcnow,
)
from .db import get_database
from .errors import ApiError
from .telemetry import list_telemetry


router = APIRouter(prefix="/bins", tags=["bins"])

WasteType = Literal["general", "organic", "recyclable", "hazardous", "other"]
BinStatus = Literal["active", "maintenance", "retired"]

# Latest confirmed collection per bin; served by index collection_bin_time.
LAST_COLLECTION = {
    "$lookup": {
        "from": "collection_events",
        "localField": "_id",
        "foreignField": "bin_id",
        "pipeline": [{"$sort": {"completed_at": -1}}, {"$limit": 1},
                     {"$project": {"_id": 0, "completed_at": 1}}],
        "as": "last_collection",
    }
}


def state_view(state, last_collected_at, now):
    if not state or not state["device_id"] or not state["latest_message_id"]:
        return None
    good = state["last_good"] or {}
    return {
        "device_id": state["device_id"],
        "fill_pct": good.get("fill_pct"),
        "distance_mm": good.get("distance_mm"),
        "sampled_at": iso(good.get("sampled_at")),
        "latest_quality": state["latest_quality"],
        "latest_sampled_at": iso(state["latest_sampled_at"]),
        "alarm_active": state["alarm_active"],
        "last_contact_at": iso(state["last_contact_at"]),
        "last_collected_at": iso(last_collected_at),
        "fresh": is_fresh(state["last_good"], now),
    }


def bin_view(doc, now):
    location = doc["location"]
    lng, lat = location["coordinates"] if location else (None, None)
    collections = doc.get("last_collection") or [{}]
    state = (doc.get("state") or [None])[0]
    return {
        "id": doc["_id"], "code": doc["code"], "name": doc["name"], "address": doc["address"],
        "ward_code": doc["ward_code"], "waste_type": doc["waste_type"],
        "capacity_l": doc["capacity_l"], "status": doc["status"], "location": location,
        "lat": lat, "lng": lng,
        "state": state_view(state, collections[0].get("completed_at"), now),
    }


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
    now = utcnow()
    match = {"environment": "field"}
    for field, value in (("ward_code", ward_code), ("waste_type", waste_type), ("status", status)):
        if value is not None:
            match[field] = value
    if cursor:
        match["_id"] = {"$gt": decode_cursor(cursor, 1)[0]}

    state_match = {}
    if full is not None:
        state_match["state.alarm_active"] = True if full else {"$ne": True}
    fresh_rule = {
        "state.last_good.time_quality": "gateway_estimated",
        "state.last_good.sampled_at": {"$gte": now - STALE_AFTER, "$lte": now + CLOCK_SKEW},
    }
    if fresh is True:
        state_match.update(fresh_rule)
    elif fresh is False:
        state_match["$nor"] = [fresh_rule]

    # ponytail: state filters run after the join, fine for a ward (~200 bins);
    # denormalise alarm/fresh onto bins if this grows to thousands.
    pipeline = [
        {"$match": match},
        {"$sort": {"_id": 1}},
        {"$lookup": {"from": "bin_state", "localField": "_id", "foreignField": "_id",
                     "as": "state"}},
    ]
    if state_match:
        pipeline.append({"$match": state_match})
    pipeline += [{"$limit": limit + 1}, LAST_COLLECTION]

    docs = list(get_database().bins.aggregate(pipeline))
    has_more = len(docs) > limit
    docs = docs[:limit]
    return {
        "items": [bin_view(doc, now) for doc in docs],
        "next_cursor": encode_cursor([docs[-1]["_id"]]) if has_more else None,
    }


@router.get("/{bin_id}")
def get_bin(bin_id: str, user=Depends(current_user)):
    database = get_database()
    docs = list(database.bins.aggregate([
        {"$match": {"_id": bin_id}},
        {"$lookup": {"from": "bin_state", "localField": "_id", "foreignField": "_id",
                     "as": "state"}},
        LAST_COLLECTION,
    ]))
    if not docs:
        raise ApiError(404, "Không tìm thấy thùng", {"bin_id": bin_id})
    doc = docs[0]
    view = bin_view(doc, utcnow())

    state = (doc["state"] or [None])[0]
    device = None
    if state and state["device_id"]:
        found = database.devices.find_one({"_id": state["device_id"]},
                                          {"lifecycle": 1, "enabled": 1})
        if found:
            device = {"id": found["_id"], "lifecycle": found["lifecycle"],
                      "enabled": found["enabled"]}

    open_alerts = database.alerts.find({"bin_id": bin_id, "active": True}).sort("opened_at", -1)
    return {**view, "notes": doc["notes"], "device": device,
            "open_alerts": [alert_view(alert) for alert in open_alerts]}


@router.get("/{bin_id}/telemetry")
def bin_telemetry(
    bin_id: str,
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(require_roles("admin", "dispatcher")),
):
    start, end = naive_utc(from_), naive_utc(to)
    if start > end:
        raise ApiError(422, "from phải nhỏ hơn hoặc bằng to", {"field": "from"})
    if not get_database().bins.find_one({"_id": bin_id}, {"_id": 1}):
        raise ApiError(404, "Không tìm thấy thùng", {"bin_id": bin_id})

    before = None
    if cursor:
        ms, message_id = decode_cursor(cursor, 2)
        before = (from_ms(ms), message_id)
    rows = list_telemetry(bin_id, start_at=start, end_at=end, limit=limit + 1, before=before)
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [{
            "message_id": row["_id"], "sampled_at": iso(row["sampled_at"]),
            "received_at": iso(row["received_at"]), "reason": row["reason"],
            "quality": row["quality"], "fill_pct": row["fill_pct"],
            "distance_mm": row["distance_mm"], "alarm_active": row["alarm_active"],
            "lid_open": row["lid_open"], "rssi_dbm": row["rssi_dbm"], "snr_db": row["snr_db"],
            "time_quality": row["time_quality"],
        } for row in rows],
        "next_cursor": (encode_cursor([to_ms(rows[-1]["sampled_at"]), rows[-1]["_id"]])
                        if has_more else None),
    }
