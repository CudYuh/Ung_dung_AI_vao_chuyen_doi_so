import csv
import io
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from langchain_ollama import ChatOllama
from routers.tavily_search_service import search_and_price_product, search_and_price_product_batch
from pydantic import BaseModel

from services.llm_wiki.legal_rules import load_legal_rules_for_ai
from routers.domain_registry import get_domains_for_category, detect_category_from_keywords


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


router = APIRouter(
    prefix="/api/v1",
    tags=["Valuation"],
)



class ValuationRequest(BaseModel):
    product_name: str


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    no_accent = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return no_accent.replace("đ", "d").replace("Đ", "D")


def normalize_text(value: str) -> str:
    value = strip_accents(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_lowest_price(price_str: str) -> str:
    """Nếu giá là 1 khoảng (vd: 592.540.000 - 855.000.000), lấy giá thấp nhất."""
    if not price_str:
        return ""
    # Tách các ký tự phân cách khoảng giá phổ biến
    for sep in ["-", "~", " đến ", " tới "]:
        if sep in price_str.lower():
            return price_str.lower().split(sep)[0].strip()
    return price_str.strip()


def understand_product_query(product_name: str) -> Dict[str, Any]:
    original = (product_name or "").strip()
    plain = normalize_text(original)

    normalized = original
    assumptions: List[str] = []

    # --- Các rule đặc biệt để chuẩn hóa tên sản phẩm ---
    if re.search(r"\bip\s*\d+", plain):
        number = re.findall(r"\d+", plain)
        if number:
            normalized = f"iPhone {number[0]}"
            assumptions.append(f"Người dùng nhập '{original}', hệ thống hiểu là '{normalized}'.")

    elif "sh mode" in plain:
        normalized = "Honda SH Mode 125 2024 2025"
        assumptions.append(
            "Người dùng nhập SH Mode, hệ thống mở rộng thành Honda SH Mode 125 đời 2024/2025 để tìm giá tham khảo."
        )

    elif "vision" in plain and ("honda" in plain or "xe" in plain or plain.startswith("vision")):
        normalized = "Honda Vision 110 2024 2025"
        assumptions.append(
            "Người dùng nhập Vision, hệ thống mở rộng thành Honda Vision 110 đời 2024/2025."
        )

    elif "air blade" in plain or "airblade" in plain:
        normalized = "Honda Air Blade 125 160 2024 2025"
        assumptions.append(
            "Người dùng nhập Air Blade, hệ thống mở rộng thành Honda Air Blade 125/160 đời 2024/2025."
        )

    elif "may in" in plain and "canon" in plain:
        normalized = f"{original} chính hãng Việt Nam"

    # --- Nhận diện category TỰ ĐỘNG từ registry keywords ---
    category_hint = detect_category_from_keywords(plain)

    if category_hint != "general":
        assumptions.append(
            f"Hệ thống nhận diện sản phẩm thuộc danh mục '{category_hint}', "
            f"sẽ tìm kiếm trên các domain chuyên ngành đã đăng ký."
        )

    return {
        "original": original,
        "normalized": normalized.strip(),
        "category_hint": category_hint,
        "assumptions": assumptions,
    }


def has_price_number(value: Any) -> bool:
    if value is None:
        return False

    return bool(re.search(r"\d", str(value)))


def parse_price_number(price_str: Any) -> float | None:
    """Trích xuất số tiền từ chuỗi giá, ví dụ '12.990.000 VND' -> 12990000.0"""
    if price_str is None:
        return None
    text = str(price_str).strip()
    # Loại bỏ các ký tự không phải số hoặc dấu chấm/phẩy
    # Giá Việt Nam dùng dấu chấm phân cách hàng nghìn: 12.990.000
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not cleaned:
        return None
    # Nếu có dấu chấm phân cách hàng nghìn (pattern: 12.990.000)
    if re.match(r"^\d{1,3}(\.\d{3})+$", cleaned):
        cleaned = cleaned.replace(".", "")
    # Nếu có dấu phẩy phân cách hàng nghìn (pattern: 12,990,000)
    elif re.match(r"^\d{1,3}(,\d{3})+$", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        # Trường hợp đơn giản: chỉ lấy các chữ số
        cleaned = re.sub(r"[^\d]", "", cleaned)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def check_price_consistency(
    quotes: list[dict],
    max_deviation_pct: float = 20.0,
) -> dict:
    """
    Kiểm tra sự nhất quán giá giữa các nguồn tham khảo.

    Returns:
        {
            "consistent": True/False,
            "prices": [float, ...],
            "deviation_pct": float,
            "avg_price": float,
            "status": "equal" | "acceptable" | "divergent",
            "suggested_price": float | None,
            "message": str,
        }
    """
    prices = []
    for q in quotes:
        p = parse_price_number(q.get("price", ""))
        if p and p > 0:
            prices.append(p)

    if len(prices) == 1:
        return {
            "consistent": True,
            "prices": prices,
            "deviation_pct": 0,
            "avg_price": prices[0],
            "status": "single",
            "suggested_price": prices[0],
            "message": "Sử dụng 1 nguồn giá duy nhất.",
        }
    elif len(prices) == 0:
        return {
            "consistent": False,
            "prices": prices,
            "deviation_pct": 0,
            "avg_price": 0,
            "status": "insufficient",
            "suggested_price": None,
            "message": "Không tìm được nguồn giá hợp lệ.",
        }

    min_p = min(prices)
    max_p = max(prices)
    avg_p = sum(prices) / len(prices)

    if min_p == 0:
        deviation_pct = 100.0
    else:
        deviation_pct = round(((max_p - min_p) / min_p) * 100, 1)

    if deviation_pct == 0:
        return {
            "consistent": True,
            "prices": prices,
            "deviation_pct": 0,
            "avg_price": avg_p,
            "status": "equal",
            "suggested_price": prices[0],
            "message": f"Hai nguồn có giá hoàn toàn trùng khớp ({_format_vnd(prices[0])} VND).",
        }
    elif deviation_pct <= max_deviation_pct:
        return {
            "consistent": True,
            "prices": prices,
            "deviation_pct": deviation_pct,
            "avg_price": avg_p,
            "status": "acceptable",
            "suggested_price": round(avg_p),
            "message": f"Chênh lệch {deviation_pct}% (trong ngưỡng cho phép ≤{max_deviation_pct}%). Giá đề xuất: {_format_vnd(round(avg_p))} VND.",
        }
    else:
        return {
            "consistent": False,
            "prices": prices,
            "deviation_pct": deviation_pct,
            "avg_price": avg_p,
            "status": "divergent",
            "suggested_price": None,
            "message": f"Chênh lệch {deviation_pct}% giữa 2 nguồn (vượt ngưỡng {max_deviation_pct}%). Không thể tự động chốt giá — cần người dùng kiểm tra lại.",
        }


def _format_vnd(amount: float) -> str:
    """Format số thành dạng tiền Việt: 12.990.000"""
    if amount is None:
        return "0"
    s = f"{int(amount):,}".replace(",", ".")
    return s


def safe_json_loads(text: str) -> Dict[str, Any]:
    clean_output = (text or "").strip()

    if clean_output.startswith("```json"):
        clean_output = clean_output[7:]

    if clean_output.startswith("```"):
        clean_output = clean_output[3:]

    if clean_output.endswith("```"):
        clean_output = clean_output[:-3]

    clean_output = clean_output.strip()

    match = re.search(r"\{[\s\S]*\}", clean_output)

    if match:
        clean_output = match.group(0)

    return json.loads(clean_output)


def build_no_data_result(product_name: str, reason: str) -> Dict[str, Any]:
    return {
        "reference_quotes": [],
        "final_price": "Không đủ dữ liệu định giá",
        "basis": f"Không tìm thấy đủ thông tin giá cụ thể cho sản phẩm '{product_name}'.",
        "confidence": "thấp",
        "reason": reason,
        "legal_compliance": [
            "Không đủ dữ liệu nên hệ thống không tự tạo giá.",
            "Cần bổ sung thông tin hoặc nguồn tham khảo trước khi phê duyệt.",
        ],
    }


def normalize_valuation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    reference_quotes = result.get("reference_quotes")

    if not isinstance(reference_quotes, list):
        reference_quotes = []

    normalized_quotes = []

    for quote in reference_quotes[:1]:
        if not isinstance(quote, dict):
            continue

        url = str(quote.get("url") or "").strip()
        # Đảm bảo URL hợp lệ (bắt đầu bằng http)
        if url and not url.startswith("http"):
            url = ""

        normalized_quotes.append(
            {
                "description": str(quote.get("description") or "Nguồn tham khảo").strip(),
                "price": str(quote.get("price") or "Không rõ").strip(),
                "url": url,
            }
        )

    # --- Kiểm tra sự nhất quán giá giữa các nguồn ---
    price_check = check_price_consistency(normalized_quotes)

    final_price = str(result.get("final_price") or "").strip()
    basis = str(result.get("basis") or "").strip()
    confidence = str(result.get("confidence") or "thấp").strip().lower()
    reason = str(result.get("reason") or "").strip()

    # Tự động xác định giá chốt dựa trên kiểm tra nhất quán
    if price_check["status"] == "equal":
        # 2 nguồn giá bằng nhau → chốt ngay
        final_price = f"{_format_vnd(price_check['suggested_price'])}"
        confidence = "cao"
        basis = f"Hai nguồn tham khảo cùng đưa ra mức giá {final_price} VND. {basis}"
    elif price_check["status"] == "single":
        final_price = f"{_format_vnd(price_check['suggested_price'])}"
        confidence = "cao"
        basis = f"Sử dụng mức giá tham khảo {final_price} VND từ 1 nguồn duy nhất. {basis}"
    elif price_check["status"] == "acceptable":
        # Chênh lệch nhỏ ≤ 20% → lấy trung bình
        final_price = f"{_format_vnd(price_check['suggested_price'])}"
        confidence = "trung bình"
        basis = f"Chênh lệch {price_check['deviation_pct']}% giữa các nguồn (chấp nhận được). Giá chốt = trung bình các nguồn. {basis}"
    elif price_check["status"] == "divergent":
        # Chênh lệch quá lớn → KHÔNG tự chốt giá
        final_price = "Không đủ dữ liệu định giá"
        confidence = "thấp"
        basis = f"Giá giữa các nguồn chênh lệch {price_check['deviation_pct']}% (vượt ngưỡng 20%). Cần người dùng kiểm tra và chọn nguồn phù hợp. {basis}"
        reason = price_check["message"]
    # else: insufficient — giữ nguyên giá từ AI

    legal_compliance = result.get("legal_compliance")

    if not isinstance(legal_compliance, list):
        legal_compliance = []

    legal_compliance = [
        str(item).strip()
        for item in legal_compliance
        if str(item).strip()
    ]

    if confidence not in ["cao", "trung bình", "thấp"]:
        confidence = "thấp"

    if not has_price_number(final_price):
        final_price = "Không đủ dữ liệu định giá"

    if not basis:
        basis = "Không có đủ dữ liệu đáng tin cậy để đưa ra mức giá."

    if not reason:
        reason = "Thiếu nguồn dữ liệu có giá cụ thể."

    if not legal_compliance:
        legal_compliance = [
            "Kết quả AI chỉ mang tính tham khảo và cần người dùng phê duyệt trước khi lưu.",
        ]

    return {
        "reference_quotes": normalized_quotes,
        "final_price": final_price,
        "basis": basis,
        "confidence": confidence,
        "reason": reason,
        "legal_compliance": legal_compliance,
        "price_consistency": price_check,
    }





def search_on_internet(product_name: str, category_hint: str) -> str:
    """
    Tìm kiếm Internet bằng Tavily Search API.
    Ưu tiên whitelist domains, loại trừ bài báo/tin tức.
    Giá phải đúng với giá trên link (giá sau giảm nếu có khuyến mãi).
    """
    return search_and_price_product(product_name, category_hint)


def sync_valuate_product(request: ValuationRequest):
    user_query = request.product_name.strip()
    understood = understand_product_query(user_query)

    product_name = understood["normalized"]
    category_hint = understood["category_hint"]
    assumptions = understood["assumptions"]

    try:
        # Luôn tìm kiếm trên Internet (AI định giá KHÔNG động đến DB)
        data_source = "internet_ai"
        internet_data = search_on_internet(product_name, category_hint)

        # Rút gọn raw_data để giảm token cho model local
        raw_data = (
            f"[Truy vấn]\n{user_query} -> {product_name}\n\n"
            f"[Internet]\n{internet_data}"
        )

        if (
            "chưa cấu hình Tavily API key" in raw_data
            or "Không tìm thấy thông tin trên Internet" in raw_data
            or "Lỗi khi tìm kiếm trên Internet" in raw_data
        ):
            return {
                "status": "success",
                "product": product_name,
                "original_query": user_query,
                "normalized_query": product_name,
                "assumptions": assumptions,
                "data_source": data_source,
                "raw_data": raw_data,
                "valuation_result": build_no_data_result(
                    product_name,
                    "Không có dữ liệu Internet đủ tin cậy để định giá.",
                ),
            }

        llm = ChatOllama(
            model="llama3.2",
            temperature=0,
            format="json",
            num_predict=512,
        )

        # Lấy quy tắc định giá
        legal_rules = load_legal_rules_for_ai()
        
        # Prompt rút gọn tối ưu cho model local nhỏ
        prompt = f"""Bạn là chuyên gia định giá tài sản tại Việt Nam. Phân tích dữ liệu và trả JSON.

Người dùng nhập:
"{user_query}"

Hệ thống đã chuẩn hóa truy vấn thành:
"{product_name}"

Loại tài sản dự đoán:
"{category_hint}"

Giả định xử lý:
{json.dumps(assumptions, ensure_ascii=False)}

Dữ liệu thu thập được:
---
{raw_data}
---

Các luật và chuẩn mực định giá phải tuân thủ:
---
{legal_rules}
---

Nhiệm vụ:
1. BẮT BUỘC đọc "Tên sản phẩm trên web" từ dữ liệu và so sánh xem có ĐÚNG với sản phẩm cần tìm hay không.
2. NẾU ĐÚNG SẢN PHẨM:
   - Đưa ra mức giá định giá dự kiến bằng VND. Ưu tiên lấy "Giá hiện tại (current_price)". Nếu không có, mới lấy "Giá gốc (original_price)".
3. NẾU SAI SẢN PHẨM (khác dòng máy, phiên bản, là phụ kiện...):
   - Bỏ qua nguồn đó, TUYỆT ĐỐI KHÔNG lấy giá của nguồn đó.
4. CHỈ SỬ DỤNG DỮ LIỆU TỪ INTERNET để định giá. TUYỆT ĐỐI KHÔNG dùng dữ liệu nội bộ hay cơ sở dữ liệu.
5. Nếu truy vấn người dùng mơ hồ nhưng vẫn đoán được sản phẩm, phải ghi rõ giả định trong basis.
6. KHÔNG ĐƯỢC bịa giá. GIÁ PHẢI CHÍNH XÁC Y HỆT THEO URL, không tự làm tròn.
7. Không được trả final_price rỗng, không được chỉ trả "VND" hoặc "VNĐ".
8. Nếu không đủ dữ liệu, final_price phải là "Không đủ dữ liệu định giá".
9. confidence chỉ được là một trong ba giá trị: "cao", "trung bình", "thấp".
10. legal_compliance phải nêu hệ thống đã tuân thủ quy tắc nào.
11. SỐ LƯỢNG KẾT QUẢ: BẮT BUỘC TRẢ VỀ ĐÚNG 1 NGUỒN THAM KHẢO GIÁ DUY NHẤT. Chọn nguồn có thông tin giá rõ ràng và khớp với sản phẩm nhất.
12. TIÊU CHÍ CHỌN: Chỉ chọn kết quả KHỚP ĐÚNG SẢN PHẨM và BẮT BUỘC PHẢI CÓ GIÁ. TUYỆT ĐỐI KHÔNG LẤY GIÁ CỦA SẢN PHẨM NÀY GHÉP CHO SẢN PHẨM KHÁC.
13. URL CHÍNH XÁC: Trường "url" BẮT BUỘC phải là link chi tiết đến tận trang bán sản phẩm đó (giữ nguyên đầy đủ tham số). Tuyệt đối không được tự ý rút gọn URL thành link trang chủ.

Trả về DUY NHẤT một JSON object theo định dạng:

{{
  "reference_quotes": [
    {{
      "description": "Chỉ ghi TÊN SẢN PHẨM chính xác (ví dụ: iPhone 16 Pro Max 256GB), TUYỆT ĐỐI KHÔNG kèm tên trang web/shop",
      "price": "Mức giá bằng VND, ví dụ: 62.700.000",
      "url": "https://url-chi-tiet-den-tan-trang-san-pham.com (tuyệt đối giữ nguyên link đầy đủ)"
    }}
  ],
  "final_price": "Mức giá định giá dự kiến bằng VND hoặc Không đủ dữ liệu định giá",
  "basis": "Giải thích căn cứ định giá, nguồn dữ liệu, cách tiếp cận và giả định nếu có",
  "confidence": "cao/trung bình/thấp",
  "reason": "Lý do đánh giá mức độ tin cậy",
  "legal_compliance": [
    "Quy tắc pháp lý hoặc chuẩn mực đã được áp dụng"
  ]
}}
"""

        response = llm.invoke(prompt)
        final_output = response.content

        try:
            valuation_result = safe_json_loads(final_output)
            valuation_result = normalize_valuation_result(valuation_result)

        except Exception:
            valuation_result = build_no_data_result(
                product_name,
                "AI không trả về đúng cấu trúc JSON hoặc dữ liệu không đủ rõ.",
            )
            valuation_result["basis"] = final_output

        return {
            "status": "success",
            "product": product_name,
            "original_query": user_query,
            "normalized_query": product_name,
            "assumptions": assumptions,
            "data_source": data_source,
            "raw_data": raw_data,
            "valuation_result": valuation_result,
        }

    except Exception as e:
        return {
            "status": "error",
            "product": product_name,
            "original_query": user_query,
            "normalized_query": product_name,
            "assumptions": assumptions,
            "error": str(e),
            "valuation_result": build_no_data_result(
                product_name,
                f"Lỗi khi xử lý yêu cầu: {str(e)}",
            ),
        }

def take_desktop_screenshot_sync(product_name: str):
    """Chụp ảnh toàn màn hình desktop (bao gồm taskbar có đồng hồ góc phải)"""
    import pyautogui
    import time
    from datetime import datetime
    from pathlib import Path
    import re

    # Chờ 3 giây để frontend nhận được kết quả và render lên màn hình
    time.sleep(3)

    # Định nghĩa thư mục lưu trữ (gốc dự án)
    save_dir = Path(__file__).resolve().parents[2] / "screenshots"
    save_dir.mkdir(exist_ok=True)

    try:
        # Chụp màn hình desktop
        screenshot = pyautogui.screenshot()

        # Tạo tên file an toàn dựa trên tên sản phẩm và thời gian
        safe_name = re.sub(r"[^\w\-]", "_", product_name)[:40]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_name}_{timestamp}.png"
        filepath = save_dir / filename
        
        # Lưu ảnh
        screenshot.save(filepath)
        print(f"Screenshot saved successfully: {filename}")
        
        # Thêm log hoặc in ra file để dễ kiểm tra
        return str(filepath)
    except Exception as e:
        print(f"Error during screenshot: {type(e).__name__}")
        return ""


@router.post("/valuate")
async def valuate_product(request: ValuationRequest, background_tasks: BackgroundTasks):
    result = await run_in_threadpool(sync_valuate_product, request)
    
    # Tự động trigger chụp màn hình sau khi có giá
    background_tasks.add_task(take_desktop_screenshot_sync, request.product_name)
    
    return result

def _detect_product_column(headers: List[str]) -> int:
    """
    Tự động phát hiện cột chứa tên sản phẩm trong file CSV.

    Ưu tiên:
    1. Cột có tên chứa 'san_pham', 'sản phẩm', 'product', 'ten', 'tên'
    2. Nếu chỉ có 1 cột text → dùng cột đó
    3. Nếu có 2 cột trở lên, bỏ qua cột 'stt' / 'id' / 'no' → dùng cột text đầu tiên còn lại
    """

    PRODUCT_KEYWORDS = {"san_pham", "san pham", "sản phẩm", "product", "product_name", "ten", "tên", "name"}
    SKIP_KEYWORDS = {"stt", "id", "no", "so_thu_tu", "số thứ tự"}

    normalized_headers = [normalize_text(h) for h in headers]

    # Bước 1: tìm header khớp từ khoá sản phẩm
    for idx, norm in enumerate(normalized_headers):
        for keyword in PRODUCT_KEYWORDS:
            if keyword in norm:
                return idx

    # Bước 2: bỏ cột stt/id, lấy cột text đầu tiên còn lại
    for idx, norm in enumerate(normalized_headers):
        if norm in SKIP_KEYWORDS:
            continue
        # Bỏ cột toàn số
        if norm.replace(" ", "").isdigit():
            continue
        return idx

    # Fallback: nếu có >= 2 cột thì dùng cột thứ 2 (vì cột 0 thường là STT)
    if len(headers) >= 2:
        return 1

    return 0


# === [LEGACY] Rate limiter cho Tavily API — commented out, replaced by Google Search Grounding ===
# _tavily_lock = threading.Lock()
# _tavily_last_call_time = 0.0
#
#
# def _rate_limited_tavily_call(tavily_search, query: str) -> Any:
#     """Gọi Tavily API với rate limit: tối thiểu 1.5s giữa các lần gọi."""
#     global _tavily_last_call_time
#     with _tavily_lock:
#         now = time.time()
#         wait = 1.5 - (now - _tavily_last_call_time)
#         if wait > 0:
#             time.sleep(wait)
#         _tavily_last_call_time = time.time()
#     return tavily_search.invoke(query)
# === [END LEGACY] ===


# === [LEGACY] DuckDuckGo search — commented out, replaced by Google Search Grounding ===
# def _search_duckduckgo(query: str, max_results: int = 3) -> List[Dict[str, str]]:
#     """Tìm kiếm bằng DuckDuckGo (bắt lỗi rate limit nếu có)."""
#     if not DDGS:
#         return []
#     try:
#         items = []
#         with DDGS() as ddgs:
#             # Dùng backend lite/html thường ổn định hơn
#             results = ddgs.text(query, max_results=max_results, backend="lite")
#             for r in results:
#                 items.append({
#                     "title": r.get("title", ""),
#                     "content": r.get("body", ""),
#                     "url": r.get("href", "")
#                 })
#         return items
#     except Exception:
#         return []
# === [END LEGACY] ===


# === [LEGACY] _sync_search_internet_for_batch (Tavily + DuckDuckGo) — commented out ===
# def _sync_search_internet_for_batch(product_name: str) -> Dict[str, Any]:
#     """
#     Tìm kiếm Internet cho 1 sản phẩm trong batch.
#     Sử dụng rate limiter để tránh Tavily bị chặn.
#     Ưu tiên tìm kiếm trong các domain đã đăng ký theo category.
#     """
#     if not os.environ.get("TAVILY_API_KEY"):
#         return {"price": "", "url": "", "description": "", "confidence": "thấp"}
#
#     # Phát hiện category để lấy domain ưu tiên
#     understood = understand_product_query(product_name)
#     category_hint = understood["category_hint"]
#     priority_domains = get_domains_for_category(category_hint)
#
#     try:
#         if priority_domains:
#             tavily_search = TavilySearch(
#                 max_results=5,
#                 include_domains=priority_domains,
#             )
#         else:
#             tavily_search = TavilySearch(max_results=5)
#     except Exception:
#         return {"price": "", "url": "", "description": "", "confidence": "thấp"}
#
#     # Dùng 2 queries ngắn gọn
#     queries = [
#         f"giá {product_name} chính hãng Việt Nam",
#         f"{product_name} giá bán",
#     ]
#
#     all_items: List[Dict[str, str]] = []
#
#     for query in queries:
#         # Ưu tiên tìm bằng Tavily trước (với domain ưu tiên)
#         for attempt in range(3):
#             try:
#                 raw_results = _rate_limited_tavily_call(tavily_search, query)
#                 items = extract_tavily_results(raw_results)
#                 for item in items:
#                     item["query"] = query
#                     item["source"] = "tavily"
#                     all_items.append(item)
#                 break
#             except Exception:
#                 wait_time = 2 * (attempt + 1)  # 2s, 4s, 6s
#                 time.sleep(wait_time)
#                 continue
#
#         # Thoát nếu đã có đủ dữ liệu từ Tavily
#         if len(all_items) >= 5:
#             break
#
#     # Fallback: nếu dùng domain ưu tiên mà Tavily trả ít, tìm lại không giới hạn domain
#     if len(all_items) < 2 and priority_domains:
#         try:
#             tavily_fallback = TavilySearch(max_results=3)
#             for query in queries:
#                 for attempt in range(2):
#                     try:
#                         raw_results = _rate_limited_tavily_call(tavily_fallback, query)
#                         items = extract_tavily_results(raw_results)
#                         for item in items:
#                             item["query"] = query
#                             item["source"] = "tavily_fallback"
#                             all_items.append(item)
#                         break
#                     except Exception:
#                         time.sleep(2 * (attempt + 1))
#                         continue
#                 if len(all_items) >= 5:
#                     break
#         except Exception:
#             pass
#
#     # Nếu Tavily trả về quá ít dữ liệu (hoặc không có), dùng DuckDuckGo để bổ trợ
#     if len(all_items) < 3:
#         for query in queries:
#             ddg_results = _search_duckduckgo(query, max_results=3)
#             for r in ddg_results:
#                 r["query"] = query
#                 r["source"] = "duckduckgo"
#                 all_items.append(r)
#
#             if len(all_items) >= 5:
#                 break
#
#     if not all_items:
#         return {"price": "", "url": "", "description": "", "confidence": "thấp"}
#
#     # Format kết quả cho LLM - Tối ưu hóa để tiết kiệm token
#     formatted = []
#     # Chỉ lấy tối đa 5 kết quả tốt nhất thay vì 10 để tiết kiệm token
#     for idx, item in enumerate(all_items[:5], start=1):
#         title = item.get("title") or ""
#         content = item.get("content") or ""
#         # Cắt ngắn nội dung còn 300 ký tự (đủ để AI đọc được giá xung quanh từ khóa)
#         if len(content) > 300:
#             content = content[:300] + "..."
#
#         url = item.get("url") or ""
#         source = item.get("source") or "unknown"
#         formatted.append(
#             f"[{idx}] (Nguồn: {source}) {title}\nURL: {url}\n{content}"
#         )
#     internet_data = "\n\n".join(formatted)
#
#     # Dùng LLM để trích xuất giá (model nhẹ cho batch)
#     llm = ChatOllama(
#         model="qwen2.5:3b",
#         temperature=0,
#         format="json",
#         num_predict=256,
#     )
#
#     prompt = f"""Trích xuất giá bán của sản phẩm "{product_name}" từ dữ liệu sau.
# LƯU Ý:
# - Nếu có giá gốc (giá niêm yết) và giá sau khi giảm (giá khuyến mãi), BẮT BUỘC lấy giá SAU KHI ĐÃ GIẢM GIÁ làm kết quả.
# - CHỈ LẤY GIÁ TỪ TRANG BÁN HÀNG.
#
# {internet_data}
#
# Trả về JSON:
# {{
#   "final_price": "giá VND thấp nhất",
#   "url": "URL nguồn có giá (bắt đầu bằng https://)",
#   "description": "tên nguồn"
# }}"""
#
#     try:
#         response = llm.invoke(prompt)
#         result = safe_json_loads(response.content)
#         return {
#             "price": str(result.get("final_price", "")).strip(),
#             "url": str(result.get("url", "")).strip(),
#             "description": str(result.get("description", "")).strip(),
#             "confidence": "trung bình",
#         }
#     except Exception:
#         return {"price": "", "url": "", "description": "", "confidence": "thấp"}
# === [END LEGACY] ===


def _sync_search_internet_for_batch(product_name: str) -> Dict[str, Any]:
    """
    Tìm kiếm Internet cho 1 sản phẩm trong batch.
    Sử dụng Tavily Search API + LLM để trích xuất giá.
    Ưu tiên whitelist domains, lọc bỏ link bài báo/tin tức.
    """
    return search_and_price_product_batch(product_name)


async def _process_single_product(product_name: str) -> Dict[str, str]:
    """Xử lý 1 sản phẩm: luôn tìm kiếm AI trên Internet, KHÔNG dùng DB."""
    try:
        ai_result = await run_in_threadpool(
            search_and_price_product_batch, product_name
        )

        price = extract_lowest_price(ai_result.get("price", ""))
        link = ai_result.get("url", "")
        note = "AI tìm kiếm"

        if link and not link.startswith("http"):
            link = ""

        if not has_price_number(price):
            price = "Không đủ dữ liệu"
            note = "AI không tìm được giá. Vui lòng liên hệ cơ sở, hệ thống buôn bán."

    except Exception:
        price = ""
        link = ""
        note = "AI không tìm được giá. Vui lòng liên hệ cơ sở, hệ thống buôn bán."

    return {"price": price, "link": link, "note": note}


@router.post("/valuate/batch")
async def valuate_batch(file: UploadFile = File(...)):
    try:
        content = await file.read()
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = content.decode("latin-1")
            
        reader = csv.reader(io.StringIO(decoded))
        
        async def iter_csv():
            import asyncio

            output = io.StringIO()
            writer = csv.writer(output)
            
            headers = next(reader, None)
            if headers is None:
                yield "File CSV trống."
                return
            
            # Tự động phát hiện cột chứa tên sản phẩm
            product_col_idx = _detect_product_column(headers)
            
            # Thêm BOM để Excel đọc được tiếng Việt
            yield '\ufeff'
                
            output_headers = headers + ["Gia_du_kien", "Link_tham_khao", "Ghi_chu"]
            writer.writerow(output_headers)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            # Thu thập tất cả rows trước
            all_rows = []
            for row in reader:
                if not row or not any(row):
                    continue
                all_rows.append(row)

            # Xử lý song song theo batch (3 sản phẩm cùng lúc)
            BATCH_SIZE = 3
            for batch_start in range(0, len(all_rows), BATCH_SIZE):
                batch_rows = all_rows[batch_start:batch_start + BATCH_SIZE]

                # Tạo tasks song song cho batch này
                tasks = []
                for row in batch_rows:
                    if product_col_idx < len(row):
                        product_name = row[product_col_idx].strip()
                    else:
                        product_name = row[0].strip()

                    if product_name:
                        tasks.append(_process_single_product(product_name))
                    else:
                        # Placeholder cho sản phẩm trống
                        async def empty_result():
                            return {"price": "", "link": "", "note": "Bỏ qua vì tên sản phẩm trống"}
                        tasks.append(empty_result())

                # Chạy song song
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Ghi kết quả ra CSV
                for row, result in zip(batch_rows, results):
                    if isinstance(result, Exception):
                        price, link, note = "", "", "AI không tìm được giá. Vui lòng liên hệ cơ sở, hệ thống buôn bán."
                    else:
                        price = result.get("price", "")
                        link = result.get("link", "")
                        note = result.get("note", "")

                    # Ép Excel hiểu giá là Text (tránh việc 879.000 bị biến thành 879 do hiểu nhầm là số thập phân)
                    if price and price != "Không đủ dữ liệu" and price != "Không có dữ liệu":
                        excel_price = f'="{price}"'
                    else:
                        excel_price = price

                    # Wrap link trong công thức HYPERLINK để bấm được trong Excel
                    if link and link.startswith("http"):
                        excel_link = f'=HYPERLINK("{link}","{link}")'
                    else:
                        excel_link = link

                    writer.writerow(row + [excel_price, excel_link, note])
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)

        return StreamingResponse(
            iter_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=batch_valuation_result.csv"}
        )
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/valuate/test_batch")
async def test_batch():
    async def iter_test():
        yield "a,b,c\n"
        import asyncio
        await asyncio.sleep(1)
        yield "1,2,3\n"
    return StreamingResponse(iter_test(), media_type="text/csv")