import re

internet_data = """[1] Nguồn tham khảo
URL: https://cellphones.com.vn/macbook-air-15-m5-10-cpu-10-gpu-24gb-512gb-sac-70w.html
Tên sản phẩm trên web: MacBook Air M5 15 inch 2026 10CPU 10GPU 24GB 512GB Sạc 70W | Chính hãng Apple Việt Nam
Giá hiện tại (current_price): 40290000 VNĐ [Nguồn: Schema.org LD+JSON]
Nội dung mô tả thêm (Tavily): ...

[2] Nguồn tham khảo
URL: https://fptshop.com.vn/may-tinh-xach-tay/macbook-air-15-m5-2026-10cpu-10gpu-16gb-512gb
Tên sản phẩm trên web: MacBook Air 15 M5 2026 10CPU/10GPU/16GB/512GB/35W
"""

def extract_quotes_from_internet_data(internet_data: str):
    quotes = []
    blocks = re.split(r'\[\d+\] Nguồn tham khảo\n', internet_data)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split('\n')
        url = ""
        price = ""
        description = "Nguồn tham khảo"
        for line in lines:
            line = line.strip()
            if line.startswith("URL:"):
                url = line.replace("URL:", "").strip()
            elif "Giá hiện tại (current_price):" in line:
                p_str = line.split("Giá hiện tại (current_price):")[1]
                p_str = p_str.split("VNĐ")[0].strip()
                price = p_str
            elif "Tên sản phẩm trên web:" in line:
                description = line.replace("Tên sản phẩm trên web:", "").strip()
        
        if url and price:
            quotes.append({
                "description": description,
                "url": url,
                "price": price
            })
    return quotes

print(extract_quotes_from_internet_data(internet_data))
