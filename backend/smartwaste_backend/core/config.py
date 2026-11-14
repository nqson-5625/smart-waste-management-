"""Runtime settings, read once from environment variables (see .env.example)."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    jwt_secret: str | None
    cors_origins: list[str]


@lru_cache(maxsize=1)
def get_settings():
    return Settings(
        mongo_uri=os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        mongo_db=os.environ.get("MONGO_DB", "smartwaste_v2"),
        jwt_secret=os.environ.get("JWT_SECRET") or None,
        cors_origins=[
            origin.strip()
            for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ],
    )
