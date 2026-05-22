import os
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import or_
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from database import session_local
from models import Product

# Tải biến môi trường từ file .env
load_dotenv()

router = APIRouter(
    prefix="/api/v1",
    tags=["Valuation"],
)

# --- KHỞI TẠO CÔNG CỤ TÌM KIẾM TAVILY ---
tavily_search = None
if os.environ.get("TAVILY_API_KEY"):
    try:
        tavily_search = TavilySearch(max_results=5)
    except Exception as e:
        print(f"Warning: Could not initialize TavilySearch: {e}")
else:
    print("Warning: TAVILY_API_KEY environment variable is not set. TavilySearch tool will be disabled.")


# --- HÀM TÌM KIẾM TRONG DATABASE NỘI BỘ ---
def search_in_db(product_name: str) -> dict:
    """Tìm thông tin sản phẩm trong Database nội bộ. Trả về dict gồm found (bool) và data (str)."""
    db = session_local()
    try:
        search_query = f"%{product_name}%"
        products = db.query(Product).filter(
            or_(
                Product.name.ilike(search_query),
                Product.specifications.ilike(search_query)
            )
        ).all()

        if not products:
            return {
                "found": False,
                "data": f"Không tìm thấy '{product_name}' trong Database nội bộ."
            }

        result_lines = [f"Tìm thấy {len(products)} kết quả trong Database nội bộ:"]
        for p in products[:5]:
            result_lines.append(
                f"- Tên: {p.name} | Giá thẩm định: {p.price} VND "
                f"| Thông số: {p.specifications} "
                f"| Nguồn: {p.source} | Ngày: {p.appraisal_date}"
            )
        return {"found": True, "data": "\n".join(result_lines)}

    except Exception as e:
        return {"found": False, "data": f"Lỗi khi truy vấn database: {str(e)}"}
    finally:
        db.close()


# --- HÀM TÌM KIẾM TRÊN INTERNET (TAVILY) ---
def search_on_internet(product_name: str) -> str:
    """Tìm thông tin giá cả sản phẩm trên Internet bằng Tavily."""
    if tavily_search is None:
        return "Không tìm thấy thông tin trên Internet do chưa cấu hình Tavily API key."
    try:
        query = f"giá {product_name} chính hãng (Shopee OR Lazada OR Tiki OR dienmayxanh OR thegioididong OR fptshop OR cellphones OR phongvu)"
        results = tavily_search.invoke(query)
        # TavilySearch trả về list dict, mỗi item có 'content' và 'url'
        if isinstance(results, list):
            formatted = []
            for r in results:
                content = r.get('content', '')
                url = r.get('url', '')
                if content:
                    formatted.append(f"• {content}\n  Nguồn: {url}")
            return "\n".join(formatted) if formatted else "Không tìm thấy thông tin trên Internet."
        return str(results) if results else "Không tìm thấy thông tin trên Internet."
    except Exception as e:
        return f"Lỗi khi tìm kiếm Internet: {str(e)}"


# --- FASTAPI ENDPOINT ---
class ValuationRequest(BaseModel):
    product_name: str


@router.post("/valuate")
async def valuate_product(request: ValuationRequest):
    product_name = request.product_name
    source_label = ""
    raw_data = ""

    try:
        # ===== BƯỚC 1: TÌM TRONG DATABASE NỘI BỘ TRƯỚC =====
        db_result = search_in_db(product_name)

        if db_result["found"]:
            # Có dữ liệu trong DB → dùng dữ liệu này
            source_label = "database_noi_bo"
            raw_data = db_result["data"]
        else:
            # ===== BƯỚC 2: FALLBACK → TÌM TRÊN INTERNET =====
            source_label = "internet_tavily"
            internet_data = search_on_internet(product_name)
            raw_data = (
                f"{db_result['data']}\n\n"
                f"[Kết quả tìm kiếm Internet]:\n{internet_data}"
            )

        # ===== BƯỚC 3: DÙNG LLM ĐỂ TỔNG HỢP VÀ ĐƯA RA KẾT LUẬN ĐỊNH GIÁ =====
        llm = ChatGroq(temperature=0, model="llama-3.3-70b-versatile").bind(response_format={"type": "json_object"})

        synthesis_prompt = f"""Bạn là chuyên gia định giá tài sản doanh nghiệp tại Việt Nam.

Thông tin thu thập được cho sản phẩm "{product_name}":
---
{raw_data}
---

Nhiệm vụ: Dựa trên thông tin trên, hãy đưa ra kết quả định giá. ƯU TIÊN TUYỆT ĐỐI chọn lọc các báo giá từ những shop uy tín, nhà phân phối chính hãng, hoặc các sàn thương mại điện tử lớn (như Shopee Mall, LazMall, Tiki Trading, Điện Máy Xanh, FPT Shop, Thế Giới Di Động, Phong Vũ, CellphoneS, v.v.). Bỏ qua các tin rao vặt cá nhân không đáng tin cậy.
TRẢ VỀ DUY NHẤT một chuỗi JSON theo đúng định dạng sau (không giải thích thêm, không có markdown text):
{{
  "reference_quotes": [
    {{
      "description": "Tên/Mô tả ngắn gọn về sản phẩm tại nguồn đó",
      "price": "Mức giá duy nhất bằng VND (VD: '15.000.000')",
      "url": "Đường link (URL) hoặc Nguồn chính xác"
    }}
  ],
  "final_price": "Mức giá định giá dự kiến chốt lại bằng VND",
  "basis": "Giải thích ngắn gọn căn cứ định giá",
  "confidence": "Mức độ tin cậy (cao/trung bình/thấp)",
  "reason": "Lý do cho mức độ tin cậy"
}}
Lưu ý: reference_quotes trích xuất tối đa 2 thông tin báo giá khác nhau.
"""

        response = llm.invoke(synthesis_prompt)
        final_output = response.content
        import json
        try:
            clean_output = final_output.strip()
            if clean_output.startswith("```json"):
                clean_output = clean_output[7:-3]
            elif clean_output.startswith("```"):
                clean_output = clean_output[3:-3]
            valuation_result = json.loads(clean_output.strip())
        except Exception as e:
            valuation_result = {
                "reference_quotes": [],
                "final_price": "Không thể phân tích giá",
                "basis": final_output,
                "confidence": "thấp",
                "reason": "Lỗi phân tích cú pháp JSON"
            }

        return {
            "status": "success",
            "product": product_name,
            "data_source": source_label,
            "raw_data": raw_data,
            "valuation_result": valuation_result
        }

    except Exception as e:
        return {
            "status": "error",
            "product": product_name,
            "error": str(e),
            "valuation_result": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }
