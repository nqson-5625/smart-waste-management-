"""Shared helpers: ISO timestamps, opaque cursors, freshness."""

import base64
import json
from datetime import datetime, timedelta, timezone

from fastapi import Query

from .errors import ApiError


EPOCH = datetime(1970, 1, 1)
STALE_AFTER = timedelta(hours=8)
CLOCK_SKEW = timedelta(minutes=5)

Limit = Query(50, ge=1, le=100)


def utcnow():
    """Naive UTC now, comparable with datetimes read from pymongo."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(value):
    if value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def iso(value):
    return naive_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def to_ms(value):
    return (naive_utc(value) - EPOCH) // timedelta(milliseconds=1)


def from_ms(ms):
    return EPOCH + timedelta(milliseconds=ms)


def encode_cursor(values):
    raw = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor, size):
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if not isinstance(values, list) or len(values) != size:
            raise ValueError
        return values
    except ValueError:
        raise ApiError(422, "cursor không hợp lệ", {"field": "cursor"})


def is_fresh(last_good, now):
    """Fresh = good sample within 8 hours, not in the future, with a trusted clock."""
    if not last_good or last_good["time_quality"] != "gateway_estimated":
        return False
    sampled_at = last_good["sampled_at"]
    return sampled_at is not None and now - STALE_AFTER <= sampled_at <= now + CLOCK_SKEW
