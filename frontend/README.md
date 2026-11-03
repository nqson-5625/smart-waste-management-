# Smart Waste Management - Web Frontend

Ứng dụng web quản lý và giám sát hệ thống thùng rác thông minh (IoT) theo thời gian thực.

---

## 1. Công nghệ sử dụng
- **Giao diện & Thành phần:** React 18, HTML5, CSS thuần (tối ưu hiệu năng, không phụ thuộc UI framework nặng).
- **Công cụ đóng gói (Bundler):** Vite 6 (tốc độ khởi động miligiây, hot-reload tức thì).
- **Điều hướng (Routing):** `react-router-dom` v6 / v7.
- **Quản lý dữ liệu & Cache:** `@tanstack/react-query` v5 (tự động fetch, cache và polling 30 giây).
- **Bản đồ:** `leaflet` + `react-leaflet` (nền OpenStreetMap, ghim tọa độ và đổi màu trạng thái).
- **PWA (Progressive Web App):** `vite-plugin-pwa` (hỗ trợ cài đặt như app độc lập trên máy tính/điện thoại).

---

## 2. Hướng dẫn cài đặt & Khởi chạy

### Yêu cầu hệ thống
- Đã cài đặt **Node.js** (phiên bản 18 trở lên) và **npm**.

### Cài đặt thư viện
Mở terminal và di chuyển vào thư mục `frontend`:
```powershell
cd f:\smart-waste-management\frontend
npm install
```

---

### Cách 1: Chạy độc lập với Dữ liệu mẫu (Khuyến nghị khi phát triển UI & Báo cáo)
*Chế độ này sử dụng Mock Data bám sát 100% đặc tả API Backend v0.1, **không cần chạy Docker hay MongoDB**.*

1. Đảm bảo file `.env` trong thư mục `frontend` có cấu hình:
   ```env
   VITE_USE_MOCK=true
   VITE_API_BASE=/api/v1
   ```
2. Chạy lệnh:
   ```powershell
   npm run dev
   ```
   > **Lưu ý trên Windows:** Nếu gặp lỗi đỏ báo *`running scripts is disabled on this system`*, dùng lệnh:
   > ```powershell
   > npm.cmd run dev
   > ```
3. Mở trình duyệt và truy cập:
   👉 **http://localhost:5173**
4. **Đăng nhập:** Bạn có thể nhập bất kỳ email / mật khẩu nào (ví dụ: `admin@smartwaste.local` / `12345678`).

---

### Cách 2: Chạy kết nối với Backend thật (FastAPI & Docker)
*Khi muốn kiểm thử luồng thực tế với dữ liệu từ cơ sở dữ liệu MongoDB và cảm biến thật.*

1. **Khởi động Backend & Docker:**
   Mở terminal tại thư mục gốc `f:\smart-waste-management`:
   ```powershell
   docker compose up -d --build
   docker compose run --rm api python -m smartwaste_backend.scripts.seed_users
   docker compose run --rm api python -m smartwaste_backend.scripts.seed_demo 10
   ```
   *(Backend API lắng nghe tại cổng `http://localhost:8000`, tài liệu Swagger tại `http://localhost:8000/docs`)*.

2. **Chuyển Frontend sang kết nối Backend:**
   Mở file `frontend/.env` và đổi thành:
   ```env
   VITE_USE_MOCK=false
   ```
   Vite đã cấu hình proxy chuyển tiếp các request `/api` sang `http://localhost:8000` nên không bị lỗi CORS.

3. **Chạy Frontend:**
   ```powershell
   cd frontend
   npm run dev
   ```

4. **Tài khoản đăng nhập Backend thật:**
   - **Quản trị viên (Admin):** `admin@smartwaste.local`
   - **Điều phối viên (Dispatcher):** `dispatcher@smartwaste.local`
   - **Mật khẩu:** giá trị trong biến `DEMO_PASSWORD` ở file `.env` gốc (mặc định trong `.env.example`).

---

## 3. Bản đồ tổng quan các thùng rác (Map Overview) & Đổi màu theo mức đầy

### API có đáp ứng đủ không?
👉 **HOÀN TOÀN ĐẦY ĐỦ 100%!** 

Endpoint duy nhất cần dùng là `GET /api/v1/bins` (Backend tự động lấy danh sách thùng đang hoạt động `status=active`). Trong mỗi phần tử trả về đã có sẵn:
- **Tọa độ hiển thị:** Trường `lat` và `lng` được backend tính sẵn từ GeoJSON để đưa thẳng vào Leaflet.
- **Mức đầy rác:** `state.fill_pct` (giá trị phần trăm từ `0` đến `100`).
- **Cờ cảnh báo:** `state.alarm_active` (báo đầy) và `state.fresh` (dữ liệu mới trong 8 giờ qua).
- **Thông tin mô tả:** `code` (Mã thùng), `name` (Tên điểm đặt), `address` (Địa chỉ), `waste_type` (Loại rác).

### Quy tắc đổi màu Marker trên Bản đồ:
Dựa trên hàm chuẩn hóa trạng thái `binStatus`:

| Trạng thái | Điều kiện dữ liệu | Màu sắc Marker | Mã màu đề xuất |
|---|---|:---:|:---:|
| 🔴 **Đầy** | `alarm_active == true` hoặc `fill_pct >= 80%` | Đỏ | `#e53935` |
| 🟡 **Trung bình** | `20% <= fill_pct < 80%` | Vàng cam | `#fbc02d` |
| 🟢 **Rỗng** | `fill_pct < 20%` | Xanh lá | `#43a047` |
| ⚪ **Chưa có dữ liệu** | `fill_pct == null` hoặc `fresh == false` | Xám | `#9e9e9e` |

Khi người dùng bấm vào một Marker trên bản đồ, popup sẽ hiển thị:
- Tên & Mã thùng (`WB-001`, `Cổng B1`).
- Địa chỉ đặt thùng.
- Huy hiệu trạng thái và % đầy hiện tại.
- Liên kết điều hướng trực tiếp sang trang **Chi tiết thùng** (`/bins/:id`).

---

## 4. Các tính năng chính trên Web
1. **Trang Đăng nhập (`/login`):** Xác thực JWT, lưu phiên đăng nhập 8 giờ.
2. **Khôi phục phiên & Phân quyền (`GET /auth/me`):** Tự động nhận diện vai trò `admin` hoặc `dispatcher`. Ẩn các nút quản trị đối với `dispatcher`.
3. **Danh sách thùng rác (`/bins`):** Xem bảng danh sách, mức đầy %, cờ cảnh báo lỗi cảm biến, phân trang và tự động polling cập nhật mỗi 30 giây.
4. **Chi tiết thùng rác (`/bins/:id`):** 
   - Thông tin vị trí, thông số kỹ thuật.
   - Trạng thái thiết bị phần cứng gắn kèm.
   - Biểu đồ lịch sử đo Telemetry (24 giờ hoặc 7 ngày) tự động tải theo `cursor`.
   - Quy trình đăng ký và nạp hiệu chuẩn thiết bị (`POST /devices/{id}/configs`).
5. **Chuông cảnh báo (Header):** Đếm tổng số cảnh báo đang hoạt động (`status=open,acknowledged`), danh sách cảnh báo và nút "Đã xem" để xác nhận cảnh báo.
6. **Đổi mật khẩu cá nhân:** Modal đổi mật khẩu nhanh chóng ngay trên thanh điều hướng, xử lý lỗi chuẩn từ server.
7. **Thống kê loại rác (`/stats`):** Xem số lượng thùng và lượt thu gom theo từng loại rác theo khoảng thời gian tùy chọn.

---

## 5. Đóng gói ứng dụng (Build Production)
Để kiểm tra bản build chính thức hoặc triển khai:
```powershell
npm run build
```
Thư mục xuất kết quả: `dist/`. Chạy thử bản build:
```powershell
npm run preview
```
