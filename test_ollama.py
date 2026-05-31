from langchain_ollama import ChatOllama
import json

raw_data = """
[Internet]
[1] Đồng hồ thông minh Samsung Galaxy Watch 8 40mm/44mm
URL: https://phukiensamsunggiare.vn/products/dong-ho-thong-minh-samsung-galaxy-watch-8-40mm-44mm-bluetooth-lte-hang-chinh-hang
Đồng hồ thông minh Samsung Galaxy Watch 8 40mm/44mm - Bluetooth/LTE-Hàng chính hãng ; Giá: 6,990,000₫ (Đã có VAT) ; CAM KẾT LUÔN BÁN GIÁ TỐT NHẤT. Nếu bạn tìm

[2] Samsung Galaxy Watch8: Đồng hồ AI theo dõi sức khỏe - Clickbuy
URL: https://clickbuy.com.vn/samsung-galaxy-watch8-chinh-hang.html
Giá của Galaxy Watch8 là khoảng 8.990.000 VNĐ. Với mức giá này, người dùng có thể sở hữu một chiếc đồng hồ thông minh thế hệ mới, tích hợp nhiều
"""

prompt = f"""Bạn là chuyên gia định giá tài sản tại Việt Nam. Phân tích dữ liệu và trả JSON.

Sản phẩm: "Đồng hồ thông minh Samsung Galaxy Watch8" (loại: general)

Dữ liệu:
{raw_data}

Quy tắc BẮT BUỘC:
- Phải trả về ĐÚNG 2 nguồn tham khảo (reference_quotes) từ 2 kết quả KHÁC NHAU trong phần Dữ liệu.
- Trong mỗi nguồn tham khảo (quote), BẮT BUỘC phải có ĐẦY ĐỦ 3 trường là "description", "price", và "url".
- Giá tiền của mỗi nguồn PHẢI TRÍCH XUẤT CHÍNH XÁC từ nội dung đi kèm với URL đó. TUYỆT ĐỐI KHÔNG ghép link của kết quả này với giá của kết quả khác. KHÔNG TỰ BỊA GIÁ.
- Hai nguồn tham khảo phải là của cùng một sản phẩm hoặc tương đương, mức giá không được chênh lệch nhau quá lớn. Không bắt buộc giá phải bằng nhau y hệt.
- Trường "url" CHỈ ĐƯỢC CHỨA URL THỰC TẾ (lấy từ dòng 'URL: ...' của kết quả đó). BẮT BUỘC phải bắt đầu bằng http hoặc https.
- Mỗi nguồn PHẢI CÓ giá cụ thể dạng số (ví dụ: 12.990.000).
- description phải ghi rõ tên trang web + tên sản phẩm.
- Ưu tiên nguồn từ các cửa hàng uy tín, sàn thương mại điện tử.
- Ưu tiên dữ liệu nội bộ trước Internet.
- Nếu không đủ dữ liệu, final_price = "Không đủ dữ liệu định giá".
- confidence: "cao"/"trung bình"/"thấp"

Trả về JSON:
{{
  "reference_quotes": [
    {{"description": "Tên trang - Tên sản phẩm", "price": "12.990.000", "url": "https://url-thuc-te-cua-trang-web-thu-nhat.com"}},
    {{"description": "Tên trang - Tên sản phẩm", "price": "13.500.000", "url": "https://url-thuc-te-cua-trang-web-thu-hai.com"}}
  ],
  "final_price": "giá VND trung bình hoặc Không đủ dữ liệu định giá",
  "basis": "căn cứ định giá",
  "confidence": "cao/trung bình/thấp",
  "reason": "lý do",
  "legal_compliance": ["quy tắc đã tuân thủ"]
}}"""

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
    format="json",
    num_predict=512,
)

response = llm.invoke(prompt)
with open("test_ollama_out_3.txt", "w", encoding="utf-8") as f:
    f.write(response.content)
