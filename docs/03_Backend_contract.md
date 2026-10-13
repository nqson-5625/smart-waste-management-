# 03. Hợp đồng Firmware/IoT - Backend (wire v1, database v2)

Tài liệu này là hợp đồng dữ liệu chung. Firmware & Kết nối IoT phụ trách Gateway -> MQTT -> kiểm tra và ghi telemetry vào MongoDB -> ACK sau khi ghi thành công. Backend query trực tiếp MongoDB để lấy dữ liệu; Backend không nhận MQTT và không gửi ACK. Các lựa chọn chưa có trong hai PDF đã được chốt thành mặc định v1 dưới đây; đây là đề xuất thực thi của bộ mã, không phải thông số đã được nhóm đo thực tế. Backend không phải giải mã LoRa: ESP32 gateway đã chuyển thành JSON UTF-8.

## 1. Thiết lập môi trường và phân chia công việc

1. Dùng `docker compose up -d --build` ở thư mục gốc để chạy MongoDB, Mosquitto, seed registry và dịch vụ `iot-ingestion`.
2. `iot-ingestion/consumer.py` nhận MQTT, kiểm tra schema/registry, ghi raw telemetry bền vững vào MongoDB và gửi ACK `stored`/`duplicate`. Nếu ghi thất bại, không gửi ACK thành công để Gateway giữ và thử lại bản tin.
3. Backend cài `backend/requirements.txt`, cấu hình `MONGO_URI`/`MONGO_DB`, rồi dùng các helper trong `backend/smartwaste_backend/` để query MongoDB.
4. Có thể phát simulator bằng `python iot-ingestion/mock_publisher.py`. Mặc định simulator dùng bin-900001/gw-simulator để tách khỏi bin-001/gw-001.
5. Khi Gateway thật xong, cấu hình endpoint MQTT/TLS và credential trong firmware; giữ nguyên schema và MongoDB contract. Không đưa credential thật vào Git.

| Biến môi trường | Ý nghĩa / giá trị mặc định |
|---|---|
| MQTT_HOST | Host của broker; mặc định localhost cho script chạy trên máy phát triển |
| MQTT_PORT | 8883 khi TLS=1; 1883 khi TLS=0 |
| MQTT_TLS | 1 mặc định; chỉ đặt 0 trong LAN phát triển được kiểm soát |
| MQTT_USERNAME, MQTT_PASSWORD | Tài khoản đúng vai trò; không hardcode vào Git |
| MQTT_CA_FILE | Đường dẫn PEM CA nếu broker dùng CA riêng; bỏ trống dùng CA hệ thống |
| MQTT_CLIENT_ID | consumer mặc định smartwaste-ingestor; phải duy nhất nếu chạy nhiều tiến trình |
| MONGO_URI | Mặc định `mongodb://localhost:27017/?directConnection=true`; môi trường khác dùng URI có quyền phù hợp |
| MONGO_DB | Mặc định `smartwaste_v2` |
| MOCK_DEVICE_NUMBER | 900001 mặc định; nếu đổi phải cập nhật registry/ACL |
| MOCK_GATEWAY_ID | gw-simulator mặc định; nếu đổi phải cập nhật registry/ACL |

Ví dụ PowerShell cho môi trường phát triển: `$env:MQTT_TLS="0"`; `$env:MQTT_HOST="192.168.1.10"`; `$env:MQTT_USERNAME="sw-ingestion"`; `$env:MQTT_PASSWORD="MAT_KHAU_DA_CAP"`. Ở terminal simulator dùng tài khoản `sw-simulator`. Với bash dùng `export MQTT_TLS=0` và các biến tương ứng. Đây là giá trị minh họa, không phải tài khoản đã được tạo.

MongoDB schema v2 phải tồn tại trước khi chạy ingestion. Ingestion dùng write concern majority và journal, đồng thời từ chối khởi động nếu thiếu migration `schema-v2_0_0`. Docker Compose tạo replica set, chạy `mql/01_schema.js`, seed dữ liệu registry, rồi mới chạy ingestion. Validator và index chỉ do script schema quản lý.

## 2. Broker, topic, QoS và ACL

MQTT 3.1.1 qua TCP/TLS. Gateway client ID `smartwaste-gw-001`, username `gw-001`, keepalive 30 giây. Firmware reconnect có độ trễ ngẫu nhiên 5-10 giây; Wi-Fi thử lại mỗi 15 giây. Không dùng HTTP từ node/gateway trong bản này.

| Topic | Bên phát -> bên nhận | QoS / retain | Nội dung |
|---|---|---|---|
| smartwaste/v1/devices/bin-001/telemetry | Gateway -> IoT ingestion | Publish QoS 0, retain=false | Một phép đo/sự kiện JSON |
| smartwaste/v1/gateways/gw-001/ack | IoT ingestion -> Gateway | Publish QoS 1, retain=false; gateway subscribe QoS 1 | ACK sau lưu bền vững |
| smartwaste/v1/gateways/gw-001/status | Gateway -> IoT ingestion | Online/heartbeat QoS 0 retain=true; LWT QoS 1 retain=true | Trạng thái được kiểm tra và lưu vào `gateways` |

Consumer subscribe `smartwaste/v1/devices/+/telemetry` và `smartwaste/v1/gateways/+/status`. Backend đọc MongoDB trực tiếp, không subscribe MQTT. Topic không có dấu `/` ở đầu, tên phân biệt hoa thường. Payload telemetry tối đa 1.200 byte; buffer MQTT gateway 1.536 byte gồm cả topic/header. Dữ liệu thật là JSON thu gọn. Topic không chứa API key/mật khẩu.

ACL tối thiểu cho tài khoản gw-001: write telemetry của bin-001 đã được gán; write status của gw-001; read ack của gw-001. Không cho gateway write ack. Tài khoản IoT ingestion: read telemetry và write ack theo gateway được quản lý. Backend chỉ cần quyền đọc MongoDB theo chính sách triển khai. Tài khoản simulator: write telemetry bin-900001 và read ack gw-simulator; không ghi dữ liệu thiết bị thật. Tạo mapping broker identity -> gateway và registry device -> gateway; không dùng riêng trường gateway_id tự khai trong JSON làm bằng chứng xác thực.

Các ACK của IoT ingestion không được retained. Xóa retained telemetry/ACK tồn tại do thử sai trước khi tích hợp. Consumer từ chối telemetry được gửi đến như retained. Gateway không có topic config/cmd; Backend không cần xây downlink cấu hình cho v1.

## 3. Payload telemetry đầy đủ

Payload mẫu nằm ở `iot-ingestion/fixtures/full.json`. Mọi trường trong schema đều bắt buộc; trường chưa đo được phải là JSON null, không phải chuỗi "null", chuỗi rỗng hay 0 giả.

| Trường | Kiểu, đơn vị | Quy tắc |
|---|---|---|
| schema_version | integer | Luôn 1 |
| message_id | string | `{device_id}-{boot_id hex 8}-{seq hex 8}`, hex thường |
| device_id | string | `bin-001` từ DEVICE_NUMBER=1; tối thiểu 3 chữ số, tối đa 999999 |
| gateway_id | string | Ví dụ gw-001, định danh từ Config gateway |
| boot_id | integer 1..4294967295 | Tăng theo cold boot, giữ qua timer wake; NVS node |
| seq | integer 1..4294967295 | Tăng theo báo cáo trong boot; gửi lại giữ nguyên |
| node_uptime_s | integer, giây | Thời điểm đo tương đối từ đầu boot, bao gồm deep sleep |
| sample_age_at_rx_s | integer, giây | Tuổi mẫu tại lần radio nhận đầu được giữ trong queue |
| reason | enum | boot, periodic, full, cleared, sensor_fault, sensor_recovered |
| quality | enum | ok, timeout, unstable, lid_open, out_of_range |
| distance_mm | integer hoặc null | 20..4000 khi ok; khoảng cách từ sensor tới mặt rác |
| fill_pct | number hoặc null | 0..100; độ phân giải 0,1%; phải ok mới có giá trị |
| battery_mv | integer hoặc null | mV; v1 luôn null vì chưa có mạch ADC và hiệu chuẩn pin |
| alarm_active | boolean hoặc null | Trạng thái đã xác nhận; null nếu chưa đủ bằng chứng sau boot |
| lid_open | boolean hoặc null | null khi không gắn reed; true khi phát hiện mở nắp |
| valid_samples | integer 0..7 | Số mẫu còn hợp lệ sau lọc; ok đòi hỏi >=5 |
| config_rev | integer 1..65535 | Bản hiệu chuẩn node; Backend lưu lịch sử, không tự sửa node |
| dropped_reports | integer 0..65535 | Số báo cáo node bỏ do RTC queue đầy trong boot hiện tại; bão hòa tại 65535 |
| node_fw, gateway_fw | string | Phiên bản, hiện 1.0.0 |
| rssi_dbm | integer, dBm | RSSI radio tại gateway, không phải RSSI Wi-Fi |
| snr_db | number, dB | SNR LoRa; gateway giữ đến 0,1 dB |
| gateway_boot_id | integer | Phiên gateway tại thời điểm nhận LoRa, có thể khác phiên đang publish |
| gateway_rx_uptime_ms | integer, ms | millis của gateway khi nhận, quay vòng sau khoảng 49,7 ngày; không dùng để sắp xếp nghiệp vụ |
| gateway_received_at_ms | integer hoặc null | Unix epoch UTC ms lúc nhận LoRa nếu đã có thời gian hợp lệ |
| sampled_at_ms | integer hoặc null | Ước tính bằng gateway_received_at_ms - sample_age_at_rx_s × 1000 |
| time_quality | enum | gateway_estimated hoặc unsynced |

Ingestion thêm các trường DB v2: `_id`, `db_schema_version`, `bin_id`, `assignment_id`, `mapping_status`, `sampled_at`, `gateway_received_at`, `received_at`, `content_hash` và `processing`. Payload nguồn vẫn giữ nguyên ở cấp đầu. UI hiển thị theo Asia/Ho_Chi_Minh. Không chia timestamp ms cho 1.000 hai lần. Node không có thời gian UTC/GPS trong v1. Thời gian ước tính có sai số RTC, làm tròn giây và truyền; không phải timestamp chuẩn đo lường.

Nhận bản tin trong thời gian gateway chưa có NTP: hai trường epoch đều null, time_quality=unsynced; ngay cả khi gateway đồng bộ sau đó bản ghi cũ vẫn giữ null. Không gán giờ publish MQTT thành giờ đo. Với một queue lưu qua mất Internet, thời gian server nhận có thể muộn nhiều giờ.

Cross-check ngoài JSON Schema: topic phải khớp device_id; message_id phải khớp device_id/boot_id/seq; hai timestamp phải đúng quan hệ tuổi mẫu; device phải enabled và được gán gateway đó. Schema nằm tại `iot-ingestion/schemas/telemetry.schema.json`, chuẩn Draft 2020-12, additionalProperties=false. Thay đổi phá vỡ hợp đồng phải nâng version/topic; v1 không tự chấp nhận schema tương lai.

## 4. Nghĩa của quality, reason và cảnh báo

| Giá trị | Backend xử lý |
|---|---|
| quality=ok | Cho phép cập nhật giá trị đo; xem tiếp thứ tự và độ mới |
| timeout | Không đủ 5 khoảng cách hợp lệ; gồm không có echo và mẫu vượt phạm vi vật lý bị loại |
| unstable | Còn <5 mẫu sau loại ngoại lai; không dùng fill cũ như giá trị đo mới |
| lid_open | Có reed và phát hiện nắp mở trong nhóm đo; phép đo vô hiệu |
| out_of_range | Khoảng cách/hiệu chuẩn không phù hợp; cần kiểm tra gá và mốc |
| reason=boot | Báo sau khởi động; alarm có thể null |
| reason=periodic | Đến chu kỳ tương đối 6 giờ |
| reason=full | Đã xác nhận hai chu kỳ >80%, alarm_active=true |
| reason=cleared | Đã xác nhận hai chu kỳ <=70%, alarm_active=false |
| reason=sensor_fault | Lỗi chất lượng 3 chu kỳ liên tiếp; không đồng nghĩa thùng rỗng |
| reason=sensor_recovered | Chất lượng trở lại ok 2 chu kỳ liên tiếp |

Backend dùng alarm_active đã được firmware xác nhận để đồng bộ trạng thái cần thu gom, áp dụng trên báo cáo **mới hơn và quality=ok**. Nếu null thì giữ trạng thái đã biết. Có thể so sánh fill để kiểm tra bất nhất, nhưng không đếm hai bản tin MQTT làm “hai chu kỳ đo”: phần lớn chu kỳ 60 giây không được phát.

Bật cảnh báo chỉ khi chuyển trạng thái chưa đầy -> đầy; một full bị phát lại 10 lần chỉ tạo một lần mở cảnh báo. Khi nhận periodic chất lượng tốt với alarm_active=true mà trước đó chưa biết đầy, cũng phải khôi phục trạng thái cần thu gom vì có thể sự kiện full trước đã mất. Tương tự false đã xác nhận có thể đóng cảnh báo cũ. Mức giảm không tự chứng minh nhân viên đã thu gom; cần bản ghi xác nhận thu gom từ ứng dụng.

## 5. ACK và xử lý lỗi chính xác

ACK JSON gồm đúng 3 trường: `{"schema_version":1,"message_id":"bin-001-00000001-00000001","status":"stored"}`. status có hai giá trị: stored khi insert mới, duplicate khi bản ghi giống nội dung nguồn đã tồn tại. Topic ACK lấy gateway_id của bản tin hiện nhận, kể cả bản đó trùng bản đã nhận qua gateway khác.

Trình tự consumer: kiểm tra schema/topic/registry -> tạo ID/hash -> upsert telemetry với ghi bền vững -> nếu trùng kiểm tra hash nội dung node -> publish ACK. Không ACK thành công trước commit. Khi timeout MongoDB có kết quả chưa biết, không ACK; lần retry thực hiện upsert lại nên vẫn an toàn với khóa duy nhất.

Hash loại các metadata đường truyền có thể đổi: gateway_id, gateway_fw, rssi_dbm, snr_db, gateway_boot_id, gateway_rx_uptime_ms, gateway_received_at_ms, sampled_at_ms, time_quality, sample_age_at_rx_s. Các trường nguồn còn lại của cùng ID phải nhất quán. Cùng ID nhưng khoảng cách/seq/nội dung node khác thì cách ly và báo lỗi định danh; không ACK duplicate, không ghi đè bản cũ. Consumer tham chiếu thực hiện kiểm tra này.

Schema sai, thiết bị lạ, sai quyền, lỗi database: không gửi stored/duplicate. Ghi log/quarantine nội bộ kèm lý do; sửa nguyên nhân để gateway thử lại. Chưa có ACK rejected và chưa có tự bỏ “poison message”; một bản lỗi có thể chặn đầu queue. Backend cần giám sát queue_depth, số lần retry và lỗi ingest, có quy trình xử lý thủ công thay vì ACK giả để xóa dữ liệu.

MQTT PUBACK của broker khác application ACK này. Node ACK radio chỉ cho biết gateway đã lưu; ACK từ IoT ingestion cho biết raw telemetry đã lưu. Consumer ACK sau raw persistence, chưa đợi Web/App hay projection. Backend query collection raw trong MongoDB và có thể dựng projection có checkpoint/replay mà không nằm trên đường nhận MQTT.

## 6. Bộ đệm, trùng, thứ tự và trạng thái offline

| Tình huống | Hành vi đã định nghĩa |
|---|---|
| Mất ACK radio | Node phát lại cùng ID; gateway có bản trong queue thì ACK lại, không nhân đôi slot |
| Mất MQTT/Internet | Gateway tiếp tục nhận radio đến tối đa 32 bản ghi NVS; phát lại khi nối được |
| Backend chưa hoạt động | Ingestion vẫn ghi dữ liệu; Gateway vẫn publish lại đầu queue mỗi 10 giây cho tới ACK |
| IoT ingestion ACK mất | Cùng bản tin đến lần nữa; Mongo upsert không tạo bản thứ hai; ACK duplicate |
| Gateway reset/mất điện | Queue NVS được nạp lại; bản đã được ACK sau ghi MongoDB nhưng xóa NVS thất bại có thể phát lại |
| Node mất điện/reset ngoài timer | Queue RTC chưa giao có thể mất; boot_id mới, seq bắt đầu lại |
| Gateway đầy queue | Không ACK radio; node retry/backoff và có thể tràn queue 4 bản |
| Bản cũ đến sau bản mới | Lưu lịch sử nhưng không ghi đè latest, không đóng/mở lại cảnh báo mới |
| Unknown/future schema | Từ chối/quarantine, không ACK thành công |

Thứ tự nguồn là cặp số `(boot_id, seq)` trong cùng device_id. So sánh số nguyên, không dùng string thời gian, không dùng thứ tự nhận MQTT. Boot_id chỉ có ý nghĩa tăng nếu NVS không bị xóa; quy trình reprovision là bắt buộc khi xóa toàn flash. `received_at` dùng vận hành/độ trễ, không thay thế thứ tự nguồn.

Gateway gửi heartbeat 60 giây. Online/heartbeat có đủ trường trong `iot-ingestion/schemas/status.schema.json`; LWT offline chỉ có schema_version, gateway_id, state. Khi mất kết nối broker có thể phát LWT sau timeout keepalive, không cam kết offline tức thời. Consumer cập nhật collection `gateways`, bỏ heartbeat retained cũ hơn 150 giây và không cho phiên boot cũ ghi đè phiên mới.

Node không có MQTT session và ngủ phần lớn thời gian; không áp dụng LWT gateway cho từng node. Mặc định đánh dấu dữ liệu node stale khi quá **8 giờ** không có mẫu mới có thời gian đáng tin; mất liên lạc cần so thời gian nhận radio mới nhất đã biết. Gateway mất mạng lâu hoặc time_quality=unsynced khiến thời điểm liên lạc không rõ: hiển thị unknown/needs_review, không đưa vào tuyến tự động như dữ liệu mới. 8 giờ và 150 giây là chính sách v1 đề xuất, phải lưu cấu hình server, tách khỏi firmware.

## 7. MongoDB, idempotency và projection

| Collection | Khóa/index chính | Nội dung |
|---|---|---|
| bins | `_id=bin_id`, unique code, 2dsphere location | Thùng vật lý và metadata vận hành |
| devices | `_id=device_id`, unique serial khi có | ESP32, sensor nhúng và gateway allowlist |
| device_assignments | unique assignment active theo device và bin | Lịch sử gắn thiết bị theo khoảng thời gian |
| device_configs | unique `(device_id, config_rev)` | Phiên hiệu chuẩn bất biến |
| telemetry | `_id=message_id`, unique `(device_id,boot_id,seq)`, index `(bin_id,sampled_at,_id)` | Payload nguồn cùng metadata DB v2 và trạng thái xử lý |
| bin_state | `_id=bin_id` | Projection hiện trạng có thể tái dựng |
| alerts | unique cảnh báo active theo scope/type | Vòng đời cảnh báo đầy, lỗi, stale và gateway offline |
| collection_events | unique idempotency key và route/stop | Lần thu gom được xác nhận |
| routes | index worker/ngày và lịch | Tuyến cùng các stop có giới hạn |
| users, gateways, audit_logs, ingest_rejections, schema_migrations | Theo `mql/01_schema.js` | Registry, audit, lỗi ingest và phiên schema |

Projection worker đọc `telemetry.processing.state=pending`, kiểm tra assignment/config rồi cập nhật `bin_state`, `alerts` và `audit_logs` trong transaction. Nếu dùng nhiều worker phải dùng lease và retry write conflict. Không làm read-then-write không điều kiện vì hai gói có thể đè nhau.

Bản mới nhưng quality!=ok: cập nhật latest_quality/latest_tuple, giữ last_good_fill cùng timestamp cũ; không biến last_good_fill thành mẫu mới. Alarm bool chỉ cập nhật khi quality=ok và alarm_active không null. Bản cũ: giữ raw, không đổi projection. Bản valid mới nhưng thời gian quá cũ/unsynced: có thể cập nhật lịch sử trạng thái, gắn stale/unknown; loại khỏi lựa chọn tuyến tự động cho tới khi có dữ liệu đủ tin cậy.

Consumer hiện thực validation, mapping assignment, raw persistence, gateway status và ACK. Phần projection, giao dịch cảnh báo, xác thực người dùng, API, thống kê và tối ưu tuyến là đầu việc Backend. Chi tiết chuẩn của toàn bộ 14 collection nằm trong `docs/05.Thiet_ke_MongoDB_SmartWaste.md` và `mql/01_schema.js`.

## 8. API đề xuất cho Web/App

Đây là hợp đồng HTTP đề xuất để nhóm thống nhất, chưa có HTTP server trong gói firmware.

| API | Dữ liệu/ý nghĩa cần trả |
|---|---|
| GET /api/v1/bins?status=full&limit=50&cursor=... | Danh sách phân trang; id, name, location, fill_pct, quality, alarm_active, freshness, sampled_at, last_contact_at |
| POST /api/v1/bins | Tạo thùng vật lý với metadata, vị trí, loại rác và dung tích; trả 201 |
| POST /api/v1/devices | Cấp thiết bị cùng sensor và gateway allowlist; trả 201 |
| POST /api/v1/bins/{id}/assignments | Gắn/thay thiết bị bằng transaction và tăng assignment_version |
| PATCH /api/v1/bins/{id} | Sửa metadata thùng; không tự cấu hình lại firmware |
| GET /api/v1/bins/{id} | Metadata + latest + last_good; thùng không tồn tại trả 404 |
| GET /api/v1/bins/{id}/telemetry?from=...&to=...&limit=... | Lịch sử UTC ISO8601, phân trang, quality/null rõ ràng |
| GET /api/v1/alerts?state=open | Các cảnh báo mở, tách đầy và lỗi thiết bị |
| POST /api/v1/collection-events | Xác nhận nhân viên đã thu gom; Idempotency-Key, bin_id, completed_at, worker_id, route_id, measured_weight_kg nếu có |
| POST /api/v1/routes/plan | Danh sách điểm đủ mới/cần thu gom, depot, ràng buộc xe; trả tuyến và km dự kiến |

HTTP thành công 200/201; validation 400/422 theo quy ước server; chưa đăng nhập 401; không đủ quyền 403; không tồn tại 404; trùng device_id/idempotency key với nội dung khác 409. Error dạng `{code,message,request_id,details}`. Không trả mật khẩu broker hay khóa node cho Web/App.

Tọa độ quản lý nằm trong registry, không có trong telemetry. Backend nhập từ vị trí lắp đặt thật; `location` GeoJSON có thứ tự `[longitude, latitude]`. Firmware không có GPS. Waste_type là metadata hoặc dữ liệu khác có nguồn, không suy ra bằng sóng siêu âm. Chỉ số dự án: lưu km/chuyến baseline và km/chuyến sau tối ưu trên cùng phạm vi/thời gian, không dùng số bản tin làm chỉ số lợi ích.

## 9. Phạm vi Backend sau khi có dữ liệu

Backend đọc trực tiếp các collection `telemetry` và `devices` trong MongoDB. `telemetry` lưu payload đã kiểm tra cùng `_id=message_id`, `received_at` và `content_hash`; unique index theo `device_id/boot_id/seq` ngăn bản ghi lặp. `devices` là registry định danh và metadata quản lý. Backend không subscribe MQTT, không ghi raw telemetry và không gửi ACK cho Gateway.

Backend query lịch sử/latest và device metadata trực tiếp từ MongoDB theo yêu cầu phần ứng dụng. Ingestion sở hữu xác thực payload, ghi bền vững, retry/idempotency và ACK sau commit. Thông tin broker, TLS, ACL và Wi-Fi được cấu hình bởi Firmware & Kết nối IoT theo môi trường; credential production không thuộc repository.

## 10. Khung radio để Firmware/Hardware bảo trì

Backend không cần tự đọc khung này, nhưng giữ đặc tả để không phụ thuộc một người. LoRa dùng explicit header, CRC phần cứng bật; khung ứng dụng 44 byte little-endian, CRC16/CCITT-FALSE (poly 0x1021, init0xffff) trên byte 0..41. Giá trị uint16 65535 nghĩa là thiếu ở distance/fill/battery.

| Offset | Số byte | Nội dung |
|---|---|---|
| 0 | 2 | ASCII SW |
| 2 | 1 | Version=1 |
| 3 | 1 | Kind=1 telemetry, 2 ACK |
| 4, 8, 12, 16 | Mỗi trường 4 | device_number, boot_id, seq, sample uptime_s |
| 20, 22, 24 | Mỗi trường 2 | distance_mm, fill_x10, battery_mv |
| 26, 27 | Mỗi trường 1 | reason enum 0..5; quality enum 0..4 theo thứ tự trong Protocol.h |
| 28 | 1 | Bit0 alarm active; bit1 lid known; bit2 lid open; bit3 alarm known |
| 29 | 1 | valid_samples |
| 30, 32 | Mỗi trường 2 | config_rev; dropped_reports |
| 34, 35, 36 | Mỗi trường 1 | Firmware major/minor/patch |
| 37 | 1 | Reserved=0 |
| 38 | 4 | sample_age_s, cập nhật khi retransmit |
| 42 | 2 | CRC16 ứng dụng |

ACK radio sao chép frame và đổi kind=2/CRC; node so device+boot+seq. ACK này chưa có key/xác thực; chỉ phù hợp cho prototype thử nghiệm có kiểm soát. `Protocol.h` là nguồn thực thi; mọi sửa đổi wire cần tăng phiên bản và đồng bộ hai sketch.
