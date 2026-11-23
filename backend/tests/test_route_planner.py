"""route_planner_service: the routing maths, no database."""

import random

from smartwaste_backend.services import route_planner_service as rp


DEPOT = {"lat": 21.0, "lng": 105.84}


def points(n, seed=7):
    rnd = random.Random(seed)
    return [{"code": f"WB-{i:03d}", "lat": 21.0 + rnd.uniform(0, 0.0125),
             "lng": 105.84 + rnd.uniform(0, 0.0135)} for i in range(n)]


def test_distance_is_metres():
    assert 110 < rp.distance_m(DEPOT, {"lat": 21.001, "lng": 105.84}) < 112  # 0.001° lat


def test_sweep_splits_evenly_without_losing_bins():
    pts = points(41)
    sectors = rp.sweep(DEPOT, pts, 3)
    assert [len(s) for s in sectors] == [14, 14, 13]
    assert sorted(p["code"] for s in sectors for p in s) == sorted(p["code"] for p in pts)
    assert len(rp.sweep(DEPOT, pts[:2], 5)) == 2  # never an empty route
    assert rp.sweep(DEPOT, [], 3) == []
    assert len(rp.plan(DEPOT, pts, 0, 20)) == 1  # nobody free: one unassigned route


def test_order_beats_fixed_order_and_keeps_every_stop():
    pts = points(50)
    ordered = rp.order_stops(DEPOT, pts)
    assert sorted(p["code"] for p in ordered) == sorted(p["code"] for p in pts)
    fixed_m, fixed_trips = rp.baseline(DEPOT, pts, 20)
    assert fixed_trips == 3
    # NN + 2-opt on the same bins is far shorter than visiting them by code
    assert rp.trips_distance_m(DEPOT, ordered, 20) < 0.6 * fixed_m


def test_trips_return_to_depot():
    a, b = {"lat": 21.001, "lng": 105.84}, {"lat": 21.002, "lng": 105.84}
    one_trip = rp.trips_distance_m(DEPOT, [a, b], 20)
    two_trips = rp.trips_distance_m(DEPOT, [a, b], 1)
    assert round(one_trip) == round(2 * rp.distance_m(DEPOT, b))
    assert two_trips > one_trip
    assert [len(t) for t in rp.trips(points(45), 20)] == [20, 20, 5]
