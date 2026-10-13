"""Shared MQTT client configuration, with TLS enabled by default."""

import os
import ssl

import paho.mqtt.client as mqtt


def make_client(client_id):
    """Create an MQTT v3.1.1 client using environment-based credentials."""
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
    )

    username = os.environ.get("MQTT_USERNAME")
    if username:
        password = os.environ.get("MQTT_PASSWORD", "")
        client.username_pw_set(username, password)

    if os.environ.get("MQTT_TLS", "1") == "1":
        client.tls_set(
            ca_certs=os.environ.get("MQTT_CA_FILE") or None,
            cert_reqs=ssl.CERT_REQUIRED,
        )

    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


def connect(client):
    """Connect using host and port settings from the environment."""
    tls_enabled = os.environ.get("MQTT_TLS", "1") == "1"
    host = os.environ.get("MQTT_HOST", "localhost")
    default_port = "8883" if tls_enabled else "1883"
    port = int(os.environ.get("MQTT_PORT", default_port))

    client.connect(host, port, keepalive=30)
