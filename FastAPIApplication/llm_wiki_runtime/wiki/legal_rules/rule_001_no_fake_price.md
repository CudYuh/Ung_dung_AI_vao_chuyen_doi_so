# Không bịa giá khi thiếu dữ liệu

## Mức ưu tiên

critical

## Quy tắc áp dụng cho AI

Nếu không có giá cụ thể từ database nội bộ, kho tri thức, hoặc nguồn Internet đáng tin cậy, AI phải trả về 'Không đủ dữ liệu định giá', không được tự tạo ra mức giá.

## Căn cứ pháp lý / chuẩn mực liên quan

- [[Luật Giá số 16/2023/QH15]]
- [[Thông tư 30/2024/TT-BTC]]
- [[Thông tư 31/2024/TT-BTC]]

## Cách hệ thống sử dụng

Quy tắc này được nạp vào prompt định giá để AI kiểm tra trước khi đưa ra kết quả.

Nếu kết quả AI vi phạm quy tắc này, hệ thống phải ưu tiên an toàn:
- Không bịa giá
- Không phê duyệt tự động
- Yêu cầu bổ sung thông tin hoặc nguồn dữ liệu
