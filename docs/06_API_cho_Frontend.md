# 06. Đặc tả REST API cho Frontend (bản đề xuất v0.1)

**Người viết:** Đỗ Thanh Sơn (Backend) · **Người đọc:** Dũng (Web/App) · **Trạng thái:** đề xuất để chốt, **chưa có server chạy**.

Phạm vi: 27 endpoint, lấy theo danh sách trong `smartwastew1.txt` của Dũng (web và mobile) cộng nhóm quản lý người dùng và ảnh vị trí thùng (nhóm thêm 21/11). Phủ các yêu cầu chức năng của đề bài: quản lý thùng, bản đồ, cảnh báo, thống kê theo loại, lập và giao tuyến, xác nhận thu gom, quản lý người dùng. Backend chỉ đọc/ghi dữ liệu nghiệp vụ; dữ liệu cảm biến vào MongoDB qua `iot-ingestion` (xem `03_Backend_contract.md`).

## 1. Quy ước chung

- Base URL dev: `http://localhost:8000/api/v1`. JSON UTF-8. CORS cho origin dev của frontend (Dũng cho biết port).
- Xác thực: `Authorization: Bearer <access_token>` cho mọi endpoint trừ `POST /auth/login`, `GET /health` và link ảnh `photo_url` (link đã có chữ ký, mục 3.7b).
- Vai trò: `admin` (quản trị, gồm cả việc điều phối) và `collector` (thu gom). Nhóm đã bỏ vai trò `dispatcher` (19/11): mọi quyền điều phối thuộc về admin. Web dành cho admin, app mobile dành cho collector. Backend lấy vai trò và user từ token, **không** tin `role`/`worker_id` trong body.
- Thời gian: ISO-8601 UTC có `Z` (`2026-10-16T08:00:00Z`); frontend tự đổi sang Asia/Ho_Chi_Minh khi hiển thị.
- Tọa độ: `location = {"type":"Point","coordinates":[lng, lat]}`. Mọi phản hồi có thùng kèm thêm `lat`, `lng` để dùng thẳng với Leaflet.
- Giá trị thiếu là `null`, không dùng 0 hay chuỗi rỗng. `fill_pct = null` nghĩa là chưa có số đo tốt, **không phải thùng rỗng**.
- Phân trang: `limit` (mặc định 50, tối đa 100) và `cursor` (chuỗi do server trả, không tự tạo). Phản hồi danh sách có dạng `{"items":[...],"next_cursor":"..."|null}`.
- Mã trạng thái: 200/201 thành công; 400/422 dữ liệu sai; 401 chưa đăng nhập; 403 thiếu quyền; 404 không tồn tại; 409 xung đột (trùng khóa, sai idempotency); 413 file quá lớn.
- Lỗi: `{"code":"VALIDATION","message":"...","request_id":"req-9f3a","details":{}}`. `code` thuộc: `VALIDATION`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `TOO_LARGE`.
- Chỉ thêm trường mới, không đổi tên hay xóa trường đã chốt; thay đổi phải báo Dũng trước.

## 2. Danh sách endpoint

| #   | Method | Path                     | Quyền                                             | Ưu tiên |
| --- | ------ | ------------------------ | ------------------------------------------------- | ------- |
| 1   | GET    | `/health`                | công khai                                         | Cao     |
| 2   | POST   | `/auth/login`            | công khai                                         | Cao     |
| 3   | GET    | `/bins`                  | mọi user đã đăng nhập                             | Cao     |
| 4   | GET    | `/bins/{id}`             | mọi user đã đăng nhập                             | Cao     |
| 5   | GET    | `/bins/{id}/telemetry`   | admin                                             | Cao     |
| 6   | GET    | `/alerts`                | admin, collector                                  | Cao     |
| 7   | POST   | `/bins`                  | admin                                             | Trung   |
| 8   | PATCH  | `/bins/{id}`             | admin                                             | Trung   |
| 9   | POST   | `/devices`               | admin                                             | Trung   |
| 10  | POST   | `/bins/{id}/assignments` | admin                                             | Trung   |
| 11  | POST   | `/collection-events`     | collector, admin                                  | Trung   |
| 12  | GET    | `/stats/waste-by-type`   | admin, collector                                  | Trung   |
| 13  | POST   | `/routes/generate`       | admin                                             | Trung   |
| 14  | GET    | `/auth/me`               | mọi user đã đăng nhập                             | Cao     |
| 15  | POST   | `/alerts/{id}/ack`       | admin, collector                                  | Cao     |
| 16  | POST   | `/users`                 | admin                                             | Trung   |
| 17  | PATCH  | `/users/{id}`            | admin                                             | Trung   |
| 18  | GET    | `/users`                 | admin                                             | Trung   |
| 19  | POST   | `/auth/change-password`  | mọi user đã đăng nhập                             | Thấp    |
| 20  | POST   | `/devices/{id}/configs`  | admin                                             | Trung   |
| 22  | GET    | `/routes`                | admin, collector (chỉ tuyến của mình)             | Trung   |
| 23  | PATCH  | `/routes/{id}/status`    | xem mục 3.14                                      | Trung   |
| 24  | GET    | `/reports/routes`        | admin                                             | Trung   |
| 25  | GET    | `/collection-events`     | admin, collector (chỉ của mình)                   | Trung   |
| 26  | PUT    | `/bins/{id}/photo`       | admin                                             | Trung   |
| 27  | GET    | `/bins/{id}/photo`       | link có chữ ký trong `photo_url` (xem mục 3.7b)   | Trung   |
| 28  | DELETE | `/bins/{id}/photo`       | admin                                             | Trung   |

Làm theo thứ tự ưu tiên: các endpoint "Cao" có trước để Dũng dựng UI.

Ngày 22/11, theo đề xuất tuyến tuần 9 (phương án B, tuyến tự động theo ca): `POST /routes/suggest` (#13 cũ) và `POST /routes` (#21 cũ) được thay bằng một endpoint `POST /routes/generate`, vì tuyến do hệ thống tự lập và giao, admin không còn bước gợi ý rồi lưu tay. Tổng còn 27 endpoint.

## 3. Chi tiết

### 3.1 `POST /auth/login`

Body `{"email","password"}`. Trả `{"access_token","token_type":"bearer","expires_in":28800,"user":{"id","display_name","roles":["admin"]}}`. Tài khoản `pending`/`disabled` bị từ chối (401). Có giới hạn tần suất. Tài khoản demo do script seed của Backend tạo.
Chỉ một `access_token` sống 8 giờ (JWT, HS256), không có refresh token; hết hạn thì đăng nhập lại. Backend kiểm tra `status` của user ở mỗi request nên tài khoản bị khóa mất hiệu lực ngay.

### 3.1b `GET /auth/me`

Trả `{"id","display_name","roles":[...]}` của user trong token. Dùng để khôi phục phiên và quyết định ẩn/hiện nút theo vai trò. Backend vẫn tự kiểm tra quyền ở mọi endpoint, ẩn nút chỉ để giao diện gọn hơn.

### 3.1c `POST /auth/change-password`

Body `{"current_password","new_password"}` (mật khẩu mới tối thiểu 8 ký tự). Sai mật khẩu hiện tại trả **422** (`details.field = "current_password"`); không dùng 401 vì web coi mọi 401 là hết phiên và tự đăng xuất. Thành công trả 200 `{"ok":true}`; token cũ vẫn dùng được cho tới khi hết hạn. User mới do admin tạo nên dùng endpoint này để đổi mật khẩu ban đầu.

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
      "photo_url": "/api/v1/bins/WB-001/photo?v=6740c1e2a9&exp=1795000000&sig=3f9a…",
      "state": {
        "device_id": "bin-001",
        "fill_pct": 86.5,
        "distance_mm": 130,
        "sampled_at": "2026-10-16T08:00:00Z",
        "latest_quality": "ok",
        "latest_sampled_at": "2026-10-16T08:00:00Z",
        "alarm_active": true,
        "last_contact_at": "2026-10-16T08:00:03Z",
        "last_collected_at": "2026-10-16T09:05:00Z",
        "fresh": true
      }
    }
  ],
  "next_cursor": null
}
```

- `fill_pct`, `distance_mm`, `sampled_at` lấy từ **lần đo tốt gần nhất**. `latest_quality` là chất lượng của bản tin mới nhất. Khi `latest_quality != "ok"` mà vẫn còn số cũ, hiển thị số cũ kèm biểu tượng lỗi cảm biến.
- `fresh` do Backend tính: lần đo tốt trong 8 giờ gần nhất, không ở tương lai, và thời gian đo đáng tin. Frontend không tự tính.
- `last_collected_at`: lần thu gom gần nhất đã xác nhận (null nếu chưa có). Nếu `last_collected_at` mới hơn `sampled_at` mà `alarm_active` vẫn `true`, UI hiển thị "đã thu gom, chờ cảm biến xác nhận".
- `state` là `null` nếu thùng chưa gắn thiết bị hoặc chưa có dữ liệu.

### 3.3 `GET /bins/{id}`

Trả như một phần tử của `/bins`, thêm `notes`, `device` (`{id, lifecycle, enabled}` hoặc null) và `open_alerts` (cảnh báo còn hiệu lực của thùng: cả `open` lẫn `acknowledged`, mới nhất trước; gồm cảnh báo đầy và lỗi cảm biến). 404 nếu không tồn tại.

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

Body: `code`, `name`, `address`, `ward_code`, `waste_type`, `location` (hoặc `lat`,`lng`; **bắt buộc**, thiếu tọa độ trả 422 vì thùng phải lên được bản đồ và vào tuyến), `capacity_l?`, `notes?`. `id` của thùng chính là `code` (ví dụ `WB-001`); Backend tự đặt `status=active`, `environment=field`. 409 nếu trùng `code`. Trả thùng vừa tạo theo cùng dạng một phần tử của `GET /bins` (`state = null` vì chưa gắn thiết bị).

Ràng buộc (sai trả 422): `code` chỉ gồm chữ, số, `-`, `_`, `:` (tối đa 40 ký tự, không dấu cách); `capacity_l` từ 1 đến 100000 (bỏ trống = null, không gửi 0); tọa độ `[kinh độ -180..180, vĩ độ -90..90]`; gửi `lat` thì phải gửi cả `lng`.

### 3.7 `PATCH /bins/{id}`

Sửa một phần: `name`, `address`, `ward_code`, `waste_type`, `location`, `capacity_l`, `status`, `notes`. Chỉ trường có mặt trong body mới bị đổi. Không sửa `id`, `code`, `environment` (gửi lên sẽ bị bỏ qua). Không xóa thùng: "xóa" là `{"status":"retired"}`. `capacity_l`, `notes` được đặt `null`; các trường khác (kể cả `location`) không được `null`. Body rỗng trả 422. Trả thùng sau khi sửa.

### 3.7b Ảnh vị trí đặt thùng: `PUT`, `GET`, `DELETE /bins/{id}/photo`

Admin chụp chỗ đặt thùng để collector ra đến nơi nhận ra đúng thùng (tọa độ GPS lệch vài mét). Mỗi thùng **một ảnh**, ảnh mới thay ảnh cũ.

- **Tạo thùng có ảnh** gồm 2 bước: `POST /bins` (JSON như mục 3.6), thành công thì gọi `PUT /bins/{id}/photo` nếu admin có chọn ảnh. Sửa thùng thì gọi lại `PUT` để đổi ảnh.
- `PUT` (admin): body `multipart/form-data`, field tên `photo`. Nhận JPEG, PNG, WebP, tối đa **2 MB**; backend kiểm tra nội dung file, không dựa vào đuôi tên. Trả `{"bin_id","content_type","size_bytes","photo_url"}`. Lỗi: không phải ảnh hoặc thiếu field `photo` → 422; quá 2 MB → 413 `TOO_LARGE`; thùng không tồn tại → 404.
- **`photo_url`**: mọi phản hồi có thùng (`GET /bins`, `GET /bins/{id}`, `POST`/`PATCH /bins`) có trường này. Là link tương đối có chữ ký, **dùng thẳng trong `<img src>`, không cần token**; `null` khi thùng chưa có ảnh. Link sống 6–12 giờ, nên luôn lấy `photo_url` mới từ API, không lưu lâu. Đổi ảnh thì link đổi theo, nên trình duyệt không hiện ảnh cũ từ cache.
- `GET /bins/{id}/photo?v=…&exp=…&sig=…`: chính là link trong `photo_url`, frontend không tự ghép. Trả **file ảnh** (`image/jpeg|png|webp`), không phải JSON. Chữ ký sai hoặc hết hạn → 403; ảnh đã bị thay hoặc xóa → 404.
- `DELETE` (admin): 204; 404 nếu chưa có ảnh.

Gợi ý frontend:

- Ô chọn ảnh: `<input type="file" accept="image/jpeg,image/png,image/webp">`; trên điện thoại ô này cho chọn chụp bằng camera. Ảnh điện thoại thường lớn hơn 2 MB: nên thu nhỏ trước khi gửi (vẽ lên `<canvas>` cạnh dài ~1600 px rồi `canvas.toBlob(cb, "image/jpeg", 0.8)`).
- Gửi: `const fd = new FormData(); fd.append("photo", file); fetch(url, {method: "PUT", headers: {Authorization}, body: fd})`. **Không** tự đặt header `Content-Type`, trình duyệt tự thêm `boundary`.
- Hiển thị: `<img src={bin.photo_url ?? ảnhMặcĐịnh}>`. Mobile PWA (`MobileBinDetail`, `MobileMap`) đã đọc sẵn `photo_url` nên không phải sửa. Sau khi `PUT` thành công, dùng `photo_url` trong phản hồi để hiện ngay ảnh mới.

### 3.8 `POST /devices` (201)

Body: `id` (dạng `bin-001`, 3 đến 6 chữ số), `hardware_model`, `firmware_version`, `gateway_ids[]`, `sensors[]` (`{sensor_id,type:"ultrasonic|lid_switch",model}`), `serial_number?`, `notes?`. 409 nếu trùng `id` hoặc `serial_number`. Không trả thông tin MQTT.

- Mỗi gateway trong `gateway_ids` (dạng `gw-001`) phải đã được đăng ký, nếu không trả 422 với `details.unknown = [...]`. Với dữ liệu mô phỏng dùng `gw-simulator`.
- Cần ít nhất một cảm biến `ultrasonic`; `model` không được rỗng.
- Thiết bị mới ở trạng thái `lifecycle = "stock"` cho tới khi được gắn vào thùng.

### 3.9 `POST /bins/{id}/assignments` (201)

Body: `device_id`, `reason`. Gắn hoặc thay thiết bị cho thùng trong một transaction: đóng gắn cũ, tăng `assignment_version`, reset hiện trạng thùng (số đo cũ không còn hiện), đóng các cảnh báo đang mở của thùng với lý do `device_replaced`, chuyển thiết bị cũ về `stock`. Trả `{"id","bin_id","device_id","assignment_version","installed_at","reason","replaced_device_id"}`.

- 409 nếu thiết bị đang gắn thùng khác (`details.bin_id` cho biết thùng nào), thiết bị đã tắt, hoặc thùng đã `retired`. 404 nếu thùng hoặc thiết bị không tồn tại.
- Chỉ số đo lấy **sau** thời điểm gắn mới được tính cho thùng. Lưu ý khi demo: simulator của Quang Sơn phát mẫu đo lùi 7 phút về quá khứ, nên với thiết bị vừa gắn phải đợi quá 7 phút rồi chạy simulator thì thùng mới có số đo.

### 3.10 `POST /collection-events` (201)

Bắt buộc header `Idempotency-Key` (UUID do client sinh, dùng lại khi gửi lại). Body: `bin_id`, `completed_at`, `measured_weight_kg?` (null nếu không có cân), `weight_source?` (`scale|manual|unknown`), `fill_before_pct?`, `fill_after_pct?`, `note?`.

- Cùng key và cùng nội dung: trả lại bản ghi cũ (200). Cùng key, nội dung khác: 409.
- Thiếu header `Idempotency-Key` trả 422. Mỗi lần bấm "Đã thu" sinh một key mới; chỉ dùng lại key khi gửi lại đúng yêu cầu đó (mất mạng, hết thời gian chờ).
- `completed_at` không được ở tương lai quá 5 phút (422).
- `worker_id` lấy từ token. `waste_type` lấy theo thùng tại lúc thu gom.
- Cân: có `measured_weight_kg` thì `weight_source` là `scale` hoặc `manual` (bỏ trống thì mặc định `manual`); không có cân thì bỏ cả hai, Backend lưu `weight_source = unknown`. Gửi `weight_source` mà không có số kg trả 422.
- Thùng không tồn tại: 404. Thùng đã `retired`: 409.
- Thu gom theo tuyến: gửi thêm `route_id` và `stop_order` (phải đi cùng nhau, thiếu một trả 422). Tuyến không tồn tại 404; không giao cho user này 403; chưa `in_progress` hoặc điểm dừng đã thu/bỏ qua 409; điểm dừng không khớp `bin_id` hoặc `completed_at` trước lúc bắt đầu tuyến 422. Thành công thì điểm dừng chuyển `collected`. Thu gom ngoài tuyến: bỏ hai trường này (null). Hoàn thành cả tuyến vẫn qua `PATCH /routes/{id}/status`.
- Trả phần tử cùng dạng `GET /collection-events`.
- Thu gom **không** tự đặt `fill_pct` về 0 và không đóng cảnh báo; UI có thể hiển thị "đã thu gom, chờ cảm biến xác nhận" (xem `last_collected_at` ở mục 3.2).

### 3.10b `GET /collection-events`

Lịch sử thu gom, mới nhất trước. Query (đều không bắt buộc): `bin_id`, `worker_id`, `route_id`, `from`, `to`, `limit`, `cursor`; `from > to` trả 422. Quyền: admin, collector. Collector chỉ thấy lượt của mình (Backend tự lọc, bỏ qua `worker_id` gửi lên). Phần tử: `{"id","bin_id","worker_id","worker_name","route_id","stop_order","completed_at","recorded_at","waste_type","measured_weight_kg","weight_source","fill_before_pct","fill_after_pct","note"}`.

### 3.11 `GET /stats/waste-by-type`

Quyền: admin, collector (app mobile có màn thống kê). Query: `from`, `to` (bắt buộc). Trả `{"items":[...]}` (không phân trang), luôn đủ 5 phần tử theo thứ tự `general, organic, recyclable, hazardous, other`:
`{"waste_type","bin_count","collection_count","avg_fill_pct","known_weight_kg","known_weight_count","unknown_weight_count"}`.

- `bin_count`: số thùng đang dùng (field, chưa `retired`) thuộc loại đó.
- `avg_fill_pct`: mức đầy trung bình của các mẫu đo **tốt** trong khoảng thời gian; `null` nếu không có mẫu.
- `collection_count`, `known_weight_*`, `unknown_weight_count`: từ các lượt thu gom đã xác nhận trong khoảng. Không có cân thì chỉ có số lượt; `known_weight_kg` chỉ cộng các lượt có cân, `null` nếu không lượt nào có cân. Không suy kg từ `fill_pct`.

### 3.12 Lập tuyến tự động theo ca và `POST /routes/generate`

Tuyến do hệ thống tự lập và tự giao; admin chỉ xử lý ngoại lệ (đề xuất tuần 9, phương án B).

**Mỗi ca** (giờ trong `ROUTE_SHIFT_TIMES`, mặc định `06:00,14:00` giờ Việt Nam), worker nền:

1. Hủy các tuyến của ca trước chưa ai bắt đầu (`planned`, `assigned`), để thùng của chúng được lập lại.
2. Chọn thùng cần thu gom. Thùng phải là thùng `field`, `active`, có tọa độ, đang gắn thiết bị, có số đo tốt còn mới (`fresh`) và `latest_quality = ok`. Thêm một trong ba điều kiện:
   - cảm biến báo đầy (`alarm_active = true`);
   - hoặc `fill_pct >= 80`;
   - hoặc dự báo sẽ tràn trước ca sau: `fill_pct + 1,3 × tốc độ đầy × số giờ tới ca sau >= 100`. Tốc độ đầy tính từ các mẫu tốt trong 48 giờ gần nhất, sau lần thu gom gần nhất; cần ít nhất 2 mẫu.

   Thùng bị loại nếu đang nằm trong một tuyến chưa xong, hoặc đã có lượt thu gom mới hơn số đo gần nhất (đã đổ, chờ cảm biến báo lại).
3. Lấy các collector `active` chưa cầm tuyến nào (`assigned` hoặc `in_progress`), sắp theo id.
4. Chia thùng theo góc quanh bãi tập kết (sweep), mỗi collector một vùng. Trong mỗi vùng, sắp thứ tự bằng láng giềng gần nhất rồi 2-opt. Không có collector nào thì vẫn tạo **một** tuyến `planned` để admin giao tay.
5. Lưu tuyến `assigned` (hoặc `planned`), `created_by = "system:route-worker"`.

Mỗi ca chỉ chạy một lần. Worker tắt lúc 06:00 rồi bật lại lúc 10:00 thì vẫn chạy ca 06:00; bật lại sau 14:00 thì chỉ chạy ca 14:00.

**`POST /routes/generate`** (admin, không cần body) là nút **"Tạo tuyến ngay"**: chạy đúng thuật toán trên ngay lúc bấm, nhưng không hủy tuyến nào, chỉ lấy thùng chưa nằm trong tuyến. Dùng khi có thùng đầy gấp giữa ca, hoặc khi demo. Trả `{"items":[...]}` gồm các tuyến vừa tạo (dạng như `GET /routes`); `items` rỗng nghĩa là không có thùng nào cần thu.

**Khoảng cách** là đường chim bay (haversine), **không** phải đường phố thật. Một tuyến gồm một hoặc nhiều **chuyến**, mỗi chuyến tối đa `ROUTE_MAX_STOPS` điểm (mặc định 20), đi từ bãi tập kết và quay về. `planned_distance_m` cộng mọi chuyến.

**Baseline** là lịch cố định: đi hết mọi thùng `active` có tọa độ theo thứ tự mã thùng, cùng cách tính khoảng cách và cùng số điểm mỗi chuyến. Baseline tính cho **cả ngày**, nên mọi tuyến cùng ngày mang cùng một `baseline_distance_m`, và báo cáo chỉ lấy một lần mỗi ngày (mục 3.15). Đây là phép so sánh mô phỏng để đo chỉ tiêu km và số chuyến giảm được, không phải quãng đường xe thực chạy.

Cấu hình (biến môi trường của `api` và `worker`, có giá trị mặc định nên không bắt buộc đặt):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DEPOT_LAT`, `DEPOT_LNG` | `21.0047`, `105.8431` (cổng Parabol, ĐHBK) | Bãi tập kết, điểm xuất phát và kết thúc mỗi chuyến |
| `ROUTE_SHIFT_TIMES` | `06:00,14:00` | Giờ chạy ca, giờ Việt Nam |
| `ROUTE_MAX_STOPS` | `20` | Số điểm tối đa một chuyến |
| `ROUTE_FORECAST` | `true` | Bật dự báo tràn |

### 3.13 Quản lý người dùng (chỉ admin)

Dùng để admin tạo tài khoản cho nhân viên thu gom và cho admin khác. Không bao giờ trả `password_hash`.

- `POST /users` (201): body `{"email","display_name","password","roles":["collector"],"phone?"}`. `roles` gồm 1 đến 2 giá trị **không lặp** trong `admin|collector` (gửi `dispatcher` trả 422); mật khẩu 8 đến 72 ký tự; tài khoản tạo xong ở trạng thái `active`, đăng nhập được ngay. Email được lưu chữ thường; 409 nếu trùng email (không phân biệt hoa thường). Trả `{"id","email","display_name","roles","status","phone","last_login_at","created_at"}`.
- `PATCH /users/{id}`: sửa một phần `display_name`, `roles`, `status` (`active|disabled`), `phone` (được đặt `null`), và `password` (admin đặt lại mật khẩu khi người dùng quên). Các trường khác `phone` không được `null`; body rỗng 422; không có tài khoản 404. Admin không được tự khóa hoặc tự bỏ quyền admin của chính mình (409). Tài khoản `disabled` mất hiệu lực ngay ở request kế tiếp. Kích hoạt tài khoản chưa có mật khẩu phải gửi kèm `password` (không thì 422). Trả cùng dạng `POST /users`.
- `GET /users`: query `role`, `status` (`pending|active|disabled`), `limit`, `cursor`; trả `{"items":[...],"next_cursor":...}` với phần tử như kết quả `POST /users`, sắp theo `id`. Chỉ admin gọi được (collector trả 403). Chọn người khi giao tuyến: `GET /users?role=collector&status=active`.

### 3.14 Tuyến thu gom

Tuyến được tạo tự động (mục 3.12); không có endpoint tạo tuyến bằng tay.

- `GET /routes` (admin, collector): query `service_date` (`YYYY-MM-DD`), `status`, `assigned_worker_id`, `limit`, `cursor`. Sắp **mới nhất trước**. Collector chỉ thấy tuyến được giao cho mình (backend tự lọc, bỏ qua `assigned_worker_id` gửi lên). Phần tử:

```json
{
  "id": "rt-20261122-0600-1",
  "service_date": "2026-11-22",
  "status": "assigned",
  "assigned_worker_id": "usr-3f2a9c1b7e40",
  "assigned_worker_name": "Nguyễn Văn A",
  "depot": { "lat": 21.0047, "lng": 105.8431 },
  "stops": [
    {
      "stop_order": 1, "bin_id": "WB-007", "lat": 21.006, "lng": 105.845,
      "planned_fill_pct": 86.5, "status": "pending", "completed_at": null,
      "collection_event_id": null, "skip_reason": null
    }
  ],
  "stop_count": 8, "collected_count": 0, "trip_count": 1,
  "planned_distance_m": 4200, "baseline_distance_m": 18600,
  "actual_distance_m": null, "actual_distance_source": null,
  "started_at": null, "completed_at": null,
  "created_by": "system:route-worker", "created_at": "2026-11-21T23:00:02Z"
}
```

  Điểm dừng đã sắp sẵn theo thứ tự ghé (`stop_order` 1, 2, 3...); mobile nối `depot` → các điểm theo `stop_order` → `depot` để vẽ tuyến. `lat`/`lng` của điểm là tọa độ chụp lúc lập tuyến. `trip_count` là số chuyến (mỗi chuyến tối đa `ROUTE_MAX_STOPS` điểm, về bãi đổ giữa các chuyến).
- **Thu gom một điểm** trên tuyến: `POST /collection-events` kèm `route_id` và `stop_order` (mục 3.10). Tuyến phải đang `in_progress`; điểm chuyển `collected`.
- `PATCH /routes/{id}/status`: body `{"status", ...}`. Chuyển trạng thái hợp lệ:

| Từ → sang                              | Ai được làm         | Body thêm                                                                                         |
| -------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------- |
| `planned` → `assigned`                 | admin               | `assigned_worker_id` (collector đang `active`, sai thì 422)                                       |
| `assigned` → `assigned` (**giao lại**) | admin               | `assigned_worker_id` mới; chỉ khi tuyến chưa bắt đầu (collector nghỉ đột xuất)                    |
| `assigned` → `in_progress`             | collector được giao |                                                                                                   |
| `in_progress` → `completed`            | collector được giao | `actual_distance_m?`, `actual_distance_source?` (`odometer`, `gps` hoặc `manual`), `skip_reason?` |
| bất kỳ trước `completed` → `cancelled` | admin               |                                                                                                   |

Khi `completed`, các điểm dừng còn `pending` chuyển `skipped` với `skip_reason` (bắt buộc nếu còn điểm `pending`, thiếu thì 422). `actual_distance_m` và `actual_distance_source` gửi cùng nhau hoặc không gửi. Người không đúng vai trò hoặc không phải người được giao trả 403; chuyển trạng thái sai trả 409; không có tuyến trả 404. Trả tuyến sau khi đổi. Tuyến bị hủy trả thùng của nó về cho lần lập tuyến sau.

### 3.15 `GET /reports/routes`

Admin. Query `from`, `to` (ngày `YYYY-MM-DD`, giờ Việt Nam; `from <= to`). Chỉ tính tuyến `completed`. Trả `{"items":[...],"summary":{...}}`:

- Mỗi **ngày** có tuyến hoàn thành: `{"service_date","route_count","stop_count","collected_count","planned_distance_m","actual_distance_m","baseline_distance_m","planned_trips","baseline_trips","planned_reduction_pct","actual_reduction_pct","trip_reduction_pct"}`.
- `summary`: `day_count`, `route_count` và tổng các cột quãng đường, số chuyến, cùng ba tỷ lệ giảm trên cả khoảng.

Tính theo ngày vì baseline là lịch cố định của cả ngày (mục 3.12): `planned` và `actual` cộng mọi tuyến trong ngày (2 ca), `baseline` lấy một lần.

`planned_reduction_pct = (baseline - planned) / baseline × 100` là mức giảm theo mô phỏng. `actual_distance_m` chỉ có khi **mọi** tuyến trong ngày đã nhập km thực tế, nếu không là `null` và `actual_reduction_pct` cũng `null`. Không lấy planned thay cho actual. `trip_reduction_pct` so số chuyến kế hoạch với số chuyến của lịch cố định.

### 3.16 `POST /devices/{id}/configs` (201)

Khai báo thông số hiệu chuẩn đang nạp trong firmware của thiết bị. Body `{"config_rev":1,"empty_distance_mm":1000,"full_distance_mm":200,"sample_interval_s":60,"report_interval_s":21600,"note?"}`; điều kiện `full_distance_mm < empty_distance_mm`. `config_rev` phải trùng giá trị đang nạp trên node. Tạo xong ở trạng thái đã xác minh và thành cấu hình đang dùng của thiết bị. 409 nếu revision đã tồn tại (revision cũ không sửa được, muốn đổi thì tạo revision mới).

- `sample_interval_s` mặc định 60, `report_interval_s` mặc định 21600 (6 giờ), `report_interval_s >= sample_interval_s`. Ngưỡng 80% / 70% / 2 chu kỳ cố định theo firmware v1, client không gửi.
- `sensor_id` Backend tự lấy từ cảm biến siêu âm của thiết bị.
- Trả cấu hình vừa tạo kèm `requeued_messages`: số bản tin trước đó bị chặn vì thiếu hiệu chuẩn, nay được đưa lại hàng đợi xử lý.
- Mốc rỗng, mốc đầy và `config_rev` phải là giá trị thật đo trên thùng và nạp trên node; web nên cho admin nhập thay vì viết cứng.

**Thiết bị chưa có cấu hình thì dữ liệu đo vẫn được lưu nhưng không hiện lên thùng.** Vì vậy hộp thoại gắn thiết bị trên web nên đi theo thứ tự: `POST /devices` → `POST /devices/{id}/configs` → `POST /bins/{id}/assignments`.

## 4. Ghi chú về dữ liệu

- Hệ thống chỉ có 1 thùng gắn cảm biến thật; các thùng còn lại là dữ liệu mô phỏng. API không phân biệt hai loại này.
- Thùng thật có thể báo chất lượng xấu (mở nắp, mất echo). UI nên hiển thị `latest_quality` cùng `fill_pct`, không ẩn.

## 5. Không làm và thứ tự cắt

- WebSocket đẩy cập nhật: không làm, polling 30 giây là đủ.
- Quên mật khẩu qua email: không làm (admin đặt lại bằng `PATCH /users/{id}`).
- Nếu Backend trễ lịch, thứ tự cắt: `GET /reports/routes`, rồi nhóm `/routes`, rồi `change-password`. Sẽ báo trước nếu phải cắt.
- `GET /reports/routes` chỉ có km thực tế khi collector nhập `actual_distance_m` lúc hoàn thành tuyến (mục 3.14); nếu không nhập thì chỉ có mức giảm theo mô phỏng.

## 6. Chú ý!

Đã thống nhất: một `access_token` 8 giờ không refresh; polling `GET /bins` mỗi 30 giây; web chạy ở `http://localhost:5173` (CORS).

1. Tên trường trong ví dụ `GET /bins`, `GET /bins/{id}` (mục 3.2, 3.3) có khớp với code web hiện tại không?
2. Web cần thêm: màn hình quản lý người dùng (admin), đổi mật khẩu, và bước nhập hiệu chuẩn trong hộp thoại gắn thiết bị (mục 3.16).
