# 06. Đặc tả REST API cho Frontend (bản đề xuất v0.1)

**Người viết:** Đỗ Thanh Sơn (Backend) · **Người đọc:** Dũng (Web/App) · **Trạng thái:** đề xuất để chốt, **chưa có server chạy**.

Phạm vi: 24 endpoint, lấy theo danh sách trong `smartwastew1.txt` của Dũng (web và mobile) cộng nhóm quản lý người dùng. Phủ các yêu cầu chức năng của đề bài: quản lý thùng, bản đồ, cảnh báo, thống kê theo loại, lập và giao tuyến, xác nhận thu gom, quản lý người dùng. Backend chỉ đọc/ghi dữ liệu nghiệp vụ; dữ liệu cảm biến vào MongoDB qua `iot-ingestion` (xem `03_Backend_contract.md`).

## 1. Quy ước chung

- Base URL dev: `http://localhost:8000/api/v1`. JSON UTF-8. CORS cho origin dev của frontend (Dũng cho biết port).
- Xác thực: `Authorization: Bearer <access_token>` cho mọi endpoint trừ `POST /auth/login` và `GET /health`.
- Vai trò: `admin`, `dispatcher` (điều phối), `collector` (thu gom). Backend lấy vai trò và user từ token, **không** tin `role`/`worker_id` trong body.
- Thời gian: ISO-8601 UTC có `Z` (`2026-10-16T08:00:00Z`); frontend tự đổi sang Asia/Ho_Chi_Minh khi hiển thị.
- Tọa độ: `location = {"type":"Point","coordinates":[lng, lat]}`. Mọi phản hồi có thùng kèm thêm `lat`, `lng` để dùng thẳng với Leaflet.
- Giá trị thiếu là `null`, không dùng 0 hay chuỗi rỗng. `fill_pct = null` nghĩa là chưa có số đo tốt, **không phải thùng rỗng**.
- Phân trang: `limit` (mặc định 50, tối đa 100) và `cursor` (chuỗi do server trả, không tự tạo). Phản hồi danh sách có dạng `{"items":[...],"next_cursor":"..."|null}`.
- Mã trạng thái: 200/201 thành công; 400/422 dữ liệu sai; 401 chưa đăng nhập; 403 thiếu quyền; 404 không tồn tại; 409 xung đột (trùng khóa, sai idempotency).
- Lỗi: `{"code":"VALIDATION","message":"...","request_id":"req-9f3a","details":{}}`. `code` thuộc: `VALIDATION`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`.
- Chỉ thêm trường mới, không đổi tên hay xóa trường đã chốt; thay đổi phải báo Dũng trước.

## 2. Danh sách endpoint

| #   | Method | Path                     | Quyền                                             | Ưu tiên |
| --- | ------ | ------------------------ | ------------------------------------------------- | ------- |
| 1   | GET    | `/health`                | công khai                                         | Cao     |
| 2   | POST   | `/auth/login`            | công khai                                         | Cao     |
| 3   | GET    | `/bins`                  | mọi user đã đăng nhập                             | Cao     |
| 4   | GET    | `/bins/{id}`             | mọi user đã đăng nhập                             | Cao     |
| 5   | GET    | `/bins/{id}/telemetry`   | admin, dispatcher                                 | Cao     |
| 6   | GET    | `/alerts`                | admin, dispatcher, collector                      | Cao     |
| 7   | POST   | `/bins`                  | admin                                             | Trung   |
| 8   | PATCH  | `/bins/{id}`             | admin                                             | Trung   |
| 9   | POST   | `/devices`               | admin                                             | Trung   |
| 10  | POST   | `/bins/{id}/assignments` | admin                                             | Trung   |
| 11  | POST   | `/collection-events`     | collector, admin                                  | Trung   |
| 12  | GET    | `/stats/waste-by-type`   | admin, dispatcher                                 | Trung   |
| 13  | POST   | `/routes/suggest`        | admin, dispatcher                                 | Thấp    |
| 14  | GET    | `/auth/me`               | mọi user đã đăng nhập                             | Cao     |
| 15  | POST   | `/alerts/{id}/ack`       | admin, dispatcher, collector                      | Cao     |
| 16  | POST   | `/users`                 | admin                                             | Trung   |
| 17  | PATCH  | `/users/{id}`            | admin                                             | Trung   |
| 18  | GET    | `/users`                 | admin                                             | Thấp    |
| 19  | POST   | `/auth/change-password`  | mọi user đã đăng nhập                             | Thấp    |
| 20  | POST   | `/devices/{id}/configs`  | admin                                             | Trung   |
| 21  | POST   | `/routes`                | admin, dispatcher                                 | Thấp    |
| 22  | GET    | `/routes`                | admin, dispatcher, collector (chỉ tuyến của mình) | Thấp    |
| 23  | PATCH  | `/routes/{id}/status`    | xem mục 3.14                                      | Thấp    |
| 24  | GET    | `/reports/routes`        | admin, dispatcher                                 | Thấp    |

Làm theo thứ tự ưu tiên: các endpoint "Cao" có trước để Dũng dựng UI.

## 3. Chi tiết

### 3.1 `POST /auth/login`

Body `{"email","password"}`. Trả `{"access_token","token_type":"bearer","expires_in":28800,"user":{"id","display_name","roles":["admin"]}}`. Tài khoản `pending`/`disabled` bị từ chối (401). Có giới hạn tần suất. Tài khoản demo do script seed của Backend tạo.
Chỉ một `access_token` sống 8 giờ (JWT, HS256), không có refresh token; hết hạn thì đăng nhập lại. Backend kiểm tra `status` của user ở mỗi request nên tài khoản bị khóa mất hiệu lực ngay.

### 3.1b `GET /auth/me`

Trả `{"id","display_name","roles":[...]}` của user trong token. Dùng để khôi phục phiên và quyết định ẩn/hiện nút theo vai trò. Backend vẫn tự kiểm tra quyền ở mọi endpoint, ẩn nút chỉ để giao diện gọn hơn.

### 3.1c `POST /auth/change-password`

Body `{"current_password","new_password"}` (mật khẩu mới tối thiểu 8 ký tự). Sai mật khẩu hiện tại trả 401 hoặc 422 (`details` ghi rõ trường). Thành công trả 200 `{"ok":true}`; token cũ vẫn dùng được cho tới khi hết hạn. User mới do admin tạo nên dùng endpoint này để đổi mật khẩu ban đầu.

### 3.2 `GET /bins`

Query: `ward_code`, `waste_type` (`general|organic|recyclable|hazardous|other`), `status` (`active|maintenance|retired`), `full` (true/false: có đang báo đầy), `fresh` (true/false), `limit`, `cursor`. Mặc định chỉ trả thùng `environment=field`.

```json
{
  "items": [
    {
      "id": "WB-001",
      "code": "WB-001",
      "name": "Cổng B1",
      "address": "Số 1 Đại Cồ Việt",
      "ward_code": "BK",
      "waste_type": "general",
      "capacity_l": 240,
      "status": "active",
      "location": { "type": "Point", "coordinates": [105.8442, 21.005] },
      "lat": 21.005,
      "lng": 105.8442,
      "state": {
        "device_id": "bin-001",
        "fill_pct": 86.5,
        "distance_mm": 130,
        "sampled_at": "2026-10-16T08:00:00Z",
        "latest_quality": "ok",
        "latest_sampled_at": "2026-10-16T08:00:00Z",
        "alarm_active": true,
        "last_contact_at": "2026-10-16T08:00:03Z",
        "fresh": true
      }
    }
  ],
  "next_cursor": null
}
```

- `fill_pct`, `distance_mm`, `sampled_at` lấy từ **lần đo tốt gần nhất**. `latest_quality` là chất lượng của bản tin mới nhất. Khi `latest_quality != "ok"` mà vẫn còn số cũ, hiển thị số cũ kèm biểu tượng lỗi cảm biến.
- `fresh` do Backend tính: lần đo tốt trong 8 giờ gần nhất, không ở tương lai, và thời gian đo đáng tin. Frontend không tự tính.
- `state` là `null` nếu thùng chưa gắn thiết bị hoặc chưa có dữ liệu.

### 3.3 `GET /bins/{id}`

Trả như một phần tử của `/bins`, thêm `notes`, `device` (`{id, lifecycle, enabled}` hoặc null) và `open_alerts` (danh sách cảnh báo đang mở của thùng). 404 nếu không tồn tại.

### 3.4 `GET /bins/{id}/telemetry`

Query bắt buộc `from`, `to` (ISO UTC, `from <= to`); tùy chọn `limit` (tối đa 100), `cursor`. Sắp xếp `sampled_at` giảm dần. Muốn lấy đủ một khoảng dài (ví dụ 7 ngày) thì gọi lặp với `cursor = next_cursor` của lần trước cho tới khi `next_cursor` là `null`. Phần tử:
`{"message_id","sampled_at","received_at","reason","quality","fill_pct","distance_mm","alarm_active","lid_open","rssi_dbm","snr_db","time_quality"}`. Bản tin chất lượng xấu có `fill_pct = null`. Bản tin chưa đồng bộ giờ có `sampled_at = null`, nên bị loại khỏi kết quả theo khoảng thời gian.

### 3.5 `GET /alerts`

Query: `status` (`open|acknowledged|resolved`, mặc định `open`; có thể truyền nhiều giá trị cách nhau dấu phẩy, ví dụ `open,acknowledged` cho chuông), `type` (`full|sensor_fault|device_stale|gateway_offline`), `scope_type` (`bin|device|gateway`), `bin_id`, `limit`, `cursor`. Phần tử:
`{"id","type","status","severity":"warning|critical","scope_type","scope_id","bin_id","opened_at","acknowledged_at","acknowledged_by","resolved_at","resolve_reason"}`.
Cảnh báo `full` tự đóng khi cảm biến báo hết đầy; thu gom **không** tự đóng cảnh báo. Một lần đầy chỉ tạo một cảnh báo dù tin được gửi lại nhiều lần.

### 3.5b `POST /alerts/{id}/ack`

Không cần body. Đặt `status = acknowledged`, ghi `acknowledged_by` (từ token) và `acknowledged_at`; cảnh báo vẫn đang hoạt động cho tới khi điều kiện hết. Trả cảnh báo sau khi cập nhật. Ack lại cảnh báo đã `acknowledged` thì trả 200 giữ nguyên; cảnh báo đã `resolved` thì trả 409; không tồn tại thì 404.

### 3.6 `POST /bins` (201)

Body: `code`, `name`, `address`, `ward_code`, `waste_type`, `location` (hoặc `lat`,`lng`), `capacity_l?`, `notes?`. Backend tự đặt `id`, `status=active`, `environment=field`. 409 nếu trùng `code`.

### 3.7 `PATCH /bins/{id}`

Sửa một phần: `name`, `address`, `ward_code`, `waste_type`, `location`, `capacity_l`, `status`, `notes`. Không sửa `id`, `code`, `environment`. Không xóa thùng.

### 3.8 `POST /devices` (201)

Body: `id` (dạng `bin-001`, 3 đến 6 chữ số), `hardware_model`, `firmware_version`, `gateway_ids[]`, `sensors[]` (`{sensor_id,type:"ultrasonic|lid_switch",model}`), `serial_number?`. 409 nếu trùng `id`. Không trả thông tin MQTT.

### 3.9 `POST /bins/{id}/assignments` (201)

Body: `device_id`, `reason`. Gắn hoặc thay thiết bị cho thùng trong một transaction: đóng gắn cũ, tăng `assignment_version`, reset hiện trạng thùng. 409 nếu thiết bị đang gắn thùng khác.

### 3.10 `POST /collection-events` (201)

Bắt buộc header `Idempotency-Key` (UUID do client sinh, dùng lại khi gửi lại). Body: `bin_id`, `completed_at`, `measured_weight_kg?` (null nếu không có cân), `weight_source?` (`scale|manual|unknown`), `fill_before_pct?`, `fill_after_pct?`, `note?`.

- Cùng key và cùng nội dung: trả lại bản ghi cũ (200). Cùng key, nội dung khác: 409.
- `completed_at` không được ở tương lai quá 5 phút.
- `worker_id` lấy từ token.
- Thu gom theo tuyến: gửi thêm `route_id` và `stop_order`. Tuyến phải `in_progress`, được giao cho chính user này, điểm dừng khớp `bin_id` và chưa thu gom; thành công thì điểm dừng chuyển `collected`. Thu gom ngoài tuyến: bỏ hai trường này (null).
- Thu gom **không** tự đặt `fill_pct` về 0 và không đóng cảnh báo; UI có thể hiển thị "đã thu gom, chờ cảm biến xác nhận".

### 3.11 `GET /stats/waste-by-type`

Query: `from`, `to` (bắt buộc). Trả `{"items":[...]}` (không phân trang), mỗi phần tử là một loại rác:
`{"waste_type","bin_count","collection_count","avg_fill_pct","known_weight_kg","known_weight_count","unknown_weight_count"}`.
Không có cân thì chỉ có số lượt thu gom; `known_weight_kg` chỉ cộng các lượt có cân. Không suy kg từ `fill_pct`.

### 3.12 `POST /routes/suggest`

Gợi ý thứ tự ghé các thùng cần thu gom (nearest neighbor, khoảng cách đường chim bay, **không** phải đường phố thật). Body:
`{"depot":{"lng":105.84,"lat":21.00},"min_fill_pct":80,"max_stops_per_trip":20}`
(`min_fill_pct` mặc định 80; chỉ lấy thùng `fresh` và active). Trả:

```json
{
  "stops": [
    {
      "order": 1,
      "bin_id": "WB-001",
      "lat": 21.005,
      "lng": 105.844,
      "fill_pct": 86.5
    }
  ],
  "planned_distance_m": 4200,
  "baseline_distance_m": 18600,
  "distance_reduction_pct": 77.4,
  "planned_trips": 1,
  "baseline_trips": 3
}
```

`baseline` là phương án đi hết mọi thùng active theo thứ tự cố định, cùng cách tính khoảng cách. Đây là phép so sánh mô phỏng để đo chỉ tiêu km và số chuyến giảm được; không phải quãng đường xe thực chạy.

### 3.13 Quản lý người dùng (chỉ admin)

Dùng để admin tạo tài khoản cho nhân viên thu gom và điều phối. Không bao giờ trả `password_hash`.

- `POST /users` (201): body `{"email","display_name","password","roles":["collector"],"phone?"}`. `roles` gồm 1 đến 3 giá trị trong `admin|dispatcher|collector`; mật khẩu tối thiểu 8 ký tự; tài khoản tạo xong ở trạng thái `active`. 409 nếu trùng email (không phân biệt hoa thường). Trả `{"id","email","display_name","roles","status","phone","created_at"}`.
- `PATCH /users/{id}`: sửa một phần `display_name`, `roles`, `status` (`active|disabled`), `phone`, và `password` (admin đặt lại mật khẩu khi người dùng quên). Admin không được tự khóa hoặc tự bỏ quyền admin của chính mình (409). Tài khoản `disabled` mất hiệu lực ngay ở request kế tiếp.
- `GET /users`: query `role`, `status`, `limit`, `cursor`; trả `{"items":[...],"next_cursor":...}` với phần tử như kết quả `POST /users`, thêm `last_login_at`.

### 3.14 Tuyến thu gom

- `POST /routes` (201, admin/dispatcher): body `{"service_date":"2026-10-20","assigned_worker_id":"<id collector>|null","depot":{"lng","lat"},"bin_ids":["WB-001","WB-007"]}`. `bin_ids` theo đúng thứ tự ghé (thường lấy từ kết quả `POST /routes/suggest`), 1 đến 200 thùng, không lặp. Backend chụp lại tọa độ và mức đầy từng thùng tại lúc lập tuyến, tính `planned_distance_m` và `baseline_distance_m` cùng cách với `/routes/suggest`. Có `assigned_worker_id` thì `status = assigned`, không thì `planned`.
- `GET /routes`: query `service_date`, `status`, `assigned_worker_id`, `limit`, `cursor`. Collector chỉ thấy tuyến được giao cho mình (Backend tự lọc). Phần tử: `{"id","service_date","status","assigned_worker_id","depot","stops":[{"stop_order","bin_id","lat","lng","planned_fill_pct","status":"pending|collected|skipped","completed_at","skip_reason"}],"planned_distance_m","baseline_distance_m","actual_distance_m","started_at","completed_at"}`.
- `PATCH /routes/{id}/status`: body `{"status", ...}`. Chuyển trạng thái hợp lệ:

| Từ → sang                              | Ai được làm         | Body thêm                                                                                         |
| -------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------- |
| `planned` → `assigned`                 | admin, dispatcher   | `assigned_worker_id`                                                                              |
| `assigned` → `in_progress`             | collector được giao |                                                                                                   |
| `in_progress` → `completed`            | collector được giao | `actual_distance_m?`, `actual_distance_source?` (`odometer`, `gps` hoặc `manual`), `skip_reason?` |
| bất kỳ trước `completed` → `cancelled` | admin, dispatcher   |                                                                                                   |

Khi `completed`, các điểm dừng còn `pending` chuyển `skipped` với `skip_reason` (bắt buộc nếu còn điểm `pending`). Chuyển sai trả 409.

### 3.15 `GET /reports/routes`

Query `from`, `to` (ngày `YYYY-MM-DD`, giờ Việt Nam). Trả `{"items":[...],"summary":{...}}`:

- Mỗi tuyến đã `completed`: `{"route_id","service_date","stop_count","collected_count","planned_distance_m","baseline_distance_m","actual_distance_m","planned_reduction_pct","actual_reduction_pct"}`.
- `summary`: tổng số tuyến và tổng ba loại quãng đường, cùng hai tỷ lệ giảm.

`planned_reduction_pct = (baseline - planned) / baseline × 100` là mức giảm theo mô phỏng. `actual_reduction_pct` chỉ có khi tuyến có `actual_distance_m`, nếu không là `null`. Không lấy planned thay cho actual.

### 3.16 `POST /devices/{id}/configs` (201)

Khai báo thông số hiệu chuẩn đang nạp trong firmware của thiết bị. Body `{"config_rev":1,"empty_distance_mm":1000,"full_distance_mm":200,"sample_interval_s":60,"report_interval_s":21600,"note?"}`; điều kiện `full_distance_mm < empty_distance_mm`. `config_rev` phải trùng giá trị đang nạp trên node. Tạo xong ở trạng thái đã xác minh và thành cấu hình đang dùng của thiết bị. 409 nếu revision đã tồn tại (revision cũ không sửa được, muốn đổi thì tạo revision mới).

**Thiết bị chưa có cấu hình thì dữ liệu đo vẫn được lưu nhưng không hiện lên thùng.** Vì vậy hộp thoại gắn thiết bị trên web nên đi theo thứ tự: `POST /devices` → `POST /devices/{id}/configs` → `POST /bins/{id}/assignments`.

## 4. Ghi chú về dữ liệu

- Hệ thống chỉ có 1 thùng gắn cảm biến thật; các thùng còn lại là dữ liệu mô phỏng. API không phân biệt hai loại này.
- Thùng thật có thể báo chất lượng xấu (mở nắp, mất echo). UI nên hiển thị `latest_quality` cùng `fill_pct`, không ẩn.

## 5. Không làm và thứ tự cắt

- WebSocket đẩy cập nhật: không làm, polling 30 giây là đủ.
- Quên mật khẩu qua email: không làm (admin đặt lại bằng `PATCH /users/{id}`).
- Nếu Backend trễ lịch, thứ tự cắt: `GET /reports/routes`, rồi nhóm `/routes`, rồi `change-password` và `GET /users`. Sẽ báo trước nếu phải cắt.

## 6. Chú ý!

Đã thống nhất: một `access_token` 8 giờ không refresh; polling `GET /bins` mỗi 30 giây; web chạy ở `http://localhost:5173` (CORS).

1. Tên trường trong ví dụ `GET /bins`, `GET /bins/{id}` (mục 3.2, 3.3) có khớp với code web hiện tại không?
2. Web cần thêm: màn hình quản lý người dùng (admin), đổi mật khẩu, và bước nhập hiệu chuẩn trong hộp thoại gắn thiết bị (mục 3.16).
