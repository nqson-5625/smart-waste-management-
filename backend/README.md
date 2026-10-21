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

## Chạy trên máy phát triển (Windows PowerShell)

```powershell
docker compose up -d --build                      # MongoDB, Mosquitto, ingestion
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# nạp .env vào biến môi trường của terminal hiện tại
Get-Content ..\.env | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
.\.venv\Scripts\python.exe -m smartwaste_backend.seed_users   # tạo admin/dispatcher/collector một lần
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

| File | Nội dung |
|---|---|
| `smartwaste_backend/app.py` | Ứng dụng FastAPI, định dạng lỗi `{code,message,request_id,details}`, `X-Request-ID`, CORS, `GET /health` |
| `smartwaste_backend/auth.py` | Băm mật khẩu bcrypt, JWT HS256 sống 8 giờ, `POST /auth/login`, `GET /auth/me`, `require_roles` |
| `smartwaste_backend/errors.py` | `ApiError` |
| `smartwaste_backend/seed_users.py` | Tạo tài khoản demo |
| `smartwaste_backend/db.py`, `telemetry.py` | Helper truy vấn MongoDB |
