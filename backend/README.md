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
| `DEPOT_LAT`, `DEPOT_LNG` | Bãi tập kết của tuyến thu gom; mặc định `21.0047`, `105.8431` (cổng Parabol) |
| `ROUTE_SHIFT_TIMES` | Giờ lập tuyến tự động, giờ Việt Nam; mặc định `06:00,14:00` |
| `ROUTE_MAX_STOPS` | Số điểm tối đa một chuyến; mặc định `20` |
| `ROUTE_FORECAST` | Lập tuyến cả cho thùng dự báo sẽ tràn trước ca sau; mặc định `true` |

| `OSRM_URL` | Server tính đường bộ; Docker đặt sẵn `http://osrm:5000`. Để trống (mặc định khi chạy bằng venv) thì dùng đường chim bay. Chạy venv mà muốn đường bộ: `http://localhost:5000` |

Các biến tuyến đều có giá trị mặc định, không đặt cũng chạy được (docs/06 mục 3.12).

**Bản đồ đường bộ (OSRM).** Lần `docker compose up` đầu tiên, service `osrm-data` tải bản đồ Việt Nam (~330 MB), cắt riêng khung Hà Nội (`OSRM_BBOX`), rồi `osrm` dựng dữ liệu cho xe ô tô. Các lần sau dùng lại volume `osrm_data`, khởi động ngay. Trong lúc OSRM chưa sẵn sàng, tuyến vẫn lập được bằng đường chim bay (`distance_method = "straight"`). Đổi `OSRM_BBOX` thì phải xóa volume để dựng lại: `docker compose down; docker volume rm smartwastemanagement_osrm_data` (tên volume xem bằng `docker volume ls`).

Profile đường đi là **xe ép rác**: lấy profile ô tô của OSRM, đổi kích thước xe (cao 3,5 m, rộng 2,5 m, dài 8 m, nặng 12 tấn) và bỏ ngõ nhỏ, đường nội bộ (`highway=service`, `living_street`). Thùng trong ngõ được tính như xe đỗ ở đầu ngõ. Chưa tính giờ cấm xe tải nội thành.

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
.\.venv\Scripts\python.exe -m smartwaste_backend.scripts.seed_users   # tạo admin/collector một lần
.\.venv\Scripts\python.exe -m smartwaste_backend.jobs.projection_worker   # worker (terminal riêng)
.\.venv\Scripts\python.exe -m uvicorn smartwaste_backend.app:app --port 8000 --reload
```

Tài khoản demo: `admin@smartwaste.local` (web), `collector@smartwaste.local` (mobile), mật khẩu là `DEMO_PASSWORD`. Tài liệu API tự sinh: http://localhost:8000/docs.

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
├── schemas/      <tính năng>_schemas.py: kiểu dữ liệu vào/ra (Pydantic), hiện trên /docs
├── api/          <tính năng>_router.py: router HTTP mỏng, mỗi file một nhóm endpoint
├── services/     <tính năng>_service.py: quy tắc nghiệp vụ và truy vấn MongoDB; không có code HTTP
├── jobs/         <tên>_worker.py: tiến trình chạy nền
└── scripts/      seed_<dữ liệu>.py: script chạy tay
```

**Quy tắc đặt tên:** `<tính năng>_<vai trò>.py`, để không có hai file trùng tên ở hai thư mục. Ví dụ tính năng `devices` gồm `api/devices_router.py` và `services/devices_service.py`; test tương ứng là `tests/test_devices_api.py`. `__init__.py` là tên bắt buộc của Python để thư mục được nhận là package, mỗi file chỉ chứa một dòng mô tả.

**Quy tắc khi thêm tính năng mới:** router chỉ khai báo endpoint, kiểu tham số và quyền rồi gọi service; mọi truy vấn MongoDB và quy tắc nghiệp vụ nằm trong service. Logic dùng chung giữa nhiều service (ví dụ đưa telemetry `blocked` về `pending`) đặt ở một hàm service riêng, không chép lại.

| File | Nội dung |
|---|---|
| `core/config.py` | Đọc biến môi trường một lần (`MONGO_URI`, `MONGO_DB`, `JWT_SECRET`, `CORS_ORIGINS`, cấu hình tuyến) |
| `core/db.py` | Kết nối MongoDB, `run_transaction` (transaction majority, tự thử lại khi xung đột ghi), helper đọc nhanh |
| `core/errors.py` | `ApiError`, mã lỗi chuẩn |
| `core/security.py` | Băm mật khẩu bcrypt, JWT HS256 sống 8 giờ, `current_user`, `require_roles` |
| `core/common.py` | Thời gian ISO, cursor phân trang, tính `fresh` |
| `api/auth_router.py` + `services/auth_service.py` | `POST /auth/login`, `GET /auth/me`, `POST /auth/change-password` |
| `api/bins_router.py` + `services/bins_service.py` | `GET /bins`, `/bins/{id}`, `/bins/{id}/telemetry`, `POST /bins`, `PATCH /bins/{id}` |
| `api/bin_photos_router.py` + `services/bin_photos_service.py` | `PUT`/`GET`/`DELETE /bins/{id}/photo`: ảnh vị trí thùng, lưu trong GridFS bucket `bin_photos`; bin trả `photo_url` là link có chữ ký (HMAC bằng `JWT_SECRET`) mở được trong `<img src>` |
| `api/devices_router.py` + `services/devices_service.py` | `POST /devices`, `POST /devices/{id}/configs`, `POST /bins/{id}/assignments` |
| `api/alerts_router.py` + `services/alerts_service.py` | `GET /alerts`, `POST /alerts/{id}/ack` |
| `api/stats_router.py` + `services/stats_service.py` | `GET /stats/waste-by-type` |
| `api/users_router.py` + `services/users_service.py` | `POST /users`, `PATCH /users/{id}`, `GET /users` (admin quản lý tài khoản) |
| `api/collection_events_router.py` + `services/collection_events_service.py` | `POST /collection-events` (có `Idempotency-Key`), `GET /collection-events` |
| `api/routes_router.py` + `services/routes_service.py` | `POST /routes/generate`, `GET /routes`, `GET /routes/{id}/geometry`, `PATCH /routes/{id}/status`: chọn thùng, giao tuyến, chuyển trạng thái |
| `api/reports_router.py` | `GET /reports/routes`: km và số chuyến so với lịch cố định, theo ngày |
| `services/route_planner_service.py` | Thuật toán tuyến, không đụng database: sweep chia vùng, láng giềng gần nhất + 2-opt, cắt chuyến, baseline |
| `services/osrm_service.py` | Gọi OSRM: bảng khoảng cách đường bộ và đường đi theo phố; trả `None` khi OSRM không sẵn sàng để quay về đường chim bay |
| `services/audit_service.py` | Ghi `audit_logs` cho thao tác của người dùng (ai, làm gì, request nào) |
| `services/telemetry_service.py` | Truy vấn lịch sử đo theo `(bin_id, sampled_at, _id)` |
| `services/projection_service.py` | Quy tắc tính `bin_state` và mở/đóng cảnh báo từ một bản telemetry; `requeue_blocked` đưa bản tin bị chặn về hàng đợi khi có hiệu chuẩn |
| `jobs/projection_worker.py` | Vòng lặp: nhận bản `pending` có lease, gọi `projection_service.apply` trong transaction, thử lại khi lỗi; mỗi phút gọi `route_worker` |
| `jobs/route_worker.py` | Đầu mỗi ca lập và giao tuyến; chạy trong tiến trình worker nên không cần thêm container |
| `scripts/seed_users.py` | Tạo tài khoản demo |
| `scripts/seed_demo.py` | Thùng `field` mô phỏng kèm thiết bị, gắn thiết bị và hiệu chuẩn `verified` |
