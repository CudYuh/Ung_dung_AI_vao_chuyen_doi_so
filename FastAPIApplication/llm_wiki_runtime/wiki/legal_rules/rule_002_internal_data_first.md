# Ưu tiên dữ liệu nội bộ đã thẩm định

## Mức ưu tiên

high

## Quy tắc áp dụng cho AI

Khi database nội bộ hoặc LLM Wiki có dữ liệu tương tự đã được thẩm định, AI phải ưu tiên dữ liệu này trước khi sử dụng dữ liệu Internet.

## Căn cứ pháp lý / chuẩn mực liên quan

- [[Luật Giá số 16/2023/QH15]]
- [[Thông tư 30/2024/TT-BTC]]

## Cách hệ thống sử dụng

Quy tắc này được nạp vào prompt định giá để AI kiểm tra trước khi đưa ra kết quả.

Nếu kết quả AI vi phạm quy tắc này, hệ thống phải ưu tiên an toàn:
- Không bịa giá
- Không phê duyệt tự động
- Yêu cầu bổ sung thông tin hoặc nguồn dữ liệu
