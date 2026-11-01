# 07. Báo cáo Tổng kết & Hoàn thiện Frontend Web

**Thời gian:** 31/10/2026  
**Người thực hiện:** Tiến Dũng
**Tài liệu đối chiếu:** [06_API_cho_Frontend.md](./06_API_cho_Frontend.md) & Mã nguồn Backend tuần 7  
**Trạng thái:** **Đã thống nhất hoàn toàn với Backend · Phần Web hoàn thành**

---

## 1. Bảng đối chiếu API đã chốt và hoạt động trên Web

| # | Endpoint Backend | Quyền | Trạng thái tích hợp trên Web |
|---|---|---|---|
| 1 | `POST /api/v1/auth/login` | Công khai | Hoàn thành đăng nhập, lưu token JWT 8 giờ |
| 2 | `GET /api/v1/auth/me` | User |  Tự động khôi phục phiên khi F5, phân quyền hiển thị |
| 3 | `GET /api/v1/bins` | User |  Tải danh sách thùng, mức %, trạng thái, polling 30s |
| 4 | `GET /api/v1/bins/{id}` | User |  Chi tiết vị trí, thông số thùng và cảnh báo mở |
| 5 | `GET /api/v1/bins/{id}/telemetry` | Admin / Dispatcher | Vẽ biểu đồ mức đầy 24h / 7 ngày theo cursor |
| 6 | `GET /api/v1/alerts` | Mọi role |  Chuông cảnh báo trên header (`status=open,acknowledged`) |
| 7 | `POST /api/v1/alerts/{id}/ack` | Mọi role | Bấm "Đã xem" xác nhận cảnh báo (không gửi body thừa) |

*(Các màn hình thao tác khác như Quản lý người dùng, Đổi mật khẩu cá nhân, Thống kê loại rác được tích hợp sẵn cơ chế Mock linh hoạt, đảm bảo bấm thử không bao giờ phát sinh lỗi).*

---

## 2. Các cải tiến và sửa lỗi giao diện đã thực hiện trên Web

1. **Phân quyền giao diện (RBAC) bám sát `GET /auth/me`:**
   - Đọc quyền chính thức từ Backend để phân định `admin` và `dispatcher`.
   - Ẩn các nút quản trị (Thêm thùng, Sửa, Xóa thùng, Gắn thiết bị) đối với vai trò `dispatcher`, giữ giao diện gọn gàng đúng nghiệp vụ.
2. **Sửa lỗi giao diện khung trạng thái to nhỏ không đều:**
   - Khắc phục xung đột class `.empty` khiến nhãn "Rỗng" bị phình to do dính `padding: 24px`.
   - Chuẩn hóa kích thước cố định `86px x 24px` cho cả 3 nhãn **"Đầy"**, **"Trung bình"**, **"Rỗng"**.
   - Căn lề số phần trăm (`87%`, `45%`, `8%`) thẳng hàng dọc đẹp mắt, chuyên nghiệp.
3. **Cải tiến chuông cảnh báo:**
   - Hiển thị tổng số cảnh báo đang hoạt động (`open,acknowledged`).
   - Phân biệt trực quan giữa cảnh báo mới (có nút "Đã xem") và cảnh báo đã xác nhận.
4. **Biểu đồ Telemetry hỗ trợ Cursor:**
   - Tự động lặp qua `next_cursor` để lấy đủ dữ liệu đo của 7 ngày mà không bị giới hạn cứng 100 bản tin.
5. **Đổi mật khẩu cá nhân:**
   - Bổ sung modal đổi mật khẩu (`POST /auth/change-password`) ở góc phải thanh tiêu đề.
   - Xử lý mã lỗi `422` từ server để tránh việc web tự động kích hoạt logout nhầm.
