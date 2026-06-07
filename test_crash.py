import traceback
import sys
import io
from FastAPIApplication.routers.valuation_api import extract_quotes_from_internet_data, normalize_valuation_result

internet_data = """[1] Nguồn tham khảo
URL: https://cellphones.com.vn/macbook-air-15-m5-10-cpu-10-gpu-24gb-512gb-sac-70w.html
Tên sản phẩm trên web: MacBook Air M5 15 inch 2026 10CPU 10GPU 24GB 512GB Sạc 70W | Chính hãng Apple Việt Nam
Giá hiện tại (current_price): 40290000 VNĐ [Nguồn: Schema.org LD+JSON]
Nội dung mô tả thêm (Tavily): ...

[2] Nguồn tham khảo
URL: https://fptshop.com.vn/may-tinh-xach-tay/macbook-air-15-m5-2026-10cpu-10gpu-16gb-512gb
Tên sản phẩm trên web: MacBook Air 15 M5 2026 10CPU/10GPU/16GB/512GB/35W
"""

with open("crash_log.txt", "w", encoding="utf-8") as f:
    try:
        f.write("Extracting...\n")
        quotes = extract_quotes_from_internet_data(internet_data)
        f.write(f"Extracted quotes: {quotes}\n")

        f.write("Normalizing...\n")
        res = normalize_valuation_result({}, internet_data)
        f.write(f"Normalized: {res}\n")
    except Exception as e:
        traceback.print_exc(file=f)
