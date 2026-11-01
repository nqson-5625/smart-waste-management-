"""MongoDB connection helpers for backend read/query workloads."""

from functools import lru_cache

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from .config import get_settings


@lru_cache(maxsize=1)
def get_database():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    return client.get_database(settings.mongo_db)


def run_transaction(callback):
    """Run ``callback(database, session)`` in one majority-committed transaction.

    The driver retries transient errors (write conflicts) automatically; any other
    exception aborts the transaction and is re-raised.
    """
    database = get_database()
    with database.client.start_session() as session:
        return session.with_transaction(
            lambda s: callback(database, s),
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )


def get_device(device_id):
    """Read one device registration and its metadata from MongoDB."""
    return get_database().devices.find_one({"_id": device_id})


def get_bin(bin_id):
    """Read one physical bin document."""
    return get_database().bins.find_one({"_id": bin_id})


def get_bin_state(bin_id):
    """Read the current projection for one physical bin."""
    return get_database().bin_state.find_one({"_id": bin_id})
