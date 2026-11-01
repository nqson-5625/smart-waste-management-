"""Projection rules: how one telemetry document changes bin_state and alerts.

Rules follow docs/05 section 4.4: source order is (boot_id, seq); a bad-quality
sample never overwrites last_good; alarm_active changes only on quality=ok
non-null values; the full alert opens once per full episode and resolves when the
sensor confirms it cleared; sensor_fault follows sample quality.
"""

ACTOR = "system-worker"


def requeue_blocked(database, session, device_id, config_rev, now):
    """Put a device's blocked telemetry for ``config_rev`` back in the worker queue.

    Called once that calibration revision becomes verified. Returns how many
    messages were requeued.
    """
    result = database.telemetry.update_many(
        {"device_id": device_id, "config_rev": config_rev, "processing.state": "blocked"},
        {"$set": {
            "processing.state": "pending", "processing.attempts": 0,
            "processing.next_retry_at": now, "processing.lease_owner": None,
            "processing.lease_until": None, "processing.processed_at": None,
            "processing.last_error": None,
        }},
        session=session,
    )
    return result.modified_count


def finish(database, message_id, state, now, worker_id, error=None, session=None):
    """Record the outcome on the telemetry document and release the lease."""
    database.telemetry.update_one(
        {"_id": message_id, "processing.lease_owner": worker_id},
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


def apply(database, session, message_id, now, worker_id):
    """Project one leased telemetry document inside ``session``'s transaction.

    Returns the final processing state, or None if the lease was lost.
    """
    doc = database.telemetry.find_one({"_id": message_id}, session=session)
    if not doc or doc["processing"]["lease_owner"] != worker_id:
        return None  # lease lost to another worker; it will finish the job

    def done(state, error=None):
        finish(database, message_id, state, now, worker_id, error, session)
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
