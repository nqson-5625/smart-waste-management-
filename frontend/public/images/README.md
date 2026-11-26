# Quản lý hình ảnh trên Mobile PWA

Ứng dụng đã được cấu hình tương thích linh hoạt giữa **Ảnh Backend** và **Ảnh Nội bộ (Frontend)**:

### 1. Khi Backend có Endpoint trả ảnh (Trong tương lai):
Component `ImagePlaceholder` đã tích hợp sẵn hàm `getBackendImageUrl()`. Backend chỉ cần trả về một trong các trường sau trong đối tượng Thùng rác (`Bin`) hoặc Xe gom rác (`Truck`):
- `image_url` (ví dụ: `https://api.domain.com/uploads/bins/wb-001.jpg`)
- `photo_url`
- `thumbnail_url`
- `image`

Ứng dụng sẽ **tự động ưu tiên hiển thị ảnh từ Backend**. Nếu ảnh từ backend bị lỗi (404/mất mạng), hệ thống sẽ tự động chuyển sang ảnh dự phòng local bên dưới mà không làm crash ứng dụng.

---

### 2. Khi Backend chưa có ảnh (Hiện tại):
Hệ thống sử dụng các file ảnh tĩnh đặt trong thư mục này (`frontend/public/images/`):
- **`smart-bin-hero.jpg`**: Ảnh thùng rác tại màn hình Đăng nhập.
- **`truck-route.png`**: Ảnh xe gom rác ở Card 1 (Trang chủ) và Bottom Sheet xe rác.
- **`smart-bin-preview.png`**: Ảnh thùng rác ở Card 2 (Trang chủ).
- **`bin-spot-thumb.jpg`**: Ảnh thumbnail điểm đặt thùng ở Bottom Sheet bản đồ.
- **`bin-spot-large.jpg`**: Ảnh lớn góc rộng ở màn hình Chi tiết thùng.

*Nếu chưa có các file ảnh trên, hệ thống sẽ tự động hiển thị khung Placeholder vector giữ chỗ đẹp mắt và đồng bộ.*
