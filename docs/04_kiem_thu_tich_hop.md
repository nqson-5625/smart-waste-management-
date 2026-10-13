# 04. Kiểm thử, nghiệm thu và tích hợp

## 1. Kiểm tra trong môi trường phát triển

Chạy kiểm tra logic C++ trên máy có g++: `g++ -std=c++17 -Wall -Wextra -Werror -pedantic tests/core_test.cpp -o core_test`, rồi chạy `./core_test`. Kiểm tra dùng trực tiếp Logic.h/Protocol.h của sketch, không phải một bản mô phỏng lại công thức.

Sau khi cài requirements của iot-ingestion, chạy `python tests/check_contract.py`. Chương trình kiểm tra JSON Schema, fixture, các trường sai, quan hệ ID/time và việc các header dùng chung còn đồng nhất. Chạy `bash scripts/compile_all.sh` hoặc Verify riêng 3 sketch trong IDE để kiểm tra biên dịch đúng ESP32-C3. Kiểm tra logic host không thay thế biên dịch Arduino hay kiểm thử phần cứng.

Kết quả thực sự đã chạy khi soạn gói được ghi ở `VALIDATION.md`. Các hàng checklist bên dưới là **việc cần thực hiện**, không phải kết quả đã đo sẵn.

## 2. Checklist nghiệm thu trên bàn

| ID | Thao tác | Kết quả mong đợi / bằng chứng cần lưu |
|---|---|---|
| H01 | Đo rail khi chưa gắn board và lúc phát | Node/radio 3,3 V; cảm biến 5 V; rail không sụt gây reset |
| H02 | Đo mức Echo sau chia áp | Trong giới hạn GPIO; ảnh mạch và giá trị điện trở |
| H03 | Nạp Diagnostics, đặt mặt phẳng cách 300/500/1.000 mm | Log 7 mẫu, trung vị gần giá trị thực; mục tiêu ban đầu ±20 mm trên bàn ở điều kiện ổn định, phải xác nhận thực nghiệm |
| H04 | Rỗng/đầy và 25/50/75/85% | Ghi mốc thật; mục tiêu ban đầu sai số mức đầy <=5 điểm phần trăm trên vật thử phù hợp |
| H05 | Đưa tay thoáng qua một lần trong chu kỳ | Không bật cảnh báo từ một chu kỳ high đơn lẻ |
| H06 | Thay đổi vật cản thất thường | quality=unstable/timeout khi không đủ mẫu; không gửi 0% giả |
| H07 | Mở nắp có reed | quality=lid_open, fill=null; đóng ổn định mới được đo lại |
| H08 | Tháo sensor/cắt dây Echo | Timeout có giới hạn; fault sau 3 chu kỳ; phần truyền không bị kẹt vì pulseIn |
| F01 | Giữ mức 80,0% qua nhiều chu kỳ | Không tạo full chỉ vì bằng 80,0% |
| F02 | Giữ mức 85% hai chu kỳ | Có reason=full, alarm_active=true; đo thời gian từ thay vật đến MongoDB |
| F03 | Hạ xuống 75% khi đang đầy | Alarm vẫn true |
| F04 | Hạ <=70% hai chu kỳ | reason=cleared, alarm_active=false |
| F05 | Một chu kỳ 85%, một invalid, một 85% | Chưa full; chuỗi xác nhận bị ngắt bởi invalid |
| F06 | Reset node khi Backend đang có cảnh báo | boot tăng; bản boot alarm=null không xóa cảnh báo |
| R01 | Hai radio cùng cấu hình, gắn anten | Gateway thấy PERSISTED và Node nhận ACK |
| R02 | Tắt gateway | Node thử hữu hạn mỗi phiên, backoff và vẫn deep sleep; theo dõi pending |
| R03 | Cho node tạo >4 báo cáo khi mất gateway | Bỏ cũ nhất, dropped_reports tăng; không gọi đây là bảo toàn lịch sử |
| M01 | Chạy IoT ingestion + simulator | 9 nhận, 7 raw duy nhất; ACK duplicate; ghi log và truy vấn MongoDB |
| M02 | Ngắt MongoDB | Không có ACK stored; gateway giữ bản tin và phát lại |
| M03 | Ngắt Wi-Fi gateway, vẫn phát node | Queue tăng tới giới hạn; khôi phục mạng thì drain, không nhân đôi Mongo |
| M04 | Tắt nguồn gateway khi đang có queue | Sau bật lại còn bản đã commit NVS; không Erase All Flash |
| M05 | Chặn ACK từ IoT ingestion sau commit | Lần gửi lại chỉ tạo duplicate; không tạo thêm cảnh báo |
| M06 | Gửi bản seq cũ sau seq mới | Có raw lịch sử, latest không lùi |
| M07 | Gửi cùng ID nhưng khác nội dung node | Quarantine/log; không ghi đè và không ACK thành công |
| M08 | Bỏ NTP/đặt sai CA | LoRa vẫn nhận; TLS không được bỏ xác minh; dữ liệu unsynced không bị gán giờ giả |
| M09 | Tắt gateway đột ngột | Có LWT/timeout; không tự đánh dấu mọi thùng rỗng |
| P01 | Tắt debug, tháo USB, đo đầu pin | Bảng dòng ngủ/đo/phát/chờ ACK/retry theo thời gian |
| P02 | Tắt nguồn sensor bằng GPIO3 | Xác nhận cảm biến và boost hết dòng hoạt động, không bị cấp lén qua chân tín hiệu |

Đối với R02, cũng kiểm tra lỗi module radio/nguồn/SPI. Thư viện LoRa dùng chờ phát đồng bộ; phần v1 chưa bổ sung watchdog phục hồi riêng cho lỗi radio vật lý gây kẹt TX. Nếu gặp kẹt khi lỗi phần cứng, phải bổ sung đường watchdog/reset đã kiểm thử trước khi vận hành không giám sát; không suy ra rằng retry ứng dụng bao phủ mọi lỗi chip radio.

## 3. Kiểm tra ngoài thực địa và quy mô

Lắp thử 1-3 thùng, ghi khoảng cách, vật cản, vị trí anten, RSSI/SNR, tỷ lệ báo cáo đến được Backend, latency và thời gian mất kết nối. Không chốt phạm vi phủ sóng chỉ bằng quảng cáo radio. Thử trong điều kiện nắp đóng, gần kim loại, xe đi qua, thời tiết phù hợp; kiểm tra kín nước/ngưng tụ và chịu va đập bằng quy trình của Hardware.

Với 200 thùng và 4 báo cáo/thùng/ngày, tải nền khoảng 800 bản tin/ngày, chưa gồm boot/sự kiện/retry. Queue 32 bản của gateway chỉ chứa khoảng 0,96 giờ tải nền nếu mọi node cùng dùng gateway và tốc độ đều; burst đồng loạt có thể đầy nhanh hơn nhiều. Con số tải nền nhỏ không chứng minh radio một kênh đáp ứng được 200 node. Cần thử va chạm, gateway half-duplex khi ACK, thời gian chiếm kênh, vùng phủ và sự kiện đồng thời; ưu tiên nâng lên kiến trúc LPWAN chuẩn đã nêu.

Backend có thể kiểm tra 200 định danh giả lập, độc lập với thử RF: unique key đúng, đủ raw, projection không lùi, duplicate không tăng cảnh báo, hàng đợi xử lý không tăng vô hạn, truy vấn có index. Load test MQTT không được trình bày thành kết quả phủ sóng 200 thùng thật.

Pin: lập bảng mAh/ngày bằng đo tại đầu pin, gồm số lần đo, báo định kỳ, sự kiện, ACK và lỗi mạng. Dùng dung lượng khả dụng đã đo/dự phòng, tính tuổi thọ và kiểm tra suy giảm nhiệt độ/tự xả. Chỉ nghiệm thu 12 tháng khi mô hình năng lượng có số đo và biên dự phòng phù hợp; kế hoạch đo dài hạn có thể xác nhận thêm. Thử ngoài trời cần phần cứng phù hợp trước.

## 4. Ranh giới trách nhiệm

| Firmware & IoT phụ trách | Hardware phụ trách | Backend phụ trách |
|---|---|---|
| 3 sketch, MQTT, ingestion ghi MongoDB và ACK sau commit | Schematic/pinout, ảnh dây đúng bản lắp | Query telemetry và device registry trực tiếp từ MongoDB |
| Giao thức radio v1, topic/schema MQTT và vận hành broker | Rail nguồn, Echo level shifting, mạch ngắt sensor | Registry device/gateway và metadata vị trí trong MongoDB |
| Mốc hiệu chuẩn, config_rev và log lỗi/retry | Số đo dòng/tổn hao pin; thử môi trường | Query bản ghi mới nhất/lịch sử theo device và thời gian |
| FW hash/bản build đã Verify và log nạp | Điểm đặt gateway và nguồn/Internet | Kết quả query theo nhu cầu phần ứng dụng |
| Danh sách giới hạn/việc chưa làm, broker config/ACL | Đánh giá quy định RF/công suất/anten | Quyền query MongoDB và yêu cầu dữ liệu cho API |

## 5. Tích hợp đầu cuối

Firmware & Kết nối IoT duy trì `firmware/` và `iot-ingestion/`: gateway publish MQTT, ingestion ghi MongoDB và ACK sau commit. Backend dùng helper trong `backend/` để query MongoDB trực tiếp. Dùng tài liệu 03 làm contract dữ liệu chung; hai nhóm làm song song trên cùng database. Không commit credential thật trong `Secrets.h`.

Tích hợp được xác nhận khi thiết bị tạo raw trong MongoDB, IoT ingestion chỉ ACK sau commit, lỗi DB không làm mất queue, Backend query được lịch sử/latest, latest không lùi và API trả null/quality/freshness đúng.

## 6. Phạm vi hiện có

Repository có: 3 sketch Arduino theo cấu trúc IDE; pin map cho hai ESP32-C3; hướng dẫn điện áp/nguồn và các thiếu hụt BOM; bộ lọc/hiệu chuẩn/ngưỡng; LoRa P2P và ACK; queue RTC/NVS; MQTT TLS và application ACK; schema/fixture; simulator và IoT ingestion; query helpers cho Backend; cấu hình Compose cho môi trường phát triển; kế hoạch nghiệm thu và mở rộng.

Đã kiểm tra trong môi trường soạn: ghi riêng ở VALIDATION.md. Chưa có phần cứng thật để xác nhận pin, RF, phép đo, deep sleep, TLS broker thực hay độ bền. Chưa triển khai LoRaWAN/NB-IoT, OTA, downlink config, đo pin bằng ADC, cân khối lượng, GPS, web/app hay thuật toán tối ưu tuyến. Những phần này không được ngầm coi là đã có trong firmware v1.

Backend có thể query trực tiếp các collection MongoDB bằng helpers đã có. Firmware & IoT phụ trách broker, MQTT ingestion, registry phát triển, chống trùng và ACK sau ghi bền vững. Endpoint/credential triển khai và kết quả đo thực tế cần được cấu hình theo môi trường sử dụng.
