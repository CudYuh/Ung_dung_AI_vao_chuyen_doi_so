# Hệ thống quản lý kiosks và xếp hàng VDS - SQSM v1.0

## Thông tin định giá

- ID database: 199.0
- Tên hàng hóa: Hệ thống quản lý kiosks và xếp hàng VDS - SQSM v1.0
- Loại hàng hóa: Chưa xác định
- Đơn vị tính: License/Hệ thống
- Giá thẩm định: 49.500.000 VND
- Ngày thẩm định: 28/11/2025
- Chứng thư thẩm định: 405/2025/1206/CTTĐG-VNVIC
- Nguồn dữ liệu: …
- Người thẩm định: Bùi Thị Trà Giang

## Thông số kỹ thuật

Việt Nam
Hệ thống quản lý kiosks và xếp hàng VDS - SQSM v1.0
1. Module cấu hình
- Thiết bị được lập trình tự động tắt vào thời điểm kết thúc ngày làm việc, giúp tiết kiệm điện năng và hạn chế can thiệp thủ công.
- Sau khi khởi động, kiosk sẽ tự động chạy ứng dụng tra cứu hoặc lấy số thứ tự mà không cần thao tác từ người dùng. Giao diện URL được ẩn và màn hình được khóa để ngăn chặn truy cập hoặc thao tác trái phép, đặc biệt phù hợp cho các mô hình kiosk phục vụ công cộng như tra cứu thông tin hành chính.
- Hệ thống hỗ trợ giám sát thời gian thực các chỉ số quan trọng của thiết bị như tình trạng CPU, mức sử dụng RAM, ổ cứng và kết nối mạng. Dữ liệu này được tổng hợp và hiển thị qua giao diện dashboard trực quan.
- Cho phép cấu hình mở URL hiển thị chỉ định.
- Cho phép cấu hình phát nội dung quảng báo chờ khi không có thao tác.
- Giao diện quản trị cấu hình tham số thiết bị....
- Cấu hình tùy chỉnh thiết lập số quầy theo số lượng, cách hiển thị...
2. Module hiển thị gọi số - VDS Queue Display Manager (VDS-QDM)
- Giao diện hiển thị tại màn hình quầy: Cài đặt cấu hình hiển thị cho màn hình, hiển thị số thứ tự, quầy, tên dịch vụ...
- Màn hình hiển thị trung tâm: Hiển thị tùy chỉnh số lượng quầy được cấu hình, tùy biến logo, chữ chạy..
3. Module gọi số tại quầy - VDS Queue Call Station (VDS-QCS)
- Hiển thị thông tin khách hàng đang đến lượt...
- Có các chức năng gọi lại, gọi số tiếp theo, chuyển số giữa các quầy...
- Thông báo khi có số mới trong hàng chờ qua hệ thống loa...
4. Module Tra cứu & Tìm kiếm thủ tục dịch vụ – VDS Service Lookup (VDS-SLK)
Tra cứu dịch vụ hành chính công: Cho phép người dân tra cứu thủ tục, hồ sơ, tình trạng giải quyết hoặc thông tin liên hệ; Giao diện tối ưu cho thao tác cảm ứng, hỗ trợ tìm kiếm theo tên, mã hồ sơ, hoặc mã QR.
5. Module Báo cáo & Phân tích dữ liệu – VDS Report & Analytics (VDS-RPA)
Báo cáo đa chiều: Thống kê lượng khách đến theo giờ, dịch vụ, quầy, nhân viên; Thời gian chờ trung bình, thời gian phục vụ trung bình; Tỷ lệ hoàn tất, tỷ lệ chuyển số, tỷ lệ hủy.
Tùy biến mẫu báo cáo: Cho phép người dùng chọn tiêu chí lọc và định dạng xuất (PDF, Excel, CSV).
Phân tích nâng cao: Biểu đồ thời gian thực hiển thị hiệu suất từng quầy; Cảnh báo khi phát hiện quầy tắc nghẽn hoặc thời gian chờ vượt ngưỡng.
Hỗ trợ dashboard tổng hợp: Giao diện quản trị trực quan hiển thị dữ liệu tổng hợp toàn hệ thống.
6. Module Bảo mật & Kết nối hệ thống
Phân quyền chi tiết: Cho phép cấu hình quyền xem, sửa, quản lý từng module.
Kết nối & Mở rộng: Tích hợp HTTPS, MQTT, WebSocket/ RESTful API cho phép kết nối liên hệ thống khác; Hỗ trợ triển khai tại chỗ (on-premise) hoặc trên nền tảng đám mây (cloud); Cho phép giám sát và điều khiển từ xa qua giao diện quản lý trung tâm.

## Vai trò trong LLM Wiki

Trang này là entity tri thức của vật tư **Hệ thống quản lý kiosks và xếp hàng VDS - SQSM v1.0**.

Entity này giúp hệ thống:

- Tra cứu lại thông tin định giá
- Giải thích nguồn dữ liệu
- Liên kết với concept nghiệp vụ
- Hỗ trợ AI Agent sử dụng lại tri thức trong các lần định giá sau

## Liên kết concept

- [[Giá tham chiếu]]
- [[Nguồn dữ liệu]]
- [[Quy tắc chọn giá]]
- [[Vật tư tương tự]]
- [[Second Brain]]

## Ghi chú đồng bộ

Trang được sinh tự động từ PostgreSQL thông qua LLM Wiki Framework.
