import sys
import asyncio
import re
import json
import io
from unittest.mock import patch

def mock_llm_invoke(self, prompt, **kwargs):
    """
    Giả lập AI (Mock): Thay vì gọi Ollama, hàm này sẽ tự đọc đoạn text 
    mà Regex vừa crawl được và bóc tách ra JSON y hệt cách AI làm.
    Điều này giúp bạn test được luồng xuất file Excel mà không cần cài Ollama.
    """
    price_match = re.search(r"Giá hiện tại \(current_price\): ([\d.,]+)", prompt)
    url_match = re.search(r"URL: (https?://[^\s]+)", prompt)
    desc_match = re.search(r"Tên sản phẩm trên web: ([^\n]+)", prompt)
    
    price = price_match.group(1).replace(".", "") if price_match else ""
    url = url_match.group(1) if url_match else ""
    desc = desc_match.group(1).strip() if desc_match else ""
    
    fake_json = {
        "final_price": price,
        "url": url,
        "description": desc
    }
    
    class FakeResponse:
        content = json.dumps(fake_json)
        
    return FakeResponse()

async def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "../test.csv"
    output_file = "ket_qua_batch_test.csv"
    
    print(f"Đang đọc file CSV đầu vào: {input_file}")
    
    try:
        with open(input_file, 'rb') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Không tìm thấy file {input_file}. Vui lòng truyền đường dẫn file CSV.")
        return

    # Import FastAPI modules
    from fastapi import UploadFile
    from routers.valuation_api import valuate_batch
    
    file_obj = UploadFile(filename="test.csv", file=io.BytesIO(content))
    
    print("Đang chạy luồng Batch xuất Excel...")
    print("Đã Bypass (Mock) hệ thống AI LLM cục bộ...")
    
    # Patch thư viện ChatOllama để nó chạy hàm mock thay vì gọi thật
    with patch('langchain_ollama.ChatOllama.invoke', new=mock_llm_invoke):
        response = await valuate_batch(file_obj)
        
        if isinstance(response, dict) and response.get("status") == "error":
            print(f"Lỗi hệ thống: {response}")
            return
            
        with open(output_file, 'wb') as out_f:
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    out_f.write(chunk.encode('utf-8-sig'))
                else:
                    out_f.write(chunk)
                    
    print(f"\n✅ Đã xuất kết quả ra file: FastAPIApplication/{output_file}")
    print("Bạn có thể mở file này bằng Excel để kiểm tra xem Cột Giá và Link bên trong đã khớp nhau chưa.")

if __name__ == "__main__":
    asyncio.run(main())
