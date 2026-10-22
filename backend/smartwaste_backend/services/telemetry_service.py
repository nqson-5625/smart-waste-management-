"""Read-only schema-v2 telemetry queries for backend APIs."""

from ..core.db import get_database


PUBLIC_PROJECTION = {
    "content_hash": 0,
    "processing": 0,
}


def list_telemetry(
    bin_id,
    *,
    start_at,
    end_at,
    limit=100,
    before=None,
):
    """Return newest-first bin telemetry within a required UTC time range.

    ``before`` is a ``(sampled_at, _id)`` cursor matching the
    ``telemetry_bin_history`` index order.
    """
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if start_at is None or end_at is None or start_at > end_at:
        raise ValueError("a valid start_at/end_at range is required")

    clauses = [
        {"bin_id": bin_id},
        {"sampled_at": {"$gte": start_at, "$lte": end_at}},
    ]
    if before is not None:
        cursor_time, cursor_id = before
        clauses.append(
            {
                "$or": [
                    {"sampled_at": {"$lt": cursor_time}},
                    {
                        "sampled_at": cursor_time,
                        "_id": {"$gt": cursor_id},
                    },
                ]
            }
        )

    return list(
        get_database()
        .telemetry.find({"$and": clauses}, PUBLIC_PROJECTION)
        .sort([("sampled_at", -1), ("_id", 1)])
        .limit(limit)
    )


def get_latest_telemetry(bin_id):
    """Return the latest mapped telemetry for one bin."""
    return get_database().telemetry.find_one(
        {"bin_id": bin_id, "sampled_at": {"$type": "date"}},
        PUBLIC_PROJECTION,
        sort=[("sampled_at", -1), ("_id", 1)],
    )
