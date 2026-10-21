"""Projection worker: turn pending telemetry into bin_state and alerts.

Run: python -m smartwaste_backend.worker

Each loop claims one pending telemetry document with a 60-second lease, then
applies it inside a single transaction that re-checks the lease, so several
workers can run without double-processing. Rules follow docs/05 section 4.4:
source order is (boot_id, seq); a bad-quality sample never overwrites last_good;
alarm_active changes only on quality=ok non-null values; the full alert opens
once per full episode and resolves when the sensor confirms it cleared.
"""

import logging
import os
import socket
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from .db import get_database


LEASE = timedelta(seconds=60)
MAX_ATTEMPTS = 10
IDLE_SLEEP_S = 1.0
ACTOR = "system-worker"
WORKER_ID = os.environ.get("WORKER_ID") or f"worker-{socket.gethostname()}-{os.getpid()}"

log = logging.getLogger("smartwaste.worker")


def utcnow():
    return datetime.now(timezone.utc)


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


def finish(database, message_id, state, now, error=None, session=None):
    database.telemetry.update_one(
        {"_id": message_id, "processing.lease_owner": WORKER_ID},
        {"$set": {
            "processing.state": state,
            "processing.processed_at": now if state != "pending" else None,
            "processing.lease_owner": None,
            "processing.lease_until": None,
            "processing.last_error": error,
        }},
        session=session,
    )


def audit(database, session, key, action, alert_id, message_id, summary, now):
    database.audit_logs.insert_one({
        "_id": key, "event_key": key, "actor_id": ACTOR, "action": action,
        "entity_type": "alert", "entity_id": alert_id, "source_message_id": message_id,
        "occurred_at": now, "summary": summary, "request_id": None,
    }, session=session)


def open_alert(database, session, alert_type, scope_type, scope_id, bin_id, message_id, now):
    """Open an alert unless one is already active; return True if a new one was opened."""
    scope = {"scope_type": scope_type, "scope_id": scope_id, "type": alert_type, "active": True}
    if database.alerts.find_one_and_update(
        scope,
        {"$set": {"last_message_id": message_id, "updated_at": now}},
        session=session,
    ):
        return False
    alert_id = f"alr-{alert_type}-{message_id}"
    database.alerts.insert_one({
        "_id": alert_id, "scope_type": scope_type, "scope_id": scope_id, "bin_id": bin_id,
        "type": alert_type, "status": "open", "active": True, "severity": "warning",
        "opened_at": now, "acknowledged_at": None, "acknowledged_by": None,
        "resolved_at": None, "resolve_reason": None, "opened_message_id": message_id,
        "last_message_id": message_id, "updated_at": now,
    }, session=session)
    audit(database, session, f"alert_open:{alert_id}", "alert_open", alert_id, message_id,
          f"Mở cảnh báo {alert_type} cho {scope_id}", now)
    return True


def resolve_alert(database, session, alert_type, scope_type, scope_id, message_id, reason, now):
    alert = database.alerts.find_one_and_update(
        {"scope_type": scope_type, "scope_id": scope_id, "type": alert_type, "active": True},
        {"$set": {
            "status": "resolved", "active": False, "resolved_at": now,
            "resolve_reason": reason, "last_message_id": message_id, "updated_at": now,
        }},
        session=session,
    )
    if alert:
        audit(database, session, f"alert_resolve:{alert['_id']}", "alert_resolve", alert["_id"],
              message_id, f"Đóng cảnh báo {alert_type} cho {scope_id}: {reason}", now)


def apply(database, session, message_id, now):
    """Project one telemetry document. Returns the final processing state."""
    doc = database.telemetry.find_one({"_id": message_id}, session=session)
    if not doc or doc["processing"]["lease_owner"] != WORKER_ID:
        return None  # lease lost to another worker; it will finish the job

    def done(state, error=None):
        finish(database, message_id, state, now, error, session)
        return state

    if doc["mapping_status"] != "resolved":
        return done("ignored", f"mapping_status={doc['mapping_status']}")

    bin_id, device_id = doc["bin_id"], doc["device_id"]
    state = database.bin_state.find_one({"_id": bin_id}, session=session)
    if not state:
        return done("blocked", "bin_state missing")
    if state["assignment_id"] != doc["assignment_id"]:
        return done("ignored", "belongs to a previous assignment")

    if not database.device_configs.find_one(
        {"device_id": device_id, "config_rev": doc["config_rev"], "status": "verified"},
        session=session,
    ):
        return done("blocked", f"config_rev {doc['config_rev']} not verified")

    if (doc["boot_id"], doc["seq"]) <= (state["latest_boot_id"], state["latest_seq"]):
        return done("ignored", "older than current state")

    ok = doc["quality"] == "ok"
    update = {
        "latest_boot_id": doc["boot_id"], "latest_seq": doc["seq"],
        "latest_message_id": message_id, "latest_quality": doc["quality"],
        "latest_sampled_at": doc["sampled_at"], "latest_received_at": doc["received_at"],
        "last_contact_at": doc["received_at"], "updated_at": now,
    }
    if ok:
        update["last_good"] = {
            "message_id": message_id, "fill_pct": doc["fill_pct"],
            "distance_mm": doc["distance_mm"], "sampled_at": doc["sampled_at"],
            "received_at": doc["received_at"], "time_quality": doc["time_quality"],
        }
        if doc["alarm_active"] is not None:
            update["alarm_active"] = doc["alarm_active"]

    # Conditional on the tuple we read: a concurrent writer makes this a no-op/conflict.
    database.bin_state.update_one(
        {"_id": bin_id, "assignment_id": doc["assignment_id"],
         "latest_boot_id": state["latest_boot_id"], "latest_seq": state["latest_seq"]},
        {"$set": update},
        session=session,
    )

    if ok and doc["alarm_active"] is True:
        open_alert(database, session, "full", "bin", bin_id, bin_id, message_id, now)
    elif ok and doc["alarm_active"] is False:
        resolve_alert(database, session, "full", "bin", bin_id, message_id, "sensor_cleared", now)

    if ok:
        resolve_alert(database, session, "sensor_fault", "device", device_id, message_id,
                      "sensor_recovered", now)
    else:
        open_alert(database, session, "sensor_fault", "device", device_id, bin_id, message_id,
                   now)

    return done("applied")


def process_one(database=None):
    """Claim and project one document. Returns its final state, or None if idle."""
    if database is None:
        database = get_database()
    now = utcnow()
    doc = claim(database, now)
    if not doc:
        return None
    message_id = doc["_id"]
    try:
        with database.client.start_session() as session:
            state = session.with_transaction(
                lambda s: apply(database, s, message_id, now),
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
