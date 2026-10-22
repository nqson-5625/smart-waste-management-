# Backend

FastAPI HTTP API đọc/ghi dữ liệu nghiệp vụ trong MongoDB schema v2. MQTT ingestion, payload validation, ghi telemetry, gateway status và ACK thuộc `iot-ingestion/` (nhóm Firmware & Kết nối IoT). Đặc tả endpoint: `docs/06_API_cho_Frontend.md`.

## Cấu hình

Đặt trong `.env` ở thư mục gốc (xem `.env.example`):

| Biến | Ý nghĩa |
|---|---|
| `MONGO_URI`, `MONGO_DB` | Mặc định `mongodb://localhost:27017/?directConnection=true`, `smartwaste_v2` |
| `JWT_SECRET` | Khóa ký token, chuỗi ngẫu nhiên dài; không commit giá trị thật |
| `DEMO_PASSWORD` | Mật khẩu cho tài khoản demo do `seed_users` tạo (tối thiểu 8 ký tự) |
| `CORS_ORIGINS` | Mặc định `http://localhost:5173` |

## Chạy bằng Docker (một lệnh)

```powershell
docker compose up -d --build        # MongoDB, Mosquitto, ingestion, api (cổng 8000), worker
docker compose run --rm api python -m smartwaste_backend.scripts.seed_users     # tài khoản demo, cần DEMO_PASSWORD
docker compose run --rm api python -m smartwaste_backend.scripts.seed_demo 10   # 10 thùng mô phỏng WB-101..WB-110
docker compose run --rm -e MOCK_DEVICE_NUMBER=90101 iot-ingestion python mock_publisher.py   # dữ liệu cho WB-101
docker compose logs -f worker
```

Web của Dũng (`npm run dev`) chuyển tiếp `/api` sang `localhost:8000`, nên dùng được ngay với API trong container.

## Chạy trên máy phát triển (Windows PowerShell)

```powershell
docker compose up -d --build                      # MongoDB, Mosquitto, ingestion
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# nạp .env vào biến môi trường của terminal hiện tại
Get-Content ..\.env | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
.\.venv\Scripts\python.exe -m smartwaste_backend.scripts.seed_users   # tạo admin/dispatcher/collector một lần
.\.venv\Scripts\python.exe -m smartwaste_backend.jobs.projection_worker   # worker (terminal riêng)
.\.venv\Scripts\python.exe -m uvicorn smartwaste_backend.app:app --port 8000 --reload
```

Tài khoản demo: `admin@smartwaste.local`, `dispatcher@smartwaste.local`, `collector@smartwaste.local`, mật khẩu là `DEMO_PASSWORD`. Tài liệu API tự sinh: http://localhost:8000/docs.

## Kiểm thử

Test chạy trên database riêng `smartwaste_test`, tạo schema một lần:

```powershell
docker compose run --rm -e SW_DB=smartwaste_test db-schema
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

## Cấu trúc

```
smartwaste_backend/
├── app.py        điểm vào: tạo FastAPI, định dạng lỗi, X-Request-ID, CORS, GET /health
├── core/         hạ tầng dùng chung, không chứa nghiệp vụ
├── api/          <tính năng>_router.py: router HTTP mỏng, mỗi file một nhóm endpoint
├── services/     <tính năng>_service.py: quy tắc nghiệp vụ và truy vấn MongoDB; không có code HTTP
├── jobs/         <tên>_worker.py: tiến trình chạy nền
└── scripts/      seed_<dữ liệu>.py: script chạy tay
```

**Quy tắc đặt tên:** `<tính năng>_<vai trò>.py`, để không có hai file trùng tên ở hai thư mục. Ví dụ tính năng `devices` gồm `api/devices_router.py` và `services/devices_service.py`; test tương ứng là `tests/test_devices_api.py`. `__init__.py` là tên bắt buộc của Python để thư mục được nhận là package, mỗi file chỉ chứa một dòng mô tả.

**Quy tắc khi thêm tính năng mới:** router chỉ khai báo endpoint, kiểu tham số và quyền rồi gọi service; mọi truy vấn MongoDB và quy tắc nghiệp vụ nằm trong service. Logic dùng chung giữa nhiều service (ví dụ đưa telemetry `blocked` về `pending`) đặt ở một hàm service riêng, không chép lại.

| File | Nội dung |
|---|---|
| `core/db.py` | Kết nối MongoDB (`MONGO_URI`, `MONGO_DB`) và helper đọc nhanh |
| `core/errors.py` | `ApiError`, mã lỗi chuẩn |
| `core/security.py` | Băm mật khẩu bcrypt, JWT HS256 sống 8 giờ, `current_user`, `require_roles` |
| `core/common.py` | Thời gian ISO, cursor phân trang, tính `fresh` |
| `api/auth_router.py` + `services/auth_service.py` | `POST /auth/login`, `GET /auth/me` |
| `api/bins_router.py` + `services/bins_service.py` | `GET /bins`, `/bins/{id}`, `/bins/{id}/telemetry` |
| `api/alerts_router.py` + `services/alerts_service.py` | `GET /alerts`, `POST /alerts/{id}/ack` |
| `services/telemetry_service.py` | Truy vấn lịch sử đo theo `(bin_id, sampled_at, _id)` |
| `services/projection_service.py` | Quy tắc tính `bin_state` và mở/đóng cảnh báo từ một bản telemetry |
| `jobs/projection_worker.py` | Vòng lặp: nhận bản `pending` có lease, gọi `projection_service.apply` trong transaction, thử lại khi lỗi |
| `scripts/seed_users.py` | Tạo tài khoản demo |
| `scripts/seed_demo.py` | Thùng `field` mô phỏng kèm thiết bị, gắn thiết bị và hiệu chuẩn `verified` |
