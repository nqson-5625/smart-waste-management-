"""MongoDB connection helpers for backend read/query workloads."""

import os
from functools import lru_cache

from pymongo import MongoClient


@lru_cache(maxsize=1)
def get_database():
    client = MongoClient(
        os.environ.get(
            "MONGO_URI",
            "mongodb://localhost:27017/?directConnection=true",
        ),
        serverSelectionTimeoutMS=5000,
    )
    return client.get_database(os.environ.get("MONGO_DB", "smartwaste_v2"))


def get_device(device_id):
    """Read one device registration and its metadata from MongoDB."""
    return get_database().devices.find_one({"_id": device_id})


def get_bin(bin_id):
    """Read one physical bin document."""
    return get_database().bins.find_one({"_id": bin_id})


def get_bin_state(bin_id):
    """Read the current projection for one physical bin."""
    return get_database().bin_state.find_one({"_id": bin_id})
