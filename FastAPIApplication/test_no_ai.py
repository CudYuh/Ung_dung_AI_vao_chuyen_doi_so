import json
import sys
from routers.tavily_search_service import search_product_no_ai

def main():
    product = "Laptop Asus Vivobook 15"
    if len(sys.argv) > 1:
        product = " ".join(sys.argv[1:])
        
    print(f"Đang tìm kiếm và trích xuất giá cho: '{product}'...")
    print("Quá trình này chỉ dùng Regex/Logic (KHÔNG dùng AI/Ollama)\n")
    
    res = search_product_no_ai(product, target_count=5)
    
    print(f"Tìm thấy {len(res)} kết quả:\n" + "="*50)
    for i, item in enumerate(res):
        print(f"\n[Kết quả {i+1}]")
        print(f"- Nguồn: {item.get('shop')}")
        print(f"- Link: {item.get('link')}")
        print(f"- Tên SP crawl được: {item.get('name')}")
        print(f"- Điểm tin cậy: {item.get('score')}")
        print(f"- Nội dung trích xuất được (đã ép giá):\n{item.get('content')}")
        print("-" * 50)
        
    with open('test_res.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("\nĐã lưu raw data vào FastAPIApplication/test_res.json")

if __name__ == "__main__":
    main()
