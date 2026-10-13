# IoT ingestion service

This service belongs to Firmware & IoT. It subscribes to telemetry and gateway status topics, validates wire payloads and provisioned relationships, writes schema-v2 documents to MongoDB, and publishes the application ACK only after telemetry storage succeeds. The gateway keeps retrying until that ACK arrives.

For the complete development stack, start from the repository root with `docker compose up -d --build`. Compose creates the `smartwaste_v2` schema before running `seed_registry.py`. To run the consumer outside Docker, install this directory's `requirements.txt`, run `mql/01_schema.js`, then set `MQTT_HOST`, `MQTT_PORT`, `MQTT_TLS`, `MONGO_URI`, and `MONGO_DB`. `mock_publisher.py` sends sample telemetry.

Backend reads `bins`, `bin_state`, `telemetry`, and registry collections directly. It does not use this service to query data and does not own MQTT ACK behavior.
