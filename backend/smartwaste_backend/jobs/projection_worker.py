"""Projection worker: claim pending telemetry and apply projection_service to it.

Run: python -m smartwaste_backend.jobs.projection_worker

Each loop claims one pending telemetry document with a 60-second lease, then
applies it inside a single snapshot transaction that re-checks the lease, so
several workers can run without double-processing. Failures retry with
exponential backoff and become blocked after MAX_ATTEMPTS.
"""

import logging
import os
import socket
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from ..core.db import get_database
from ..services import projection_service


LEASE = timedelta(seconds=60)
MAX_ATTEMPTS = 10
IDLE_SLEEP_S = 1.0
WORKER_ID = os.environ.get("WORKER_ID") or f"worker-{socket.gethostname()}-{os.getpid()}"

log = logging.getLogger("smartwaste.worker")


def claim(database, now):
    """Atomically lease one pending document whose retry time has come."""
    return database.telemetry.find_one_and_update(
        {
            "processing.state": "pending",
            "processing.next_retry_at": {"$lte": now},
            "$or": [
                {"processing.lease_until": None},
                {"processing.lease_until": {"$lt": now}},
            ],
        },
        {
            "$set": {
                "processing.lease_owner": WORKER_ID,
                "processing.lease_until": now + LEASE,
            },
            "$inc": {"processing.attempts": 1},
        },
        sort=[("processing.next_retry_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


def process_one(database=None):
    """Claim and project one document. Returns its final state, or None if idle."""
    if database is None:
        database = get_database()
    now = datetime.now(timezone.utc)
    doc = claim(database, now)
    if not doc:
        return None
    message_id = doc["_id"]
    try:
        with database.client.start_session() as session:
            state = session.with_transaction(
                lambda s: projection_service.apply(database, s, message_id, now, WORKER_ID),
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )
        log.info("%s -> %s", message_id, state)
        return state
    except Exception as exc:  # retry later with backoff; never lose the raw document
        attempts = doc["processing"]["attempts"]
        final = attempts >= MAX_ATTEMPTS
        log.exception("Projection failed for %s (attempt %s)", message_id, attempts)
        database.telemetry.update_one(
            {"_id": message_id, "processing.lease_owner": WORKER_ID},
            {"$set": {
                "processing.state": "blocked" if final else "pending",
                "processing.next_retry_at": now + timedelta(seconds=min(300, 2 ** attempts)),
                "processing.lease_owner": None,
                "processing.lease_until": None,
                "processing.last_error": f"{type(exc).__name__}: {exc}"[:1000],
            }},
        )
        return "blocked" if final else "retry"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("Worker %s started", WORKER_ID)
    while True:
        if process_one() is None:
            time.sleep(IDLE_SLEEP_S)


if __name__ == "__main__":
    main()
