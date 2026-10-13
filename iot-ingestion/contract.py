"""Schema and cross-field checks for telemetry ingestion."""

import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_DIR = Path(__file__).resolve().parent
SCHEMA_DIR = PROJECT_DIR / "schemas"
TELEMETRY_SCHEMA = json.loads(
    (SCHEMA_DIR / "telemetry.schema.json").read_text()
)
STATUS_SCHEMA = json.loads((SCHEMA_DIR / "status.schema.json").read_text())
TELEMETRY_VALIDATOR = Draft202012Validator(TELEMETRY_SCHEMA)
STATUS_VALIDATOR = Draft202012Validator(STATUS_SCHEMA)


def validate(topic, payload):
    """Validate the telemetry schema and relationships between its fields."""
    TELEMETRY_VALIDATOR.validate(payload)

    expected_topic = (
        f"smartwaste/v1/devices/{payload['device_id']}/telemetry"
    )
    if topic != expected_topic:
        raise ValueError("topic/device_id mismatch")

    expected_message_id = (
        f"{payload['device_id']}-{payload['boot_id']:08x}-{payload['seq']:08x}"
    )
    if payload["message_id"] != expected_message_id:
        raise ValueError("message_id/boot_id/seq mismatch")

    fill_percentage = payload["fill_pct"]
    if fill_percentage is not None:
        if (
            not math.isfinite(fill_percentage)
            or abs(fill_percentage * 10 - round(fill_percentage * 10)) > 1e-6
        ):
            raise ValueError("fill_pct must be finite with 0.1 percent resolution")

    if payload["time_quality"] == "gateway_estimated":
        expected_sample_time = (
            payload["gateway_received_at_ms"]
            - 1000 * payload["sample_age_at_rx_s"]
        )
        if payload["sampled_at_ms"] != expected_sample_time:
            raise ValueError("sample age/time mismatch")

    return payload


def validate_status(topic, payload):
    """Validate a gateway status payload and its MQTT topic."""
    STATUS_VALIDATOR.validate(payload)

    expected_topic = (
        f"smartwaste/v1/gateways/{payload['gateway_id']}/status"
    )
    if topic != expected_topic:
        raise ValueError("topic/gateway_id mismatch")

    return payload
