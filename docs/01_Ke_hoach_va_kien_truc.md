# 01. Kế hoạch thực hiện và quyết định kỹ thuật

## 1. Yêu cầu lấy từ hai tài liệu

Nguồn nội bộ: “Dự án thu gom rác thông minh.pdf”, 6 trang, tương ứng slide 50-55; và “Giới thiệu tổng quan hệ thống(1).pdf”, 3 trang. Tài liệu thứ hai phân công Firmware & Kết nối IoT cho Nguyễn Quang Sơn.

| Yêu cầu | Cách xử lý trong bộ mã | Mức hoàn thành cần hiểu đúng |
|---|---|---|
| Đo mức đầy theo % | 7 mẫu khoảng cách, lọc ngoại lai, hiệu chuẩn 2 mốc | Có mã và kiểm tra logic; cần hiệu chuẩn thùng thật |
| 4 báo cáo/ngày | Một báo cáo mỗi 21.600 giây theo đồng hồ RTC | Chu kỳ tương đối từ lúc bật máy, không cố định 00h/06h/12h/18h |
| Báo khi vượt 80% | Hai chu kỳ hợp lệ liên tiếp >80%; phát ngay sau khi xác nhận | Với đo mỗi 60 giây: khoảng 60-120 giây cộng thời gian xử lý/truyền khi đường truyền tốt |
| MQTT + MongoDB | Gateway publish MQTT; dịch vụ IoT ingestion xác thực, ghi MongoDB rồi ACK | Backend chỉ query dữ liệu đã lưu |
| Pin ít nhất 12 tháng | Deep sleep, không bật Wi-Fi tại node, radio chỉ bật khi gửi | Chưa đạt nghiệm thu; BOM và chu kỳ đo cần đo điện thực tế |
| Ngoài trời/chịu va đập | Tách yêu cầu cơ khí, nguồn và cảm biến | HC-SR04 hở không đáp ứng bằng việc chỉ đổi firmware |
| Ít nhất 200 thùng | Định danh, payload và Backend có đường mở rộng | Cầu LoRa một kênh hiện tại chưa được kiểm chứng cho 200 node |
| Hiệu quả nghiệp vụ | Backend lưu sự kiện thu gom, tuyến và quãng đường | Không thể suy ra km giảm hay kg rác chỉ từ số gói MQTT |

Tài liệu gốc loại Wi-Fi ở từng thùng do không có phủ sóng ngoài địa bàn. Wi-Fi trong bộ mã chỉ dùng tại **gateway đặt ở nơi có nguồn và Internet**. Không có mâu thuẫn giữa hai lựa chọn này.

## 2. Kiến trúc và giới hạn

Một thùng: HC-SR04 -> ESP32-C3 node -> Ra-01H. Tại điểm tập trung: Ra-01H -> ESP32-C3 gateway -> Wi-Fi 2,4 GHz -> MQTT broker -> dịch vụ IoT ingestion -> MongoDB -> Backend query/API -> Web/App. Phần MQTT đến khi bản ghi được lưu bền vững và ACK thuộc Firmware & Kết nối IoT; Backend đọc trực tiếp MongoDB.

Hai Ra-01H hiện có là hai radio đơn, dùng LoRa P2P cùng tần số và cấu hình. Thư viện LoRa của Sandeep Mistry điều khiển radio trực tiếp, không tự cung cấp LoRaWAN, mã hóa, xác thực hay kiểm soát duty cycle [R3]. Vì vậy ghi trong báo cáo là **“bản mẫu dùng LoRa P2P để kiểm chứng luồng dữ liệu; hướng triển khai LPWAN dùng LoRaWAN hoặc NB-IoT”**.

Để triển khai LoRaWAN: cần gateway concentrator nhiều kênh phù hợp, network server/application server, stack LoRaWAN trên node, khóa riêng từng node và kế hoạch vùng tần số. Cầu ESP32 + một SX1276 không thay thế được concentrator đó. Nếu dùng NB-IoT cần thêm modem, SIM/gói dịch vụ, kiểm tra vùng phủ và dòng phát; không thể thực hiện chỉ bằng hai ESP32-C3 hiện có. Backend giữ được phần JSON chuẩn hóa; một adapter đầu vào mới chuyển dữ liệu LPWAN sang schema v1.

## 3. Thứ tự công việc và đầu ra

Thời lượng dưới đây là gợi ý ngày công, phụ thuộc việc linh kiện và broker đã sẵn sàng.

| Thứ tự | Người Firmware làm | Điều kiện hoàn tất | Backend làm song song |
|---|---|---|---|
| 1 - buổi đầu | Chốt hợp đồng v1, ID bin-001/gw-001, pin và thông số | Gửi tài liệu 03, schema, fixture, simulator | Dựng các query MongoDB trực tiếp |
| 2 - buổi đầu | Kiểm tra đúng C3, đúng Ra-01H/SX1276, nguồn và mức logic với Hardware | Đo rail 3,3 V/5 V, đấu dây đã kiểm tra | Xác nhận cách query telemetry và registry |
| 3 - ngày 1 | Cài IDE, core, thư viện; nạp SensorDiagnostics | Khoảng cách ổn định, không reset khi đo | Query collection telemetry và devices trực tiếp |
| 4 - ngày 1 | Hiệu chuẩn rỗng/đầy; gắn cảm biến cố định | Ghi EMPTY/FULL, tăng config_rev, thử vật cản/nắp | Query metadata thiết bị theo ID |
| 5 - ngày 2 | Nạp Gateway rồi Node, kiểm tra LoRa, MQTT và ACK sau MongoDB | Có bản ghi thật trong MongoDB, queue về 0 | Đọc trực tiếp bản ghi để tích hợp API |
| 6 - ngày 2 | Thử ngưỡng, timeout, đứt mạng, mất nguồn, trùng gói | Checklist tích hợp đạt, ghi bằng chứng | Query lịch sử và bản ghi mới nhất theo device |
| 7 - ngày 3+ | Bật mạch ngắt nguồn cảm biến, tắt log, đo dòng và RSSI/SNR ngoài thực địa | Có bảng mAh/ngày, thử vùng phủ, thời gian mất kết nối | Thử tải đầu vào 200 ID và theo dõi hàng đợi |
| 8 - trước tích hợp | Khóa phiên bản, lưu sơ đồ/ảnh/cấu hình và kết quả | Hoàn thành checklist tích hợp ở tài liệu 04 | Cung cấp dữ liệu query cho phần ứng dụng |

Không đợi hoàn thiện mạch mới chốt schema và cách query MongoDB. Ingestion sở hữu ACK sau ghi bền vững; Backend làm trên dữ liệu đã có trong DB.

## 4. Thuật toán đo và trạng thái

Mỗi chu kỳ: bật nguồn cảm biến nếu có mạch điều khiển, chờ 100 ms, đo 7 lần. Xung TRIG 10 microsecond; Echo có timeout 30 ms; khoảng nghỉ sau từng lần 70 ms. Khoảng cách đổi theo vận tốc âm giả định 343 m/s, chưa bù nhiệt độ.

Bỏ mẫu ngoài 20-4.000 mm và timeout. Cần ít nhất 5 mẫu hợp lệ; lấy trung vị, giữ mẫu lệch không quá max(30 mm, 5% trung vị); cần ít nhất 5 mẫu sau lọc. Nếu khoảng cách còn lớn hơn mốc rỗng 150 mm thì báo out_of_range. Dữ liệu không hợp lệ gửi `distance_mm=null`, `fill_pct=null`; không giả thành 0%.

Công thức: `fill_pct = clamp(100 × (EMPTY_DISTANCE_MM - distance_mm) / (EMPTY_DISTANCE_MM - FULL_DISTANCE_MM), 0, 100)`. Bộ mã lưu độ phân giải 0,1%, cắt phần lẻ nhỏ hơn 0,1%. Ví dụ mốc 1.000/100 mm: 1.000 mm -> 0%; 550 mm -> 50%; 235 mm -> 85%; 100 mm -> 100%.

Hai chu kỳ liên tiếp có chất lượng ok và mức đầy >80% bật alarm. Hai chu kỳ ok <=70% tắt alarm. Khoảng 70-80% giữ trạng thái để tránh bật/tắt liên tục. Đúng 80,0% không kích hoạt vì yêu cầu là “vượt 80%”. Mẫu lỗi làm đứt chuỗi xác nhận, không xóa trạng thái đầy đã biết.

Sau cold boot, `alarm_active=null` đến khi xác nhận hai lần >80% hoặc hai lần <=70%. Backend giữ trạng thái cảnh báo đã biết nếu nhận null. Đây là cách tránh một lần khởi động lại làm mất cảnh báo đang mở. Hai lần <=70% đầu tiên có thể tạo sự kiện cleared dù chưa từng có cảnh báo; Backend chỉ cần cập nhật trạng thái, không tạo một lần thu gom giả.

Lỗi cảm biến liên tục 3 chu kỳ tạo sensor_fault; phục hồi 2 chu kỳ ok tạo sensor_recovered. Báo cáo boot/định kỳ vẫn phản ánh chất lượng hiện tại. Nếu nhiều lý do xảy ra cùng chu kỳ, ưu tiên full/cleared, rồi fault/recovered, rồi boot/periodic. Bản tin sự kiện thay báo cáo định kỳ trong chu kỳ đó, tránh gửi hai bản tin cùng phép đo.

Median chỉ giảm nhiễu; không chứng minh nắp đang đóng. Reed switch là bổ sung nên làm: nắp mở ở bất kỳ lần đọc nào trong nhóm sẽ làm cả nhóm invalid. Nếu chưa có reed, `lid_open=null`, không gửi false giả. HC-SR04 không đo được khối lượng, không phân loại vật liệu và không có GPS.

## 5. Chính sách truyền, lưu và năng lượng

Node đánh số `boot_id` tăng trong NVS mỗi cold boot, `seq` tăng cho mỗi báo cáo trong phiên; timer wake không tạo boot_id mới. RTC giữ trạng thái và tối đa 4 báo cáo qua deep sleep, không giữ được khi mất nguồn. Khi đầy, bỏ báo cáo cũ nhất và tăng `dropped_reports` (tối đa 65535). Không có cam kết không mất dữ liệu ở node.

Mỗi phiên gửi tối đa hai báo cáo; mỗi báo cáo tối đa 2 lần phát, chờ ACK 800 ms/lần. Có jitter 50-500 ms trước phát. Nếu không ACK, lùi lần thử kế tiếp 120/240/480/900 giây; sự kiện mới có thể thử ngay. Gateway có queue NVS 32 bản ghi. Chỉ sau khi ghi NVS thành công hoặc đã có cùng ID trong queue mới trả ACK radio. Đầy queue thì không ACK. ACK này chỉ xác nhận gateway đã nhận lưu; không phải MongoDB đã lưu.

Gateway publish QoS 0 rồi đợi **application ACK** từ dịch vụ IoT ingestion sau khi MongoDB ghi thành công. Chưa ACK thì phát lại bản ghi đầu queue mỗi 10 giây. Nhận stored/duplicate đúng ID mới xóa NVS. PubSubClient chỉ publish QoS 0 [R4]; subscribe QoS 1 không tự nâng QoS của telemetry thành 1. Cơ chế này tạo khả năng giao lại và cần chống trùng, không phải “exactly once”. Gateway mất phần cứng vĩnh viễn vẫn có thể mất dữ liệu đã ACK cho node.

Radio P2P có CRC để phát hiện lỗi truyền, **chưa có xác thực/mã hóa/chống replay**. Danh sách ID cho phép chỉ lọc vô ý, không chống giả mạo. Bản prototype này chưa đủ bảo mật để triển khai hiện trường; cần LoRaWAN/LPWAN bảo mật hoặc giao thức đã bổ sung bảo vệ. TLS chỉ bảo vệ đoạn gateway-broker. Không dùng gói CRC làm bằng chứng xác thực thiết bị.

Với pin 3.000 mAh, giả sử dùng được 80% dung lượng: ngân sách trung bình để đạt 12 tháng là `2400 / 8760 = 0,274 mA`. Ví dụ giả định toàn mạch tiêu thụ 40 mA trong 0,8 giây mỗi 60 giây và ngủ 0,02 mA: trung bình khoảng 0,553 mA, pin lý tưởng khoảng 181 ngày, còn chưa cộng truyền và tổn hao. Đây là phép ước tính minh họa, không phải số đo của bộ linh kiện.

Do đó không được kết luận “deep sleep = pin 12 tháng”. Đo ở đầu pin, gồm LED board, regulator, boost, cảm biến, radio, dòng rò và truyền lại. Có thể cần cảm biến ít điện hơn, board tối ưu, mạch nguồn tốt hơn hoặc chu kỳ đo dài hơn; kéo dài chu kỳ sẽ tăng độ trễ cảnh báo. Nếu yêu cầu gần tức thời phải thêm cơ chế đánh thức/sự kiện và đánh giá lại nguồn.

## 6. Các giả định đã chốt để lập trình

- Bộ đang dùng đúng ESP32-C3, không phải ESP32 WROOM/S3; board Super Mini của bên thứ ba phải đối chiếu nhãn GPIO thật.
- Mốc 1.000/100 mm là ví dụ, chưa phải kích thước thùng nhóm đã đo.
- Mặc định cảm biến cấp 5 V liên tục để thử USB; chế độ pin chỉ bật sau khi Hardware bổ sung mạch ngắt nguồn.
- Cấu hình tần số thử nghiệm ban đầu 920,6 MHz, SF7, BW125 kHz, CR4/5, preamble 8, sync 0x12, công suất cấu hình 10 dBm. Hai phía phải giống nhau. Quy chuẩn chính thức có phạm vi 920-923 MHz [R8]; giá trị này không tự chứng minh hợp quy, công suất EIRP hay đáp ứng thời gian chiếm kênh. Hardware phụ trách đối chiếu quy định hiện hành, anten và phép đo trước triển khai.
- “4 lần/ngày” được triển khai thành chu kỳ tương đối 6 giờ. Muốn đúng giờ lịch cần bổ sung đồng bộ thời gian xuống node/RTC phù hợp. Đồng hồ RTC nội có thể trôi theo nhiệt độ [R6].
- Pin, tín hiệu và ngưỡng chưa cấu hình từ xa. Bản này chỉ có downlink ACK, chưa có OTA hay lệnh mở nắp.
