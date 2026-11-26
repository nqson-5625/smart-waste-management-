"""Road distances and paths from the OSRM container (docker-compose service ``osrm``).

OSRM answers from an offline OpenStreetMap extract of Hanoi with the car profile, so the
distances follow real streets, one-way rules included. Every function returns None when
OSRM is off (``OSRM_URL`` empty), unreachable, still building its map, or cannot place a
point; callers then fall back to straight-line distances and say so.
"""

import json
import logging
import urllib.request

from ..core.config import get_settings


TIMEOUT_S = 15
log = logging.getLogger("osrm")


def _call(service, points, query):
    base = get_settings().osrm_url
    if not base:
        return None
    coords = ";".join(f"{p['lng']:.6f},{p['lat']:.6f}" for p in points)
    try:
        with urllib.request.urlopen(f"{base}/{service}/v1/driving/{coords}?{query}",
                                    timeout=TIMEOUT_S) as response:
            body = json.load(response)
    except (OSError, ValueError) as error:  # URLError, HTTPError and timeouts are OSError
        log.warning("OSRM %s failed, using straight lines: %s", service, error)
        return None
    return body if body.get("code") == "Ok" else None


def distance_matrix(points):
    """Road metres ``m[i][j]`` from ``points[i]`` to ``points[j]``, or None."""
    body = _call("table", points, "annotations=distance")
    if not body:
        return None
    matrix = body["distances"]
    if any(value is None for row in matrix for value in row):  # a point with no road to it
        log.warning("OSRM found no road between some points, using straight lines")
        return None
    return matrix


def road_path(points):
    """[[lng, lat], ...] along the streets through ``points`` in order, or None."""
    body = _call("route", points, "overview=full&geometries=geojson")
    return body["routes"][0]["geometry"]["coordinates"] if body else None
