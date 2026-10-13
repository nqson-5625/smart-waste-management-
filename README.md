# Smart Waste Management

Dự án IoT quản lý thùng rác: ESP32-C3 node -> LoRa P2P -> gateway -> MQTT -> MongoDB. Firmware & Kết nối IoT phụ trách luồng MQTT đến khi telemetry được ghi thành công vào MongoDB và ACK được gửi về gateway. Backend query dữ liệu trực tiếp từ MongoDB.

## Cấu trúc

```text
firmware/          Arduino sketches cho node, gateway và sensor diagnostics
iot-ingestion/     MQTT consumer, validation, ghi MongoDB và ACK (nhóm Firmware & IoT)
backend/           Python helpers để query MongoDB (nhóm Backend)
infra/mosquitto/   Cấu hình MQTT broker cho môi trường phát triển local
docs/              Kiến trúc, wiring, contract và hướng dẫn
scripts/           Compile firmware
tests/             Kiểm tra logic/contract đã có
docker-compose.yml MongoDB 8 replica set, schema, seed registry, Mosquitto và IoT ingestion
```

## Chạy môi trường phát triển bằng Docker

Cần Docker Desktop hoặc Docker Engine kèm Docker Compose. Tạo `.env` từ `.env.example`, sau đó:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Compose khởi động MongoDB 8 dưới dạng replica set một node, chạy [schema v2](mql/01_schema.js), tạo đầy đủ quan hệ `bin/device/gateway/config/assignment/bin_state`, rồi chạy MQTT-to-MongoDB ingestion. Database mặc định là `smartwaste_v2`. Ingestion chỉ gửi ACK `stored`/`duplicate` sau khi document telemetry hợp lệ đã được lưu bền vững.

Để phát thử 9 bản tin mẫu từ simulator:

```powershell
docker compose run --rm iot-ingestion python mock_publisher.py
```

Broker Compose là cấu hình phát triển không TLS và không xác thực. Chỉ dùng trong mạng phát triển tin cậy; không đưa lên Internet hoặc dùng production. Gateway firmware cần cấu hình `USE_TLS=false`, địa chỉ IP LAN của máy chạy Docker, `MQTT_PORT=1883` và thông tin Wi-Fi trong `Secrets.h`. Không commit credential thật.

Schema DB và quy tắc ánh xạ chính thức nằm trong [thiết kế MongoDB](docs/05.Thiet_ke_MongoDB_SmartWaste.md). Xem thêm [contract dữ liệu](docs/03_Backend_contract.md), [hướng dẫn nạp firmware](docs/02_Dau_noi_va_Arduino_IDE.md) và [checklist tích hợp](docs/04_kiem_thu_tich_hop.md). Backend query MongoDB trực tiếp; `backend/` không có MQTT consumer hay ACK.

Dừng các dịch vụ bằng `docker compose down`. Dữ liệu MongoDB/Mosquitto được giữ trong named volumes; `docker compose down -v` sẽ xóa dữ liệu môi trường phát triển.
