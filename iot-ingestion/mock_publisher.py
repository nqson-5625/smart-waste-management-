"""Publish valid, duplicate, and out-of-order fixtures without an ESP32.

Each invocation uses a fresh boot ID based on the current second. Do not launch
two instances during the same second.
"""

import copy
import json
import os
import time
from pathlib import Path
from threading import Event

from contract import validate
from mqtt_client import connect, make_client


device_number = int(os.environ.get("MOCK_DEVICE_NUMBER", "900001"))
gateway_id = os.environ.get("MOCK_GATEWAY_ID", "gw-simulator")
device_id = f"bin-{device_number:03d}"
boot_id = int(time.time())
connected = Event()
mqtt_client = make_client(f"smartwaste-mock-{boot_id}")


def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to gateway ACK messages after connecting."""
    if not reason_code.is_failure:
        ack_topic = f"smartwaste/v1/gateways/{gateway_id}/ack"
        client.subscribe(ack_topic, qos=1)
        connected.set()


def on_message(client, userdata, message):
    """Print an application ACK received from the gateway."""
    payload = message.payload.decode(errors="replace")
    print("ACK", message.topic, payload, flush=True)


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
connect(mqtt_client)
mqtt_client.loop_start()

if not connected.wait(15):
    raise SystemExit("MQTT not connected; check TLS, broker, ACL, credentials")

fixture_path = Path(__file__).parent / "fixtures" / "scenarios.jsonl"
rows = [json.loads(line) for line in fixture_path.read_text().splitlines()]
current_time_ms = int(time.time() * 1000)

# Keep the replay in the past while preserving spacing and duplicate timestamps.
base_time_ms = rows[0]["payload"]["gateway_received_at_ms"]
time_shift_ms = current_time_ms - 7 * 60_000 - base_time_ms

try:
    for row in rows:
        payload = copy.deepcopy(row["payload"])
        payload.update(
            device_id=device_id,
            gateway_id=gateway_id,
            boot_id=boot_id,
            message_id=(
                f"{device_id}-{boot_id:08x}-{payload['seq']:08x}"
            ),
        )

        for field in ("gateway_received_at_ms", "sampled_at_ms"):
            if payload[field] is not None:
                payload[field] += time_shift_ms

        telemetry_topic = f"smartwaste/v1/devices/{device_id}/telemetry"
        validate(telemetry_topic, payload)

        # QoS 0 matches gateway publishing; the hardware gateway handles ACK loss.
        mqtt_client.publish(
            telemetry_topic,
            json.dumps(payload, separators=(",", ":")),
            qos=0,
            retain=False,
        ).wait_for_publish(5)
        print("SENT", payload["message_id"], payload["reason"], flush=True)
        time.sleep(1)

    time.sleep(3)
finally:
    mqtt_client.disconnect()
    mqtt_client.loop_stop()
