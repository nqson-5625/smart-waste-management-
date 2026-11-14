"""Statistics per waste type over a time window."""

from ..core.db import get_database
from ..core.errors import ApiError


WASTE_TYPES = ("general", "organic", "recyclable", "hazardous", "other")


def waste_by_type(start, end):
    """One row per waste type for [start, end].

    - bin_count: field bins in use (not retired) of that type.
    - avg_fill_pct: mean fill of good-quality samples taken in the window.
    - collection counts and weights come from confirmed collection events; weight is
      only summed for events that were actually weighed, never inferred from fill.
    """
    if start > end:
        raise ApiError(422, "from phải nhỏ hơn hoặc bằng to", {"field": "from"})
    database = get_database()

    type_of_bin = {
        doc["_id"]: doc["waste_type"]
        for doc in database.bins.find(
            {"environment": "field", "status": {"$ne": "retired"}}, {"waste_type": 1})
    }
    rows = {
        waste: {"waste_type": waste, "bin_count": 0, "collection_count": 0,
                "fill_sum": 0.0, "fill_samples": 0, "known_weight_kg": 0.0,
                "known_weight_count": 0, "unknown_weight_count": 0}
        for waste in WASTE_TYPES
    }
    for waste in type_of_bin.values():
        rows[waste]["bin_count"] += 1

    # Served by index telemetry_bin_history (bin_id, sampled_at).
    samples = database.telemetry.aggregate([
        {"$match": {"bin_id": {"$in": list(type_of_bin)},
                    "sampled_at": {"$gte": start, "$lte": end}, "quality": "ok"}},
        {"$group": {"_id": "$bin_id", "sum": {"$sum": "$fill_pct"}, "n": {"$sum": 1}}},
    ])
    for sample in samples:
        row = rows[type_of_bin[sample["_id"]]]
        row["fill_sum"] += sample["sum"]
        row["fill_samples"] += sample["n"]

    collections = database.collection_events.aggregate([
        {"$match": {"completed_at": {"$gte": start, "$lte": end}}},
        {"$group": {
            "_id": "$waste_type_snapshot",
            "count": {"$sum": 1},
            "kg": {"$sum": {"$ifNull": ["$measured_weight_kg", 0]}},
            "weighed": {"$sum": {"$cond": [{"$eq": ["$measured_weight_kg", None]}, 0, 1]}},
        }},
    ])
    for group in collections:
        row = rows[group["_id"]]
        row["collection_count"] = group["count"]
        row["known_weight_kg"] = group["kg"]
        row["known_weight_count"] = group["weighed"]
        row["unknown_weight_count"] = group["count"] - group["weighed"]

    items = []
    for row in rows.values():
        fill_sum, samples_n = row.pop("fill_sum"), row.pop("fill_samples")
        row["avg_fill_pct"] = round(fill_sum / samples_n, 1) if samples_n else None
        row["known_weight_kg"] = (round(row["known_weight_kg"], 2)
                                  if row["known_weight_count"] else None)
        items.append(row)
    return {"items": items}
