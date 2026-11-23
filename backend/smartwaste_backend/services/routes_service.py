"""Collection routes: automatic generation per shift, listing and status changes.

Rules come from the week 9 proposal (option B) and docs/06 section 3.14:
- each shift the system picks the bins to collect, splits them between the active
  collectors and assigns the routes; the admin only handles exceptions;
- a bin is picked when its fresh, good reading says full (alarm or >= 80 %), or when the
  forecast says it will overflow before the next shift;
- one bin is never in two unfinished routes.
"""

import math
import re
import uuid
from collections import defaultdict
from datetime import timedelta, timezone

from ..core.common import decode_cursor, encode_cursor, is_fresh, iso, utcnow
from ..core.config import get_settings
from ..core.db import get_database, run_transaction
from ..core.errors import ApiError
from . import audit_service, osrm_service, route_planner_service, users_service
from .bins_service import JOIN_STATE, LAST_COLLECTION


VN = timezone(timedelta(hours=7))
SYSTEM_ACTOR = "system:route-worker"
MIN_FILL_PCT = 80.0         # firmware full threshold; the alarm already covers per-device values
FORECAST_MARGIN = 1.3       # safety factor from the simulation: 0 overflows at +-25 % rate error
RATE_WINDOW = timedelta(hours=48)
MAX_ROUTE_STOPS = 200       # routes.stops limit in the MongoDB schema
OPEN = ["planned", "assigned", "in_progress"]


# ---------------------------------------------------------------- time helpers

def local(now):
    """Naive UTC -> aware Vietnam time."""
    return now.replace(tzinfo=timezone.utc).astimezone(VN)


def service_date(now):
    return local(now).strftime("%Y-%m-%d")


def hours_to_next_shift(now, shift_times):
    """Hours from ``now`` to the next shift start; with one shift a day that is up to 24 h."""
    here = local(now)
    starts = [here.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0)
              for t in shift_times]
    upcoming = [s for s in starts if s > here] or [starts[0] + timedelta(days=1)]
    return (upcoming[0] - here).total_seconds() / 3600


def due_shift(now, shift_times):
    """(service date, "HH:MM") of the latest shift that has started today, or None."""
    here = local(now)
    started = [t for t in shift_times if t <= here.strftime("%H:%M")]
    return (here.strftime("%Y-%m-%d"), started[-1]) if started else None


# ---------------------------------------------------------------- views

def stop_view(stop):
    lng, lat = stop["location_snapshot"]["coordinates"]
    return {
        "stop_order": stop["stop_order"], "bin_id": stop["bin_id"], "lat": lat, "lng": lng,
        "planned_fill_pct": stop["planned_fill_pct"], "status": stop["status"],
        "completed_at": iso(stop["completed_at"]),
        "collection_event_id": stop["collection_event_id"], "skip_reason": stop["skip_reason"],
    }


def route_view(route, names, max_stops):
    lng, lat = route["depot"]["coordinates"]
    stops = route["stops"]
    return {
        "id": route["_id"], "service_date": route["service_date"], "status": route["status"],
        "assigned_worker_id": route["assigned_worker_id"],
        "assigned_worker_name": names.get(route["assigned_worker_id"]),
        "depot": {"lat": lat, "lng": lng},
        "stops": [stop_view(stop) for stop in stops],
        "stop_count": len(stops),
        "collected_count": sum(stop["status"] == "collected" for stop in stops),
        "trip_count": math.ceil(len(stops) / max_stops),
        # "road": OSRM street distances; "straight": fallback while OSRM was unavailable
        "distance_method": ("road" if (route["baseline_method"] or "").startswith("road")
                            else "straight"),
        "planned_distance_m": route["planned_distance_m"],
        "baseline_distance_m": route["baseline_distance_m"],
        "actual_distance_m": route["actual_distance_m"],
        "actual_distance_source": route["actual_distance_source"],
        "started_at": iso(route["started_at"]), "completed_at": iso(route["completed_at"]),
        "created_by": route["created_by"], "created_at": iso(route["created_at"]),
    }


def _views(database, routes, session=None):
    names = users_service.display_names(
        database, {r["assigned_worker_id"] for r in routes if r["assigned_worker_id"]}, session)
    max_stops = get_settings().route_max_stops
    return [route_view(route, names, max_stops) for route in routes]


# ---------------------------------------------------------------- picking bins

def _fill_rates(database, session, bins, now):
    """%/hour per bin from good samples of its current device since its last collection."""
    if not bins:
        return {}
    rows = database.telemetry.find(
        {"bin_id": {"$in": [b["bin_id"] for b in bins]}, "quality": "ok",
         "fill_pct": {"$ne": None}, "sampled_at": {"$gte": now - RATE_WINDOW, "$lte": now}},
        {"bin_id": 1, "assignment_id": 1, "sampled_at": 1, "fill_pct": 1}, session=session,
    ).sort("sampled_at", 1)
    by_id = {b["bin_id"]: b for b in bins}
    samples = defaultdict(list)
    for row in rows:
        bin_ = by_id[row["bin_id"]]
        after_collection = not bin_["collected_at"] or row["sampled_at"] > bin_["collected_at"]
        if row["assignment_id"] == bin_["assignment_id"] and after_collection:
            samples[row["bin_id"]].append(row)
    rates = {}
    for bin_id, rows in samples.items():
        hours = (rows[-1]["sampled_at"] - rows[0]["sampled_at"]).total_seconds() / 3600
        if len(rows) >= 2 and hours > 0:
            rates[bin_id] = max(0.0, (rows[-1]["fill_pct"] - rows[0]["fill_pct"]) / hours)
    return rates


def pick_bins(database, session, now, settings):
    """(bins to collect, every active field bin with coordinates for the baseline)."""
    docs = list(database.bins.aggregate([
        {"$match": {"environment": "field", "status": "active", "location": {"$ne": None}}},
        JOIN_STATE, LAST_COLLECTION,
    ], session=session))
    busy = {stop["bin_id"]
            for route in database.routes.find({"status": {"$in": OPEN}}, {"stops": 1},
                                              session=session)
            for stop in route["stops"] if stop["status"] == "pending"}

    every, readable = [], []
    for doc in docs:
        lng, lat = doc["location"]["coordinates"]
        state = (doc["state"] or [None])[0]
        good = (state or {}).get("last_good") or {}
        collected_at = (doc["last_collection"] or [{}])[0].get("completed_at")
        point = {"bin_id": doc["_id"], "code": doc["code"], "lat": lat, "lng": lng,
                 "location": doc["location"], "fill_pct": good.get("fill_pct"),
                 "sampled_at": good.get("sampled_at"), "collected_at": collected_at,
                 "assignment_id": (state or {}).get("assignment_id"),
                 "alarm": (state or {}).get("alarm_active") is True}
        every.append(point)
        usable = (state and state["device_id"] and state["latest_quality"] == "ok"
                  and is_fresh(state["last_good"], now) and point["fill_pct"] is not None)
        emptied = collected_at and collected_at >= point["sampled_at"] if usable else False
        if usable and not emptied and doc["_id"] not in busy:
            readable.append(point)

    full = [p for p in readable if p["alarm"] or p["fill_pct"] >= MIN_FILL_PCT]
    picked = {p["bin_id"] for p in full}
    if settings.route_forecast:
        rest = [p for p in readable if p["bin_id"] not in picked]
        rates = _fill_rates(database, session, rest, now)
        hours = hours_to_next_shift(now, settings.route_shift_times)
        full += [p for p in rest
                 if p["fill_pct"] + FORECAST_MARGIN * rates.get(p["bin_id"], 0) * hours >= 100]
    return full, every


# ---------------------------------------------------------------- generating

def _metric(depot, every):
    """Distance functions for this run: road metres from OSRM, else straight lines.

    One OSRM table call covers the depot and every active bin, so the routes and the
    baseline are measured the same way. Points get their matrix index in ``i``.
    """
    for index, point in enumerate([depot, *every]):
        point["i"] = index
    matrix = osrm_service.distance_matrix([depot, *every])
    if matrix is None:
        return route_planner_service.distance_m, None, "straight"
    directed, symmetric = route_planner_service.road_metric(matrix)
    return directed, symmetric, "road"


def _cancel_unstarted(database, session, now, actor_id, request_id):
    """A new shift replaces routes nobody started; their bins go back into the pool."""
    for route in database.routes.find({"status": {"$in": ["planned", "assigned"]}}, {"_id": 1},
                                      session=session):
        database.routes.update_one({"_id": route["_id"]},
                                   {"$set": {"status": "cancelled", "updated_at": now}},
                                   session=session)
        audit_service.record(database, actor_id=actor_id, action="route_cancel",
                             entity_type="route", entity_id=route["_id"],
                             summary=f"Hủy tuyến {route['_id']}: hết ca, chưa bắt đầu",
                             request_id=request_id, session=session)


def _free_collectors(database, session):
    """Active collectors with no route in hand, in id order so the result is repeatable."""
    holding = set(database.routes.distinct(
        "assigned_worker_id", {"status": {"$in": ["assigned", "in_progress"]}}, session=session))
    users = database.users.find({"roles": "collector", "status": "active"}, {"_id": 1},
                                session=session).sort("_id", 1)
    return [user["_id"] for user in users if user["_id"] not in holding]


def generate(now, actor_id, id_prefix, request_id=None, shift_key=None):
    """Build and save this shift's routes in one transaction; returns the new route views.

    ``shift_key`` marks a scheduled run: the unique audit event key makes a second run of the
    same shift fail with DuplicateKeyError, and unstarted routes of the last shift are
    cancelled. A manual run (admin "generate now") only adds routes for bins not yet taken.
    """
    settings = get_settings()
    depot = {"lat": settings.depot_lat, "lng": settings.depot_lng}

    def work(database, session):
        if shift_key:
            audit_service.record(database, actor_id=actor_id, action="route_shift_run",
                                 entity_type="shift", entity_id=shift_key.split(":", 1)[1],
                                 summary=f"Lập tuyến tự động ca {shift_key}",
                                 event_key=shift_key, session=session)
            _cancel_unstarted(database, session, now, actor_id, request_id)
        bins, every = pick_bins(database, session, now, settings)
        if not bins:
            return []
        # Taking a bin writes it, so two runs racing for the same bin conflict and one retries.
        database.bins.update_many({"_id": {"$in": [b["bin_id"] for b in bins]}},
                                  {"$set": {"updated_at": now}}, session=session)

        collectors = _free_collectors(database, session)
        dist, symmetric, method = _metric(depot, every)
        sectors = math.ceil(len(bins) / MAX_ROUTE_STOPS)
        routes_stops = route_planner_service.plan(depot, bins, max(len(collectors), sectors),
                                                  settings.route_max_stops, dist, symmetric)
        base_m, base_trips = route_planner_service.baseline(depot, every,
                                                            settings.route_max_stops, dist)
        routes = []
        for index, stops in enumerate(routes_stops):
            worker = collectors[index] if index < len(collectors) else None
            routes.append({
                "_id": f"{id_prefix}-{index + 1}", "service_date": service_date(now),
                "assigned_worker_id": worker, "status": "assigned" if worker else "planned",
                "depot": {"type": "Point", "coordinates": [depot["lng"], depot["lat"]]},
                "stops": [{
                    "stop_order": order, "bin_id": stop["bin_id"],
                    "location_snapshot": stop["location"], "planned_fill_pct": stop["fill_pct"],
                    "planned_sampled_at": stop["sampled_at"], "status": "pending",
                    "completed_at": None, "collection_event_id": None, "skip_reason": None,
                } for order, stop in enumerate(stops, start=1)],
                "planned_distance_m": round(route_planner_service.trips_distance_m(
                    depot, stops, settings.route_max_stops, dist)),
                "actual_distance_m": None, "actual_distance_source": None,
                # the whole day's fixed schedule; reports take it once per day, not per route
                "baseline_distance_m": round(base_m),
                "baseline_method": (f"{method} fixed-code-order bins={len(every)} "
                                    f"trips={base_trips}"),
                "started_at": None, "completed_at": None, "created_by": actor_id,
                "created_at": now, "updated_at": now,
            })
        database.routes.insert_many(routes, session=session)
        for route in routes:
            audit_service.record(
                database, actor_id=actor_id, action="route_create", entity_type="route",
                entity_id=route["_id"],
                summary=(f"Lập tuyến {route['_id']}: {len(route['stops'])} điểm, "
                         f"giao {route['assigned_worker_id'] or 'chưa giao'}"),
                request_id=request_id, session=session)
        return _views(database, routes, session)

    return run_transaction(work)


def generate_now(user, request_id):
    """Admin "generate now": same algorithm as the shift job, for bins not yet in a route."""
    now = utcnow()
    prefix = f"rt-{local(now):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"  # two clicks never clash
    return {"items": generate(now, user["_id"], prefix, request_id)}


# ---------------------------------------------------------------- reading

def list_routes(viewer, date, status, worker_id, limit, cursor):
    """Newest first. Collectors only ever see their own routes."""
    if "admin" not in viewer["roles"]:
        worker_id = viewer["_id"]
    query = {}
    for field, value in (("service_date", date), ("status", status),
                         ("assigned_worker_id", worker_id)):
        if value is not None:
            query[field] = value
    if cursor:
        query["_id"] = {"$lt": decode_cursor(cursor, 1)[0]}
    database = get_database()
    routes = list(database.routes.find(query).sort("_id", -1).limit(limit + 1))
    has_more = len(routes) > limit
    routes = routes[:limit]
    return {"items": _views(database, routes),
            "next_cursor": encode_cursor([routes[-1]["_id"]]) if has_more else None}


def route_geometry(route_id, viewer):
    """The path to draw: depot -> stops -> depot per trip, along the streets when OSRM is up.

    GeoJSON LineString; ``source`` says "road" or "straight" (OSRM unavailable).
    """
    route = get_database().routes.find_one({"_id": route_id})
    if not route:
        raise ApiError(404, "Không tìm thấy tuyến", {"route_id": route_id})
    if "admin" not in viewer["roles"] and route["assigned_worker_id"] != viewer["_id"]:
        raise ApiError(403, "Chỉ xem được tuyến của mình")
    lng, lat = route["depot"]["coordinates"]
    depot = {"lat": lat, "lng": lng}
    stops = [dict(zip(("lng", "lat"), s["location_snapshot"]["coordinates"]))
             for s in route["stops"]]
    waypoints = [depot]
    for trip in route_planner_service.trips(stops, get_settings().route_max_stops):
        waypoints += [*trip, depot]
    path = osrm_service.road_path(waypoints)
    return {"route_id": route_id, "type": "LineString", "source": "road" if path else "straight",
            "coordinates": path or [[p["lng"], p["lat"]] for p in waypoints]}


# ---------------------------------------------------------------- status changes

def _active_collector(database, session, worker_id):
    user = database.users.find_one({"_id": worker_id}, {"roles": 1, "status": 1},
                                   session=session)
    if not user or user["status"] != "active" or "collector" not in user["roles"]:
        raise ApiError(422, "Người nhận tuyến phải là collector đang hoạt động",
                       {"field": "assigned_worker_id"})


def change_status(route_id, body, user, request_id):
    """Apply one allowed transition from docs/06 section 3.14; anything else is 409."""
    is_admin = "admin" in user["roles"]

    def work(database, session):
        now = utcnow()
        route = database.routes.find_one({"_id": route_id}, session=session)
        if not route:
            raise ApiError(404, "Không tìm thấy tuyến", {"route_id": route_id})
        current, target = route["status"], body.status
        own = route["assigned_worker_id"] == user["_id"]
        changes, action = {}, None

        if target == "assigned":
            if not is_admin:
                raise ApiError(403, "Chỉ admin giao tuyến")
            if current not in ("planned", "assigned"):
                raise ApiError(409, f"Tuyến đang {current}, không giao lại được",
                               {"status": current})
            _active_collector(database, session, body.assigned_worker_id)
            changes, action = {"assigned_worker_id": body.assigned_worker_id}, "route_assign"
        elif target == "in_progress":
            if not own:
                raise ApiError(403, "Chỉ người được giao mới bắt đầu tuyến")
            if current != "assigned":
                raise ApiError(409, f"Tuyến đang {current}, không bắt đầu được",
                               {"status": current})
            changes, action = {"started_at": now}, "route_start"
        elif target == "completed":
            if not own:
                raise ApiError(403, "Chỉ người được giao mới hoàn thành tuyến")
            if current != "in_progress":
                raise ApiError(409, f"Tuyến đang {current}, chưa hoàn thành được",
                               {"status": current})
            pending = [s for s in route["stops"] if s["status"] == "pending"]
            if pending and not body.skip_reason:
                raise ApiError(422, "Còn điểm chưa thu: cần ghi lý do bỏ qua",
                               {"field": "skip_reason", "pending": len(pending)})
            stops = [{**s, "status": "skipped", "skip_reason": body.skip_reason}
                     if s["status"] == "pending" else s for s in route["stops"]]
            changes = {"stops": stops, "completed_at": now,
                       "actual_distance_m": body.actual_distance_m,
                       "actual_distance_source": body.actual_distance_source}
            action = "route_complete"
        else:  # cancelled
            if not is_admin:
                raise ApiError(403, "Chỉ admin hủy tuyến")
            if current in ("completed", "cancelled"):
                raise ApiError(409, f"Tuyến đã {current}", {"status": current})
            action = "route_cancel"

        updated = {**route, **changes, "status": target, "updated_at": now}
        database.routes.replace_one({"_id": route_id}, updated, session=session)
        audit_service.record(database, actor_id=user["_id"], action=action, entity_type="route",
                             entity_id=route_id, summary=f"Tuyến {route_id}: {current} → {target}",
                             request_id=request_id, session=session)
        return _views(database, [updated], session)[0]

    return run_transaction(work)


# ---------------------------------------------------------------- report

TRIPS = re.compile(r"trips=(\d+)")


def route_report(start, end):
    """Completed routes per service date against the fixed schedule (docs/06 section 3.15).

    The baseline is a whole day's fixed schedule, so it is counted once per day; planned and
    actual add up over the day's routes. Actual stays null unless every route reported it.
    """
    if start > end:
        raise ApiError(422, "from phải nhỏ hơn hoặc bằng to", {"field": "from"})
    max_stops = get_settings().route_max_stops
    days = defaultdict(list)
    for route in get_database().routes.find(
            {"status": "completed", "service_date": {"$gte": start, "$lte": end}}):
        days[route["service_date"]].append(route)

    def reduction(base, value):
        return round((base - value) / base * 100, 1) if base and value is not None else None

    items = []
    for day in sorted(days):
        routes = days[day]
        stops = [s for r in routes for s in r["stops"]]
        actual = [r["actual_distance_m"] for r in routes]
        base_trips = [int(m.group(1)) for r in routes
                      if (m := TRIPS.search(r["baseline_method"] or ""))]
        row = {
            "service_date": day, "route_count": len(routes), "stop_count": len(stops),
            "collected_count": sum(s["status"] == "collected" for s in stops),
            "planned_distance_m": sum(r["planned_distance_m"] for r in routes),
            "actual_distance_m": None if None in actual else sum(actual),
            "baseline_distance_m": max(r["baseline_distance_m"] for r in routes),
            "planned_trips": sum(math.ceil(len(r["stops"]) / max_stops) for r in routes),
            "baseline_trips": max(base_trips) if base_trips else None,
        }
        items.append(row)

    def totals(rows):
        actual = [r["actual_distance_m"] for r in rows]
        trips = [r["baseline_trips"] for r in rows]
        return {
            "planned_distance_m": sum(r["planned_distance_m"] for r in rows),
            "actual_distance_m": None if None in actual else sum(actual),
            "baseline_distance_m": sum(r["baseline_distance_m"] for r in rows),
            "planned_trips": sum(r["planned_trips"] for r in rows),
            "baseline_trips": None if None in trips else sum(trips),
        }

    for row in items:
        row["planned_reduction_pct"] = reduction(row["baseline_distance_m"],
                                                 row["planned_distance_m"])
        row["actual_reduction_pct"] = reduction(row["baseline_distance_m"],
                                                row["actual_distance_m"])
        row["trip_reduction_pct"] = reduction(row["baseline_trips"], row["planned_trips"])
    summary = {"day_count": len(items), "route_count": sum(r["route_count"] for r in items),
               **totals(items)}
    summary["planned_reduction_pct"] = reduction(summary["baseline_distance_m"],
                                                 summary["planned_distance_m"])
    summary["actual_reduction_pct"] = reduction(summary["baseline_distance_m"],
                                                summary["actual_distance_m"])
    summary["trip_reduction_pct"] = reduction(summary["baseline_trips"], summary["planned_trips"])
    return {"items": items, "summary": summary}
