"""Shift job: at each ROUTE_SHIFT_TIMES start, build and assign that shift's routes.

It runs inside the projection worker process (checked once a minute), so no extra
container is needed. Each shift runs once: the run is recorded with a unique audit event
key ``route_shift:<date>:<HH:MM>``. A worker that was down at 06:00 and comes back at
10:00 still runs the 06:00 shift; one that comes back after 14:00 runs only the 14:00 one.
"""

import logging

from pymongo.errors import DuplicateKeyError

from ..core.common import utcnow
from ..core.config import get_settings
from ..core.db import get_database
from ..services import routes_service


log = logging.getLogger("route_worker")


def run_due_shift(now=None):
    """Generate the current shift's routes unless already done; returns them, or None."""
    now = now or utcnow()
    due = routes_service.due_shift(now, get_settings().route_shift_times)
    if not due:
        return None
    day, hhmm = due
    key = f"route_shift:{day}:{hhmm}"
    if get_database().audit_logs.find_one({"event_key": key}, {"_id": 1}):
        return None
    try:
        routes = routes_service.generate(now, routes_service.SYSTEM_ACTOR,
                                         f"rt-{day.replace('-', '')}-{hhmm.replace(':', '')}",
                                         shift_key=key)
    except DuplicateKeyError:  # another worker ran this shift first
        return None
    log.info("Shift %s %s: %d routes, %d stops", day, hhmm, len(routes),
             sum(route["stop_count"] for route in routes))
    return routes
