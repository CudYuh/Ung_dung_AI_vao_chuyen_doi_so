import asyncio, json
from routers.tavily_search_service import search_product_no_ai

def main():
    res = search_product_no_ai('iPhone 13 128GB', target_count=5)
    with open('test_res.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
