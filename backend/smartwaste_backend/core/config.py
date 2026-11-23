"""Runtime settings, read once from environment variables (see .env.example)."""

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    jwt_secret: str | None
    cors_origins: list[str]
    # Collection routes (docs/06 section 3.14); defaults agreed in the week 9 proposal.
    depot_lat: float
    depot_lng: float
    route_shift_times: list[str]  # "HH:MM" in Vietnam time, sorted
    route_max_stops: int
    route_forecast: bool
    osrm_url: str  # road distances; empty means straight-line distances only


def _shift_times(raw):
    """'6:00, 14:00' -> ['06:00', '14:00']; a bad value stops the process at start-up."""
    times = sorted(datetime.strptime(t.strip(), "%H:%M").strftime("%H:%M")
                   for t in raw.split(",") if t.strip())
    if not times:
        raise RuntimeError("ROUTE_SHIFT_TIMES needs at least one HH:MM")
    return times


@lru_cache(maxsize=1)
def get_settings():
    def env(name, default=None):
        """Unset or empty both mean the default (docker-compose passes empty values)."""
        return os.environ.get(name) or default

    return Settings(
        mongo_uri=env("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        mongo_db=env("MONGO_DB", "smartwaste_v2"),
        jwt_secret=env("JWT_SECRET") or None,
        cors_origins=[
            origin.strip()
            for origin in env("CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ],
        depot_lat=float(env("DEPOT_LAT", "21.0047")),  # Parabol gate, HUST
        depot_lng=float(env("DEPOT_LNG", "105.8431")),
        route_shift_times=_shift_times(env("ROUTE_SHIFT_TIMES", "06:00,14:00")),
        route_max_stops=int(env("ROUTE_MAX_STOPS", "20")),
        route_forecast=env("ROUTE_FORECAST", "true").lower() in ("1", "true", "yes"),
        osrm_url=env("OSRM_URL", "").rstrip("/"),
    )
