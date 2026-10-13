# 02. Đấu nối ESP32-C3, cài Arduino IDE và nạp mã

## 1. Kiểm tra linh kiện trước khi đấu

Đọc chữ trên radio: **Ra-01H, SX1276**, không thay bằng Ra-01/SX1278 hoặc Ra-01SH/SX1262 rồi giữ nguyên code. Ai-Thinker công bố Ra-01H thuộc dải 803-930 MHz [R2]. Board phải là **ESP32-C3 Super Mini** như BOM. Các số trong bảng là **GPIO**, không phải số thứ tự chân trên hàng cắm.

Thử ban đầu bằng USB, chưa nối pin 18650. Rút nguồn khi thay dây. Gắn anten đúng dải vào radio trước khi phát. Đặt hai bộ cách nhau vài mét khi thử, tránh sát nhau. Đo nguồn bằng đồng hồ trước khi cắm ESP32/radio.

BOM gốc còn thiếu phần cấp 5 V phù hợp HC-SR04 chuẩn và phần hạ mức Echo. HT7333 3,3 V không tạo ra 5 V. Đừng cấp HC-SR04 chuẩn bằng 3,3 V rồi coi lỗi đo là lỗi phần mềm; cũng không coi module có nhãn HC-SR04 nào cũng hỗ trợ 3,3 V. Hướng dẫn này chọn bản 5 V [R7].

## 2. LoRa - đấu giống nhau trên cả Node và Gateway

| Chân Ra-01H | ESP32-C3 | Ghi chú |
|---|---|---|
| VCC/3V3 | Rail 3,3 V ổn định | Tuyệt đối không cấp 5 V vào radio |
| GND, các pad GND | GND chung | Node/radio chung mass; tương tự phía gateway |
| SCK | GPIO4 | SPI clock |
| MISO | GPIO5 | Radio -> ESP32 |
| MOSI | GPIO6 | ESP32 -> radio |
| NSS/CS | GPIO7 | Nên kéo lên 3,3 V bằng 10 kOhm |
| NRESET/RST | GPIO10 | Nên kéo lên 3,3 V bằng 10 kOhm |
| DIO0..DIO5 | Không nối | Code polling, không gọi onReceive/onTxDone |
| ANT | Anten phù hợp module/dải tần | Không nối ANT vào GPIO |

Đặt tụ 100 nF song song tụ khoảng 100 microfarad gần VCC-GND radio, dây SPI ngắn. Radio có dòng phát xung; thiết kế rail đủ cả ESP32 và radio, kiểm tra sụt áp tại lúc phát. Gateway có Wi-Fi nên cần nguồn 3,3 V đủ dòng đỉnh và tản nhiệt. Nếu dùng AMS1117 từ 5 V, Hardware phải kiểm tra công suất nhiệt; không ghép song song đầu ra AMS1117 với regulator trên board. Thư viện lưu ý nguồn riêng cho radio có khả năng đáp ứng dòng phát tối thiểu khoảng 120 mA trong cấu hình liên quan [R3]. Đây chưa phải tổng dòng yêu cầu của cả gateway.

Bảng này tránh GPIO2/8/9 là chân strapping và GPIO18/19 dùng USB của ESP32-C3 [R1]. Nếu board clone bố trí/ghi tên khác, bám theo GPIO và schematic đúng board, không bám hình một board khác trên mạng.

## 3. HC-SR04 - chỉ đấu tại Node

| HC-SR04 | Kết nối | Mục đích |
|---|---|---|
| VCC | 5 V USB trong chế độ thử | Chưa dùng mạch pin |
| GND | GND chung Node | Bắt buộc chung mass |
| TRIG | GPIO0 | Code xuất xung 10 microsecond |
| ECHO | Qua cầu chia áp tới GPIO1 | Không nối Echo trực tiếp |

**Cầu chia áp:** Echo -> điện trở 1 kOhm -> điểm giữa -> GPIO1; từ điểm giữa -> điện trở 2 kOhm -> GND. Tại Echo 5 V, điện áp điểm giữa lý tưởng là `5 × 2/(1+2) = 3,33 V`. Chọn điện trở dung sai 1%, dùng rail 5 V ổn định và xác nhận biên độ thực tế. ESP32 không phải ngõ vào chịu 5 V. Nếu nguồn/linh kiện không bảo đảm mức vào, dùng bộ chuyển mức logic phù hợp thay cho cầu chia áp.

TRIG 3,3 V thường dùng được với đầu vào TTL của module; nếu module cụ thể không nhận ổn định, Hardware thêm buffer chuyển 3,3 -> 5 V loại có đầu vào tương thích 3,3 V (ví dụ họ HCT), đối chiếu datasheet linh kiện đã mua. Không kéo GPIO0 lên 5 V.

Không dùng GPIO để cấp trực tiếp nguồn HC-SR04. Mặc định `PIN_SENSOR_POWER=-1`, nghĩa là nguồn cảm biến luôn bật trong thử USB. Đây không phải cấu hình nghiệm thu pin.

## 4. Nguồn pin và công tắc nguồn cảm biến

Hardware thực hiện sơ đồ sau theo đúng cực, pinout và thông số của linh kiện thực tế:

- Cell 18650 đúng loại -> B+/B- của module sạc/bảo vệ TP4056; lấy tải tại OUT+/OUT- theo module có bảo vệ. Đầu vào sạc 5 V đi đúng cổng IN+/IN-, không đi vào B+/B-.
- OUT+ -> nguồn ổn áp 3,3 V -> ESP32-C3 và Ra-01H. OUT- là GND chung. Pin đầy có thể đạt 4,2 V, không nối trực tiếp vào chân 3V3.
- Nhánh cảm biến: OUT+ -> Source AO3401 -> Drain -> VIN bộ boost 5 V -> VCC HC-SR04. Gate AO3401 kéo về Source qua 100 kOhm để mặc định tắt.
- Dùng NPN (ví dụ 2N3904 theo đúng datasheet/pinout bản mua): collector nối Gate AO3401, emitter về GND, base nhận GPIO3 qua 10 kOhm, base kéo GND qua 100 kOhm. GPIO3 HIGH bật NPN, kéo gate thấp, bật nhánh boost; GPIO3 LOW/tắt nguồn MCU thì nhánh cảm biến tắt.
- Kiểm tra chiều diode thân MOSFET, điện áp VGS, dòng boost, thời gian khởi động và dòng rò. Không điều khiển trực tiếp gate P-MOSFET ở rail pin/5 V bằng GPIO3 nếu mức logic không bảo đảm tắt hoàn toàn.

Sau khi đo được nhánh cảm biến thực sự tắt/bật đúng, đổi `PIN_SENSOR_POWER=3` trong **cả SensorDiagnostics/Config.h và WasteNode/Config.h**. BJT và điện trở kéo xuống giữ trạng thái tắt khi ESP32 vào deep sleep/reset, tránh phụ thuộc GPIO thả nổi.

HT7333 trong BOM cần được kiểm tra dropout, dòng đỉnh và nhiệt với cả node/radio; vùng pin thấp có thể không giữ được rail 3,3 V. Super Mini còn LED/regulator trên board; không được lấy dòng ngủ của chip ESP32-C3 thay cho dòng ngủ toàn board. Nếu cấp ngoài vào 3V3, kiểm tra schematic để không cấp ngược qua regulator/USB. Khi nạp bằng USB, dùng cấu hình nguồn đã được Hardware xác nhận, không tự ghép hai nguồn đầu ra.

TP4056 thông dụng không mặc nhiên có quản lý đường nguồn vừa sạc vừa cấp tải. Trong thử nghiệm hãy tách bước sạc và chạy pin, hoặc dùng thiết kế power-path đã được kiểm tra. Dùng cell và module bảo vệ phù hợp; kiểm tra dòng sạc của module theo cell.

Vật tư cần bổ sung/đối chiếu so với BOM: boost 5 V có dòng nghỉ phù hợp; NPN; điện trở Echo 1 kOhm/2 kOhm; điện trở điều khiển MOSFET/kéo chân; tụ; hộp và đầu nối chống nước; cảm biến nắp nếu dùng. Giá 486.000 đồng là ước tính trong tài liệu gốc, chưa tính phần bổ sung và không phải báo giá hiện tại.

## 5. Cảm biến nắp và lắp cơ khí

Tùy chọn reed switch: một chân GPIO20, chân kia GND; chọn vị trí nam châm để nắp **đóng** thì tiếp điểm kín. Thêm kéo lên 3,3 V 10 kOhm nếu dây dài; code cũng dùng INPUT_PULLUP. Đổi `PIN_LID=20` ở hai Config của Node/Diagnostics. GPIO20 không dùng làm UART khi cấu hình này bật; Serial Monitor dùng USB CDC.

Gắn cảm biến tại vị trí cố định, hướng vuông góc về vùng rác đại diện, tránh thành thùng, gân, bản lề và vùng người đưa tay vào. Nên gắn trên khung cố định để việc mở nắp không đổi hướng đo. Mốc rỗng là khoảng cách từ mặt cảm biến đến đáy; mốc đầy là khoảng cách đến mức rác tối đa cho phép, vẫn ngoài vùng mù cảm biến. Rác nghiêng, mềm/xốp, túi lồi, giọt nước đều có thể gây sai số.

HC-SR04 hở là cảm biến thử nghiệm trong prototype này. Muốn ngoài trời cần cảm biến phù hợp môi trường, gá chống rung, hộp, đầu nối và quản lý nước ngưng. Nếu đổi sang module chống nước có giao diện/điện áp khác, phải sửa driver và hiệu chuẩn; không mặc định thay chân là chạy.

## 6. Cài Arduino IDE và thư viện

1. Cài Arduino IDE 2.x từ trang chính thức Arduino. Chuẩn bị cáp USB có dây dữ liệu, không chỉ cáp sạc.
2. Mở File -> Preferences; tại Additional Boards Manager URLs thêm `https://espressif.github.io/arduino-esp32/package_esp32_index.json` theo hướng dẫn Espressif [R5].
3. Tools -> Board -> Boards Manager, tìm **esp32 by Espressif Systems**, chọn **3.3.1** làm baseline của gói này. Không chọn nhầm gói “Arduino ESP32 Boards”.
4. Chọn Tools -> Board -> esp32 -> **ESP32C3 Dev Module**. Chọn đúng cổng COM/tty sau khi cắm từng board. Bật **USB CDC On Boot = Enabled**; Flash Size theo board thật (Super Mini thường được bán bản 4 MB, cần xác nhận); partition mặc định có NVS; CPU mặc định; Upload Speed 115200 khi cần ổn định. Không bật Erase All Flash trong mỗi lần nạp.
5. Sketch -> Include Library -> Manage Libraries, cài đúng tác giả và phiên bản trong bảng dưới. Đây là baseline có chủ ý, không tuyên bố là các bản mới nhất.
6. Mở đúng `.ino`, bấm Verify trước, rồi Upload. Serial Monitor 115200 baud. Gateway cần nối Wi-Fi 2,4 GHz; ESP32-C3 không kết nối mạng chỉ có 5 GHz.

| Phụ thuộc | Tác giả/gói | Phiên bản baseline | Sketch dùng |
|---|---|---|---|
| ESP32 Arduino core | Espressif Systems | 3.3.1 | Cả ba |
| LoRa | Sandeep Mistry | 0.8.0 | WasteNode, WasteGateway |
| ArduinoJson | Benoit Blanchon | 7.4.2 | WasteGateway |
| PubSubClient | Nick O'Leary | 2.8 | WasteGateway |
| Arduino.h, SPI, WiFi, WiFiClientSecure, Preferences, esp_sleep, FreeRTOS | Có trong ESP32 core | Theo core | Không cài bản trùng trong Library Manager |
| Driver HC-SR04 | Sensor.h dùng pulseIn | Có sẵn trong gói | Không cần NewPing/Ultrasonic |

PubSubClient được ghim cho mẫu Arduino này; trang dự án hiện ghi không còn được duy trì [R4]. Khi chọn nền tảng sản xuất, Firmware & IoT cần đánh giá client MQTT được duy trì, TLS và cơ chế xác nhận tương ứng, giữ nguyên hợp đồng JSON nếu có thể.

Nếu Upload báo “Failed to connect”: giữ BOOT, bấm rồi thả RESET, thả BOOT, chọn lại cổng và Upload. Sau nạp có thể cần bấm RESET để chạy. USB CDC có thể đổi cổng sau reset/deep sleep. Node không đợi Serial kết nối nên có thể bỏ lỡ log đầu; dùng sketch Diagnostics khi hiệu chuẩn. Gateway chạy liên tục, không deep sleep.

## 7. Nạp và hiệu chuẩn theo thứ tự

### A. SensorDiagnostics

Mở `firmware/SensorDiagnostics/SensorDiagnostics.ino`. Cấp 5 V cho sensor theo bảng, Verify và Upload. Log `raw_mm` có 7 số; 0 là timeout. `distance_mm=65535` và `fill_x10=65535` chỉ là sentinel ở log/khung nhị phân, khi lên JSON sẽ là null.

Đặt thùng rỗng, ghi khoảng cách ổn định từ ít nhất 10 nhóm đo; chọn giá trị trung tâm làm EMPTY_DISTANCE_MM. Đặt mặt phẳng tại mức đầy thiết kế, lấy FULL_DISTANCE_MM tương tự. Cập nhật mốc ở cả Node và Diagnostics, tăng CONFIG_REV khi thay hiệu chuẩn, ghi vào registry MongoDB. Kiểm tra tại 0/25/50/75/85/100% độ cao hữu dụng; mức phần trăm theo chiều cao không nhất thiết bằng phần trăm thể tích ở thùng không có tiết diện đều.

### B. WasteGateway

Mở `firmware/WasteGateway/WasteGateway.ino`. Trong Secrets.h điền SSID/password, MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD và PEM root CA do người vận hành broker cung cấp. Dùng hostname có trong chứng thư, không tự thay bằng IP nếu chứng thư không chứa IP đó. USE_TLS=true, port8883 mặc định; firmware không gọi setInsecure. Cần DNS và NTP để kiểm tra thời hạn chứng thư; nếu chưa có thời gian hợp lệ gateway tiếp tục nhận LoRa nhưng chưa kết nối MQTT TLS.

Để thử LAN kín: đặt USE_TLS=false và MQTT_PORT=1883, dùng IP LAN của máy broker; `localhost` trên ESP32 là chính ESP32, không phải laptop. Cho phép cổng broker trong firewall và bảo đảm hai máy cùng mạng. Không dùng cấu hình không TLS này cho Internet. Mật khẩu mẫu là placeholder, phải thay; file Secrets.h thật không đưa lên kho mã công khai.

Đợi Serial có `READY gw-001`. Kiểm tra status online trên MQTT broker. `MQTT connect state=-2` thường cần kiểm tra host/cổng/đường mạng; `4/5` cần kiểm tra tài khoản/quyền; lỗi TLS cần kiểm tra giờ, CA, hostname và chuỗi chứng thư. Không xử lý lỗi chứng thư bằng tắt xác minh TLS.

### C. WasteNode

Mở `firmware/WasteNode/WasteNode.ino`; đặt DEVICE_NUMBER=1 cho bin-001, mốc hiệu chuẩn và chân đúng mạch. Gateway ALLOWED_DEVICE_NUMBERS phải chứa 1; registry MongoDB phải có bin-001 -> gw-001. Nạp rồi quan sát `QUEUED ...`, `ACK gateway persisted`, `SLEEP ...`. Gateway in `PERSISTED ...`; sau khi IoT ingestion lưu thành công vào MongoDB, in `MONGODB STORED ...`.

Để demo nhanh có thể đặt SAMPLE_INTERVAL_S=5 và REPORT_INTERVAL_S=60 trong Node, đồng bộ thông số demo với người phụ trách ingestion. Ngưỡng cần giữ vật thể qua hai lần đo. Trước nghiệm thu đổi về 60/21600. Không sửa giảm chu kỳ rồi báo là đã đạt ngân sách pin chính thức.

Muốn thêm node: cấp DEVICE_NUMBER mới, thêm allowlist gateway và registry MongoDB trước khi nạp. Không clone nguyên ID. Không xóa NVS của node đang dùng rồi giữ nguyên ID: boot_id có thể lặp và ingestion sẽ coi dữ liệu mới là trùng. Nếu phải xóa toàn flash, cấp định danh thiết bị mới hoặc thực hiện quy trình reprovision có thay namespace/version; không âm thầm giữ ID cũ.

## 8. Công cụ dòng lệnh tùy chọn

Nếu đã cài Arduino CLI, chạy `bash scripts/compile_all.sh` ở Linux/macOS/WSL để tải baseline và compile ba sketch. Script chỉ compile, không upload. Với Arduino IDE, thao tác Verify ở mỗi sketch là tương đương về mục đích kiểm tra biên dịch. Ghi phiên bản thực tế và kết quả build vào biên bản; repository không kèm `.bin` đã được xác minh trên board thật.
