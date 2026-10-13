# Backend

Backend đọc trực tiếp schema v2 từ MongoDB. MQTT ingestion, payload validation, ghi telemetry, gateway status và ACK thuộc `iot-ingestion/` (nhóm Firmware & Kết nối IoT). Các helper query nằm trong `backend/smartwaste_backend/`.

Cài dependency trong virtual environment:

```bash
python -m pip install -r backend/requirements.txt
```

Đặt `MONGO_URI` (mặc định `mongodb://localhost:27017/?directConnection=true`) và `MONGO_DB` (mặc định `smartwaste_v2`). Module `smartwaste_backend.telemetry` phân trang lịch sử theo `bin_id`, `sampled_at`, `_id` và yêu cầu khoảng thời gian. Module `smartwaste_backend.db` đọc `bins`, `bin_state` và `devices`.
