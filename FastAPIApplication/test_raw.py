import asyncio, json
from routers.tavily_search_service import search_and_price_product_batch, search_product_no_ai
from langchain_ollama import ChatOllama

def test():
    results = search_product_no_ai('Laptop ASUS Vivobook 15', target_count=5)
    formatted = []
    for idx, item in enumerate(results[:5], start=1):
        content = item.get('content', '')
        url = item.get('link', '')
        source = item.get('shop', 'tavily')
        formatted.append(f'[{idx}] (Nguồn: {source})\nURL: {url}\n{content}')
    internet_data = '\n\n'.join(formatted)
    llm = ChatOllama(model='llama3.2', temperature=0, format='json', num_predict=512)
    prompt = f"""Bạn là một chuyên gia đánh giá và bóc tách dữ liệu.
Nhiệm vụ của bạn là lấy giá cho sản phẩm cần tìm: "Laptop ASUS Vivobook 15"

Dữ liệu crawl được bằng Regex từ các nguồn:
{internet_data}

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM:
1. Bạn phải kiểm tra xem "Tên sản phẩm trên web" có đúng là sản phẩm cần tìm hay không.
2. Nếu ĐÚNG sản phẩm:
   - Ưu tiên lấy "Giá hiện tại (current_price)".
   - Nếu không có "Giá hiện tại", hãy lấy "Giá gốc (original_price)".
   - Nếu có cả hai, chỉ lấy "Giá hiện tại".
3. Nếu SAI sản phẩm:
   - Bỏ qua, KHÔNG lấy giá.
4. URL phải dẫn thẳng đến trang chi tiết của đúng sản phẩm này.

Trả về kết quả ĐÚNG định dạng JSON sau (nếu tìm thấy giá hợp lệ):
{{
  "final_price": "số tiền (ví dụ: 12.990.000)",
  "url": "link sản phẩm (bắt đầu bằng https://)",
  "description": "tên sản phẩm trên web"
}}
Nếu không có nguồn nào khớp sản phẩm, trả về các trường rỗng."""
    
    response = llm.invoke(prompt)
    with open('test_raw.txt', 'w', encoding='utf-8') as f:
        f.write(response.content)

test()
