# Legal Rules / Chuẩn mực định giá cho AI

Cập nhật lần cuối: 07/06/2026 22:21:25

## Văn bản pháp lý và chuẩn mực sử dụng

- Luật Giá số 16/2023/QH15 — hiệu lực: 01/07/2024
- Nghị định 78/2024/NĐ-CP — hiệu lực: 01/07/2024
- Thông tư 30/2024/TT-BTC — hiệu lực: 01/07/2024
- Thông tư 31/2024/TT-BTC — hiệu lực: 01/07/2024
- Thông tư 32/2024/TT-BTC — hiệu lực: 01/07/2024

## Quy tắc AI phải tuân thủ

- [critical] Không bịa giá khi thiếu dữ liệu: Nếu không có giá cụ thể từ database nội bộ, kho tri thức, hoặc nguồn Internet đáng tin cậy, AI phải trả về 'Không đủ dữ liệu định giá', không được tự tạo ra mức giá.
- [high] Ưu tiên dữ liệu nội bộ đã thẩm định: Khi database nội bộ hoặc LLM Wiki có dữ liệu tương tự đã được thẩm định, AI phải ưu tiên dữ liệu này trước khi sử dụng dữ liệu Internet.
- [high] Ưu tiên cách tiếp cận từ thị trường với hàng hóa phổ thông: Với vật tư, thiết bị, hàng hóa, xe, máy móc phổ thông, AI cần ưu tiên cách tiếp cận từ thị trường: so sánh giá từ database, vật tư tương tự, báo giá đại lý, sàn thương mại điện tử hoặc nguồn bán hàng đáng tin cậy.
- [high] Phải nêu giả định khi truy vấn mơ hồ: Nếu người dùng nhập thiếu thông tin như đời xe, model, cấu hình, tình trạng, dung lượng, phiên bản, AI được phép mở rộng truy vấn nhưng phải ghi rõ giả định trong phần căn cứ.
- [medium] Bắt buộc có độ tin cậy: Mọi kết quả định giá phải có độ tin cậy: cao, trung bình hoặc thấp. Độ tin cậy phải dựa trên số lượng nguồn, chất lượng nguồn và mức độ khớp thông số sản phẩm.
- [critical] AI chỉ hỗ trợ, không thay thế phê duyệt: Kết quả AI chỉ là tham khảo. Chỉ khi người dùng có thẩm quyền bấm phê duyệt thì kết quả mới được lưu vào database và trở thành dữ liệu tham chiếu cho các lần sau.
- [high] Lưu hồ sơ sau phê duyệt: Sau khi phê duyệt, hệ thống phải lưu lại tên tài sản, giá phê duyệt, căn cứ, nguồn dữ liệu, ngày phê duyệt, người phê duyệt và đồng bộ vào LLM Wiki để tái sử dụng.

## Vai trò trong hệ thống

Kho luật này là một phần của LLM Wiki Framework.

Khi AI định giá, hệ thống sẽ nạp các quy tắc này vào ngữ cảnh để:
- Ưu tiên dữ liệu nội bộ
- Ưu tiên cách tiếp cận thị trường với hàng hóa phổ thông
- Không bịa giá khi thiếu dữ liệu
- Nêu rõ giả định khi truy vấn mơ hồ
- Trả kết quả có căn cứ và độ tin cậy
- Chỉ lưu dữ liệu sau khi người dùng phê duyệt
