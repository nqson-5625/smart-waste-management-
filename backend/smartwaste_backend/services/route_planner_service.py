"""Route planning maths, no database: split bins between collectors and order the stops.

Ported from the week 9 proposal simulation (plan/tools/route_sim.py):
- sweep: sort bins by angle around the depot and cut them into k equal sectors, one per
  collector, so two people never criss-cross the same streets (Gillett and Miller, 1974);
- nearest neighbour from the depot, then 2-opt to untangle crossing legs;
- a route is cut into trips of at most ``max_stops`` stops, each trip leaving from and
  returning to the depot (the truck unloads between trips).

Distances come from a ``dist(a, b)`` function: road metres from an OSRM matrix
(``road_metric``) or, as a fallback, great-circle metres (``distance_m``). Planned and
baseline always use the same one, so the reduction percentage stays meaningful.

Points are dicts with ``lat`` and ``lng`` (plus ``i``, their matrix index, for road
distances); any other keys are carried along untouched.
"""

import math

EARTH_RADIUS_M = 6_371_000


def distance_m(a, b):
    """Straight-line (haversine) metres."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def road_metric(matrix):
    """(directed, symmetric) distance functions over an OSRM matrix indexed by ``p["i"]``.

    One-way streets make A->B differ from B->A. Ordering uses the symmetric average, which
    keeps 2-opt's segment reversal valid; reported metres use the directed values.
    """
    def directed(a, b):
        return matrix[a["i"]][b["i"]]

    def symmetric(a, b):
        return (matrix[a["i"]][b["i"]] + matrix[b["i"]][a["i"]]) / 2

    return directed, symmetric


def trips(stops, max_stops):
    return [stops[i:i + max_stops] for i in range(0, len(stops), max_stops)]


def trips_distance_m(depot, stops, max_stops, dist=distance_m):
    """Depot -> stops -> depot for every trip of at most ``max_stops`` stops."""
    total = 0.0
    for trip in trips(stops, max_stops):
        path = [depot, *trip, depot]
        total += sum(dist(p, q) for p, q in zip(path, path[1:]))
    return total


def nearest_neighbor(depot, points, dist=distance_m):
    left, here, order = list(points), depot, []
    while left:
        nearest = min(left, key=lambda p: dist(here, p))
        left.remove(nearest)
        order.append(nearest)
        here = nearest
    return order


def two_opt(depot, order, dist=distance_m):
    """Reverse any segment whose ends cross until no swap shortens the closed tour.

    ``dist`` must be symmetric. ponytail: O(n^2) per pass, 0.2 s for 200 bins; one ward.
    """
    path = [depot, *order, depot]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - 1):
                a, b, c, d = path[i - 1], path[i], path[j], path[j + 1]
                if dist(a, c) + dist(b, d) < dist(a, b) + dist(c, d) - 1e-6:
                    path[i:j + 1] = reversed(path[i:j + 1])
                    improved = True
    return path[1:-1]


def sweep(depot, points, k):
    """min(k, len(points)) sectors of contiguous angle whose sizes differ by at most one."""
    ordered = sorted(points, key=lambda p: math.atan2(p["lat"] - depot["lat"],
                                                      p["lng"] - depot["lng"]))
    k = min(k, len(ordered))
    if k == 0:
        return []
    size, extra = divmod(len(ordered), k)
    sectors, start = [], 0
    for index in range(k):
        end = start + size + (1 if index < extra else 0)
        sectors.append(ordered[start:end])
        start = end
    return sectors


def order_stops(depot, points, max_stops, dist=distance_m, symmetric=None):
    """Visiting order: NN + 2-opt on the symmetric distance, then the cheaper direction."""
    symmetric = symmetric or dist
    order = two_opt(depot, nearest_neighbor(depot, points, symmetric), symmetric)
    backwards = order[::-1]
    return min(order, backwards, key=lambda o: trips_distance_m(depot, o, max_stops, dist))


def plan(depot, points, collectors, max_stops, dist=distance_m, symmetric=None):
    """One ordered stop list per sector, at least one sector when there are points."""
    return [order_stops(depot, sector, max_stops, dist, symmetric)
            for sector in sweep(depot, points, max(collectors, 1))]


def baseline(depot, points, max_stops, dist=distance_m):
    """(metres, trips) of the fixed schedule: every active bin, ordered by code."""
    fixed = sorted(points, key=lambda p: p["code"])
    return trips_distance_m(depot, fixed, max_stops, dist), len(trips(fixed, max_stops))
