"""Devices: register, declare calibration, attach to a bin.

Rules follow docs/05 section 5.1: attaching runs in one transaction that closes the
previous assignment, bumps bins.assignment_version, opens the new assignment, resets
bin_state and closes alerts tied to the old device. Unique indexes on active
assignments stop two concurrent requests from attaching the same device or bin.
"""

from datetime import timedelta

from pymongo.errors import DuplicateKeyError

from ..core.common import iso, naive_utc, utcnow
from ..core.db import get_database, run_transaction
from ..core.errors import ApiError
from . import audit_service
from .projection_service import requeue_blocked


FULL_THRESHOLD_PCT, CLEAR_THRESHOLD_PCT, CONFIRM_CYCLES = 80, 70, 2  # fixed in firmware v1


def device_view(doc):
    return {
        "id": doc["_id"], "hardware_model": doc["hardware_model"],
        "serial_number": doc["serial_number"], "firmware_version": doc["firmware_version"],
        "gateway_ids": doc["gateway_ids"], "enabled": doc["enabled"],
        "lifecycle": doc["lifecycle"], "applied_config_rev": doc["applied_config_rev"],
        "sensors": doc["sensors"], "commissioned_at": iso(doc["commissioned_at"]),
        "notes": doc["notes"],
    }


def config_view(doc, requeued):
    return {
        "id": doc["_id"], "device_id": doc["device_id"], "config_rev": doc["config_rev"],
        "sensor_id": doc["sensor_id"], "empty_distance_mm": doc["empty_distance_mm"],
        "full_distance_mm": doc["full_distance_mm"], "sample_interval_s": doc["sample_interval_s"],
        "report_interval_s": doc["report_interval_s"],
        "full_threshold_pct": doc["full_threshold_pct"],
        "clear_threshold_pct": doc["clear_threshold_pct"],
        "confirm_cycles": doc["confirm_cycles"], "status": doc["status"],
        "verified_at": iso(doc["verified_at"]), "note": doc["note"],
        "requeued_messages": requeued,
    }


def create_device(body, user, request_id):
    """Register a device in stock; its gateways must already exist."""
    database = get_database()
    known = {g["_id"] for g in database.gateways.find({"_id": {"$in": body.gateway_ids}},
                                                       {"_id": 1})}
    unknown = [gateway for gateway in body.gateway_ids if gateway not in known]
    if unknown:
        raise ApiError(422, f"Gateway chưa được đăng ký: {', '.join(unknown)}",
                       {"field": "gateway_ids", "unknown": unknown})

    now = utcnow()
    doc = {
        "_id": body.id, "hardware_model": body.hardware_model,
        "serial_number": body.serial_number, "firmware_version": body.firmware_version,
        "gateway_ids": body.gateway_ids, "enabled": True, "lifecycle": "stock",
        "applied_config_rev": None,
        "sensors": [{**sensor.model_dump(), "status": "active"} for sensor in body.sensors],
        "commissioned_at": now, "notes": body.notes, "created_at": now, "updated_at": now,
    }
    try:
        database.devices.insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(409, "Mã thiết bị hoặc số serial đã tồn tại", {"device_id": body.id})
    audit_service.record(database, actor_id=user["_id"], action="device_create",
                         entity_type="device", entity_id=body.id,
                         summary=f"Đăng ký thiết bị {body.id}", request_id=request_id)
    return device_view(doc)


def create_config(device_id, body, user, request_id):
    """Declare the calibration flashed on the node as verified and make it current.

    Telemetry that was blocked waiting for this revision is requeued in the same
    transaction, so the worker picks it up straight away.
    """
    def work(database, session):
        device = database.devices.find_one({"_id": device_id}, session=session)
        if not device:
            raise ApiError(404, "Không tìm thấy thiết bị", {"device_id": device_id})
        sensor = next((s for s in device["sensors"]
                       if s["type"] == "ultrasonic" and s["status"] != "removed"), None)
        if not sensor:
            raise ApiError(422, "Thiết bị chưa có cảm biến siêu âm đang hoạt động",
                           {"device_id": device_id})
        if database.device_configs.find_one(
                {"device_id": device_id, "config_rev": body.config_rev}, session=session):
            raise ApiError(409, "Revision hiệu chuẩn đã tồn tại; tạo revision mới để thay đổi",
                           {"config_rev": body.config_rev})

        now = utcnow()
        doc = {
            "_id": f"{device_id}:{body.config_rev}", "device_id": device_id,
            "config_rev": body.config_rev, "sensor_id": sensor["sensor_id"],
            "empty_distance_mm": body.empty_distance_mm, "full_distance_mm": body.full_distance_mm,
            "sample_interval_s": body.sample_interval_s, "report_interval_s": body.report_interval_s,
            "full_threshold_pct": FULL_THRESHOLD_PCT, "clear_threshold_pct": CLEAR_THRESHOLD_PCT,
            "confirm_cycles": CONFIRM_CYCLES, "status": "verified", "verified_at": now,
            "created_by": user["_id"], "created_at": now, "note": body.note,
        }
        database.device_configs.insert_one(doc, session=session)
        database.devices.update_one(
            {"_id": device_id},
            {"$set": {"applied_config_rev": body.config_rev, "updated_at": now}},
            session=session,
        )
        requeued = requeue_blocked(database, session, device_id, body.config_rev, now)
        audit_service.record(database, actor_id=user["_id"], action="device_config_create",
                             entity_type="device", entity_id=device_id,
                             summary=f"Hiệu chuẩn rev {body.config_rev} cho {device_id}; "
                                     f"đưa lại {requeued} bản tin",
                             request_id=request_id, session=session)
        return config_view(doc, requeued)

    try:
        return run_transaction(work)
    except DuplicateKeyError:
        raise ApiError(409, "Revision hiệu chuẩn đã tồn tại", {"config_rev": body.config_rev})


def assign_device(bin_id, body, user, request_id):
    """Attach a device to a bin, replacing the bin's current device if any.

    Steps, all in one transaction: check -> detach the current device -> attach the
    new one -> reset the bin's projection -> audit.
    """
    device_id = body.device_id

    def work(database, session):
        now = utcnow()
        bin_doc = _check_assignable(database, session, bin_id, device_id)
        replaced, installed_at = _detach_current(database, session, bin_id, user, now)
        assignment = _attach(database, session, bin_doc, device_id, body.reason, user,
                             installed_at, now)
        _reset_bin_state(database, session, assignment, now)
        audit_service.record(
            database, actor_id=user["_id"], action="device_assign", entity_type="bin",
            entity_id=bin_id,
            summary=(f"Gắn {device_id} vào {bin_id}"
                     + (f", thay {replaced}" if replaced else "") + f": {body.reason}"),
            request_id=request_id, session=session,
        )
        return {
            "id": assignment["_id"], "bin_id": bin_id, "device_id": device_id,
            "assignment_version": assignment["assignment_version"],
            "installed_at": iso(installed_at), "reason": body.reason,
            "replaced_device_id": replaced,
        }

    try:
        return run_transaction(work)
    except DuplicateKeyError:
        raise ApiError(409, "Thiết bị hoặc thùng vừa được gắn bởi yêu cầu khác, hãy thử lại",
                       {"bin_id": bin_id, "device_id": device_id})


def _check_assignable(database, session, bin_id, device_id):
    """404/409 unless the bin is in use and the device is enabled and free. Returns the bin."""
    bin_doc = database.bins.find_one({"_id": bin_id}, session=session)
    if not bin_doc:
        raise ApiError(404, "Không tìm thấy thùng", {"bin_id": bin_id})
    if bin_doc["status"] == "retired":
        raise ApiError(409, "Thùng đã ngừng sử dụng", {"bin_id": bin_id})
    device = database.devices.find_one({"_id": device_id}, session=session)
    if not device:
        raise ApiError(404, "Không tìm thấy thiết bị", {"device_id": device_id})
    if not device["enabled"] or device["lifecycle"] == "retired":
        raise ApiError(409, "Thiết bị đã bị tắt hoặc ngừng sử dụng", {"device_id": device_id})
    busy = database.device_assignments.find_one({"device_id": device_id, "active": True},
                                                session=session)
    if busy:
        raise ApiError(409, f"Thiết bị đang gắn với thùng {busy['bin_id']}",
                       {"device_id": device_id, "bin_id": busy["bin_id"]})
    return bin_doc


def _detach_current(database, session, bin_id, user, now):
    """Close the bin's active assignment, if any.

    Returns (replaced device id or None, install time for the next assignment).
    """
    old = database.device_assignments.find_one({"bin_id": bin_id, "active": True},
                                               session=session)
    if not old:
        return None, now
    # Validator requires removed_at > installed_at, even within the same millisecond.
    removed_at = max(now, naive_utc(old["installed_at"]) + timedelta(milliseconds=1))
    database.device_assignments.update_one(
        {"_id": old["_id"], "active": True},
        {"$set": {"active": False, "removed_at": removed_at, "removed_by": user["_id"]}},
        session=session,
    )
    database.devices.update_one({"_id": old["device_id"]},
                                {"$set": {"lifecycle": "stock", "updated_at": now}},
                                session=session)
    # Alerts raised from the old device no longer describe the bin.
    database.alerts.update_many(
        {"bin_id": bin_id, "active": True},
        {"$set": {"status": "resolved", "active": False, "resolved_at": now,
                  "resolve_reason": "device_replaced", "updated_at": now}},
        session=session,
    )
    return old["device_id"], removed_at


def _attach(database, session, bin_doc, device_id, reason, user, installed_at, now):
    """Open a new assignment under the next assignment_version and install the device."""
    version = bin_doc["assignment_version"] + 1
    database.bins.update_one({"_id": bin_doc["_id"]},
                             {"$set": {"assignment_version": version, "updated_at": now}},
                             session=session)
    assignment = {
        "_id": f"asgn-{bin_doc['_id']}-v{version}", "device_id": device_id,
        "bin_id": bin_doc["_id"], "assignment_version": version, "active": True,
        "installed_at": installed_at, "removed_at": None, "installed_by": user["_id"],
        "removed_by": None, "reason": reason, "created_at": now,
    }
    database.device_assignments.insert_one(assignment, session=session)
    database.devices.update_one({"_id": device_id},
                                {"$set": {"lifecycle": "installed", "updated_at": now}},
                                session=session)
    return assignment


def _reset_bin_state(database, session, assignment, now):
    """Start the bin's projection from scratch so old samples never leak into the new device."""
    database.bin_state.replace_one({"_id": assignment["bin_id"]}, {
        "device_id": assignment["device_id"], "assignment_id": assignment["_id"],
        "assignment_version": assignment["assignment_version"], "latest_boot_id": 0,
        "latest_seq": 0, "latest_message_id": None, "latest_quality": "unknown",
        "latest_sampled_at": None, "latest_received_at": None, "last_contact_at": None,
        "last_good": None, "alarm_active": None, "updated_at": now,
    }, upsert=True, session=session)
