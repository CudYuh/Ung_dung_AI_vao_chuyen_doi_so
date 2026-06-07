# AI chỉ hỗ trợ, không thay thế phê duyệt

## Mức ưu tiên

critical

## Quy tắc áp dụng cho AI

Kết quả AI chỉ là tham khảo. Chỉ khi người dùng có thẩm quyền bấm phê duyệt thì kết quả mới được lưu vào database và trở thành dữ liệu tham chiếu cho các lần sau.

## Căn cứ pháp lý / chuẩn mực liên quan

- [[Nghị định 78/2024/NĐ-CP]]
- [[Thông tư 30/2024/TT-BTC]]

## Cách hệ thống sử dụng

Quy tắc này được nạp vào prompt định giá để AI kiểm tra trước khi đưa ra kết quả.

Nếu kết quả AI vi phạm quy tắc này, hệ thống phải ưu tiên an toàn:
- Không bịa giá
- Không phê duyệt tự động
- Yêu cầu bổ sung thông tin hoặc nguồn dữ liệu
