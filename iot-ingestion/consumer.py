"""Validate MQTT messages and persist schema-v2 documents in MongoDB."""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from contract import validate, validate_status
from mqtt_client import connect, make_client


TELEMETRY_TOPIC = "smartwaste/v1/devices/+/telemetry"
STATUS_TOPIC = "smartwaste/v1/gateways/+/status"
DATABASE_SCHEMA_VERSION = 2
ASSIGNMENT_BOUNDARY_WINDOW = timedelta(seconds=120)
GATEWAY_FRESHNESS_WINDOW = timedelta(seconds=150)
REJECTION_RETENTION = timedelta(days=30)
TRANSPORT_FIELDS = {
    "gateway_id",
    "gateway_fw",
    "rssi_dbm",
    "snr_db",
    "gateway_boot_id",
    "gateway_rx_uptime_ms",
    "gateway_received_at_ms",
    "sampled_at_ms",
    "time_quality",
    "sample_age_at_rx_s",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

mongo = MongoClient(
    os.environ.get(
        "MONGO_URI",
        "mongodb://localhost:27017/?directConnection=true",
    ),
    serverSelectionTimeoutMS=5000,
    tz_aware=True,
)
database = mongo.get_database(
    os.environ.get("MONGO_DB", "smartwaste_v2"),
    write_concern=WriteConcern(w="majority", j=True),
)
majority_telemetry = database.telemetry.with_options(
    read_concern=ReadConcern("majority")
)
mongo.admin.command("ping")

if not database.schema_migrations.find_one({"_id": "schema-v2_0_0"}):
    raise RuntimeError("MongoDB schema v2 is missing; run mql/01_schema.js first")

mqtt_client = make_client(
    os.environ.get("MQTT_CLIENT_ID", "smartwaste-ingestor")
)


def utc_now():
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def epoch_ms_to_datetime(value):
    """Convert epoch milliseconds to a BSON-compatible UTC datetime."""
    if value is None:
        return None
    try:
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            milliseconds=value
        )
    except OverflowError as error:
        raise ValueError("epoch milliseconds are outside BSON Date range") from error


def parse_json_payload(raw_payload):
    """Decode strict JSON and reject non-standard NaN/Infinity values."""
    def reject_non_finite(value):
        raise ValueError(f"non-finite JSON number is not allowed: {value}")

    return json.loads(raw_payload, parse_constant=reject_non_finite)


def node_content_hash(payload):
    """Hash the immutable node fields using the documented v1 algorithm."""
    core_payload = {
        key: value
        for key, value in payload.items()
        if key not in TRANSPORT_FIELDS
    }
    if core_payload["fill_pct"] is not None:
        core_payload["fill_pct"] = round(core_payload["fill_pct"] * 10)

    encoded = json.dumps(
        core_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_assignment(device_id, sampled_at):
    """Resolve the bin assignment while protecting replacement boundaries."""
    if sampled_at is None:
        return None, None, "ambiguous_time"

    boundary_start = sampled_at - ASSIGNMENT_BOUNDARY_WINDOW
    boundary_end = sampled_at + ASSIGNMENT_BOUNDARY_WINDOW
    boundary = database.device_assignments.find_one(
        {
            "device_id": device_id,
            "$or": [
                {"installed_at": {"$gte": boundary_start, "$lte": boundary_end}},
                {"removed_at": {"$gte": boundary_start, "$lte": boundary_end}},
            ],
        },
        {"_id": 1},
    )
    if boundary:
        return None, None, "ambiguous_time"

    assignments = list(
        database.device_assignments.find(
            {
                "device_id": device_id,
                "installed_at": {"$lte": sampled_at},
                "$or": [
                    {"removed_at": None},
                    {"removed_at": {"$gt": sampled_at}},
                ],
            },
            {"_id": 1, "bin_id": 1},
        ).limit(2)
    )
    if len(assignments) == 1:
        assignment = assignments[0]
        return assignment["bin_id"], assignment["_id"], "resolved"
    if not assignments:
        return None, None, "unassigned"
    return None, None, "ambiguous_time"


def record_rejection(topic, raw_payload, reason):
    """Upsert a bounded rejection record without masking the ingest error."""
    now = utc_now()
    rejection_id = hashlib.sha256(
        topic.encode("utf-8") + b"\0" + raw_payload
    ).hexdigest()
    preview = raw_payload.decode("utf-8", errors="replace")[:2048]

    try:
        database.ingest_rejections.update_one(
            {"_id": rejection_id},
            {
                "$setOnInsert": {
                    "topic": topic[:200],
                    "payload_preview": preview or "<empty>",
                    "reason": str(reason)[:500] or "unknown rejection",
                    "first_seen_at": now,
                },
                "$set": {
                    "last_seen_at": now,
                    "expires_at": now + REJECTION_RETENTION,
                },
                "$inc": {"seen_count": 1},
            },
            upsert=True,
        )
    except Exception:
        logging.exception("Failed to persist ingest rejection")


def require_registered_route(payload):
    """Verify the provisioned device, gateway, and device-gateway allowlist."""
    device = database.devices.find_one(
        {"_id": payload["device_id"], "enabled": True},
        {"gateway_ids": 1},
    )
    gateway = database.gateways.find_one(
        {"_id": payload["gateway_id"], "enabled": True},
        {"_id": 1},
    )
    if not device or not gateway:
        raise ValueError("device or gateway is not provisioned and enabled")
    if payload["gateway_id"] not in device["gateway_ids"]:
        raise ValueError("gateway is not allowed for this device")


def build_telemetry_document(payload):
    """Add schema-v2 metadata to a validated wire payload."""
    now = utc_now()
    sampled_at = epoch_ms_to_datetime(payload["sampled_at_ms"])
    gateway_received_at = epoch_ms_to_datetime(
        payload["gateway_received_at_ms"]
    )
    bin_id, assignment_id, mapping_status = resolve_assignment(
        payload["device_id"],
        sampled_at,
    )

    return {
        "_id": payload["message_id"],
        **payload,
        "db_schema_version": DATABASE_SCHEMA_VERSION,
        "bin_id": bin_id,
        "assignment_id": assignment_id,
        "mapping_status": mapping_status,
        "sampled_at": sampled_at,
        "gateway_received_at": gateway_received_at,
        "received_at": now,
        "content_hash": node_content_hash(payload),
        "processing": {
            "state": "pending",
            "attempts": 0,
            "lease_owner": None,
            "lease_until": None,
            "next_retry_at": now,
            "processed_at": None,
            "last_error": None,
        },
    }


def store_telemetry(document):
    """Insert telemetry once and return stored or duplicate."""
    try:
        result = database.telemetry.update_one(
            {"_id": document["_id"]},
            {"$setOnInsert": document},
            upsert=True,
        )
    except DuplicateKeyError:
        result = None

    if result is not None and result.upserted_id is not None:
        return "stored"

    existing = majority_telemetry.find_one(
        {"_id": document["_id"]},
        {"content_hash": 1},
    )
    if existing and existing.get("content_hash") == document["content_hash"]:
        return "duplicate"

    raise ValueError("message_id or source tuple conflicts with stored content")


def handle_telemetry(message):
    """Validate, persist, and acknowledge one telemetry message."""
    if message.retain:
        raise ValueError("retained telemetry is not accepted")
    if len(message.payload) > 1200:
        raise ValueError("telemetry payload exceeds 1200 bytes")

    payload = validate(message.topic, parse_json_payload(message.payload))
    require_registered_route(payload)
    document = build_telemetry_document(payload)
    status = store_telemetry(document)

    acknowledgement = {
        "schema_version": 1,
        "message_id": payload["message_id"],
        "status": status,
    }
    acknowledgement_topic = (
        f"smartwaste/v1/gateways/{payload['gateway_id']}/ack"
    )
    publish_info = mqtt_client.publish(
        acknowledgement_topic,
        json.dumps(acknowledgement, separators=(",", ":")),
        qos=1,
        retain=False,
    )
    logging.info(
        "%s %s mapping=%s publish_rc=%s",
        status,
        payload["message_id"],
        document["mapping_status"],
        publish_info.rc,
    )


def handle_gateway_status(message):
    """Persist a validated gateway heartbeat or offline status."""
    if len(message.payload) > 1200:
        raise ValueError("gateway status payload exceeds 1200 bytes")

    payload = validate_status(
        message.topic,
        parse_json_payload(message.payload),
    )
    gateway = database.gateways.find_one(
        {"_id": payload["gateway_id"], "enabled": True},
        {"boot_id": 1, "status_reported_at": 1},
    )
    if not gateway:
        raise ValueError("gateway is not provisioned and enabled")

    now = utc_now()
    if payload["state"] == "offline":
        database.gateways.update_one(
            {"_id": payload["gateway_id"], "enabled": True},
            {"$set": {"status": "offline", "updated_at": now}},
        )
        return

    reported_at = epoch_ms_to_datetime(payload["reported_at_ms"])
    if message.retain and reported_at is None:
        raise ValueError("retained online status requires reported_at_ms")
    if reported_at and abs(now - reported_at) > GATEWAY_FRESHNESS_WINDOW:
        raise ValueError("stale retained gateway status")

    known_boot_id = gateway.get("boot_id")
    if known_boot_id is not None and payload["gateway_boot_id"] < known_boot_id:
        raise ValueError("gateway status belongs to an older boot")
    if (
        known_boot_id == payload["gateway_boot_id"]
        and reported_at is not None
        and gateway.get("status_reported_at") is not None
        and reported_at <= gateway["status_reported_at"]
    ):
        return

    database.gateways.update_one(
        {"_id": payload["gateway_id"], "enabled": True},
        {
            "$set": {
                "firmware_version": payload["gateway_fw"],
                "status": "online",
                "status_reported_at": reported_at,
                "last_received_at": now,
                "boot_id": payload["gateway_boot_id"],
                "queue_depth": payload["queue_depth"],
                "queue_capacity": payload["queue_capacity"],
                "invalid_packets": payload["invalid_packets"],
                "queue_full_events": payload["queue_full_events"],
                "storage_errors": payload["storage_errors"],
                "wifi_rssi_dbm": payload["wifi_rssi_dbm"],
                "updated_at": now,
            }
        },
    )


def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to all MQTT inputs owned by the ingestion service."""
    if reason_code.is_failure:
        logging.error("MQTT connection rejected: %s", reason_code)
        return

    client.subscribe([(TELEMETRY_TOPIC, 1), (STATUS_TOPIC, 1)])
    logging.info("Subscribed to telemetry and gateway status")


def on_message(client, userdata, message):
    """Route MQTT messages to the matching schema-v2 handler."""
    try:
        if message.topic.endswith("/telemetry"):
            handle_telemetry(message)
        elif message.topic.endswith("/status"):
            handle_gateway_status(message)
        else:
            raise ValueError("unsupported MQTT topic")
    except Exception as error:
        record_rejection(message.topic, message.payload, error)
        logging.exception("MQTT message rejected")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
connect(mqtt_client)
mqtt_client.loop_forever()
