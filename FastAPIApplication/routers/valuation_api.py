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


def extract_quotes_from_internet_data(internet_data: str) -> List[Dict]:
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

def normalize_valuation_result(result: Dict[str, Any], internet_data: str = "") -> Dict[str, Any]:
    if internet_data:
        extracted = extract_quotes_from_internet_data(internet_data)
        if extracted:
            result["reference_quotes"] = extracted

    reference_quotes = result.get("reference_quotes")

    if not isinstance(reference_quotes, list):
        reference_quotes = []

    all_quotes = []

    for quote in reference_quotes:
        if not isinstance(quote, dict):
            continue

        url = str(quote.get("url") or "").strip()
        # Đảm bảo URL hợp lệ
        if url and not url.startswith("http"):
            if url.startswith("www.") or re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', url):
                url = "https://" + url
            else:
                url = ""

        parsed_p = parse_price_number(str(quote.get("price") or ""))
        all_quotes.append(
            {
                "description": str(quote.get("description") or "Nguồn tham khảo").strip(),
                "price": str(quote.get("price") or "Không rõ").strip(),
                "url": url,
                "parsed_price": parsed_p
            }
        )

    # Lọc ra các nguồn có giá hợp lệ
    valid_quotes = [q for q in all_quotes if q["parsed_price"] is not None and q["parsed_price"] > 0]

    if not valid_quotes:
        # Nếu không có nguồn nào có giá parse được, dùng tạm các nguồn đầu tiên
        normalized_quotes = [{k: v for k, v in q.items() if k != "parsed_price"} for q in all_quotes[:2]]
    else:
        from collections import Counter
        # Tính tần suất xuất hiện của các mức giá
        price_counts = Counter([q["parsed_price"] for q in valid_quotes])
        # Lấy mức giá phổ biến nhất
        most_common_price = price_counts.most_common(1)[0][0]
        
        # Nhóm các quote có mức giá phổ biến nhất
        best_quotes = [q for q in valid_quotes if q["parsed_price"] == most_common_price]
        
        # Nếu chưa đủ 2 nguồn, bổ sung thêm từ nhóm khác
        if len(best_quotes) < 2:
            other_quotes = [q for q in valid_quotes if q["parsed_price"] != most_common_price]
            best_quotes.extend(other_quotes)
            
        # Chọn tối đa 2 nguồn
        selected_quotes = best_quotes[:2]
        normalized_quotes = [{k: v for k, v in q.items() if k != "parsed_price"} for q in selected_quotes]

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
11. DO NOT return `reference_quotes`. The system will automatically extract and attach the quotes for you.

Trả về DUY NHẤT một JSON object theo định dạng:

{{
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
            valuation_result = normalize_valuation_result(valuation_result, internet_data)

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

def take_desktop_screenshot_sync(product_name: str, urls: List[str] = None):
    """Chụp ảnh toàn màn hình desktop (hoặc các urls tham khảo nếu có)"""
    import pyautogui
    import time
    from datetime import datetime
    from pathlib import Path
    import re
    import webbrowser

    # Định nghĩa thư mục lưu trữ (gốc dự án)
    save_dir = Path(__file__).resolve().parents[2] / "screenshots"
    save_dir.mkdir(exist_ok=True)

    # Nếu có urls hợp lệ, chụp từng url
    valid_urls = [u for u in (urls or []) if u and u.startswith("http")]
    
    if valid_urls:
        saved_paths = []
        for idx, url in enumerate(valid_urls, start=1):
            try:
                # Mở URL
                webbrowser.open(url)
                
                # Chờ 6 giây để trình duyệt tải trang
                time.sleep(6)
                
                # Chụp màn hình
                screenshot = pyautogui.screenshot()
                
                # Tạo tên file
                safe_name = re.sub(r"[^\w\-]", "_", product_name)[:40]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{safe_name}_ref_{idx}_{timestamp}.png"
                filepath = save_dir / filename
                
                screenshot.save(filepath)
                saved_paths.append(str(filepath))
                print(f"Reference screenshot saved: {filename} for {url}")
                
                # Đóng tab trình duyệt vừa mở
                pyautogui.hotkey('ctrl', 'w')
                time.sleep(1.5)
            except Exception as e:
                print(f"Error during reference screenshot for {url}: {e}")
        return ", ".join(saved_paths)
    
    else:
        # Hành vi mặc định khi không có urls: chờ 3 giây và chụp desktop hiện tại
        time.sleep(3)
        try:
            screenshot = pyautogui.screenshot()
            safe_name = re.sub(r"[^\w\-]", "_", product_name)[:40]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe_name}_{timestamp}.png"
            filepath = save_dir / filename
            
            screenshot.save(filepath)
            print(f"Desktop screenshot saved successfully: {filename}")
            return str(filepath)
        except Exception as e:
            print(f"Error during desktop screenshot: {type(e).__name__}")
            return ""


def take_batch_screenshots_sync(screenshot_jobs: List[Dict[str, str]]):
    """Chụp ảnh màn hình cho hàng loạt sản phẩm từ file upload (tuần tự)"""
    import pyautogui
    import time
    import webbrowser
    from datetime import datetime
    from pathlib import Path
    import re

    # Định nghĩa thư mục lưu trữ (gốc dự án)
    save_dir = Path(__file__).resolve().parents[2] / "screenshots"
    save_dir.mkdir(exist_ok=True)

    for job in screenshot_jobs:
        product_name = job.get("product_name", "product")
        url = job.get("url")
        if not url or not url.startswith("http"):
            continue

        try:
            # Mở URL
            webbrowser.open(url)
            
            # Chờ 6 giây để trình duyệt tải xong trang
            time.sleep(6)

            # Chụp màn hình
            screenshot = pyautogui.screenshot()

            # Tạo tên file
            safe_name = re.sub(r"[^\w\-]", "_", product_name)[:40]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"batch_{safe_name}_{timestamp}.png"
            filepath = save_dir / filename

            # Lưu ảnh
            screenshot.save(filepath)
            print(f"Batch screenshot saved: {filename} for {url}")

            # Đóng tab trình duyệt bằng phím tắt
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(1.5)

        except Exception as e:
            print(f"Error during batch screenshot for {product_name}: {e}")


@router.post("/valuate")
async def valuate_product(request: ValuationRequest, background_tasks: BackgroundTasks):
    result = await run_in_threadpool(sync_valuate_product, request)
    
    # Tự động trigger chụp màn hình sau khi có giá
    urls = []
    try:
        val_res = result.get("valuation_result", {})
        ref_quotes = val_res.get("reference_quotes", [])
        for q in ref_quotes:
            url = q.get("url")
            if url and url.startswith("http"):
                urls.append(url)
    except Exception:
        pass
        
    background_tasks.add_task(take_desktop_screenshot_sync, request.product_name, urls)
    
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
async def valuate_batch(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    try:
        import pandas as pd
        import asyncio
        
        filename = file.filename.lower() if file.filename else ""
        is_excel = filename.endswith(('.xlsx', '.xls'))
        
        content = await file.read()
        
        if is_excel:
            # Đọc Excel bằng Pandas
            df = pd.read_excel(io.BytesIO(content), header=None)
            all_data = df.fillna("").values.tolist()
        else:
            # Đọc CSV
            try:
                decoded = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                decoded = content.decode("latin-1")
            
            reader = csv.reader(io.StringIO(decoded))
            all_data = list(reader)
            
        if not all_data:
            return {"status": "error", "message": "File tải lên trống."}
            
        headers = [str(x) for x in all_data[0]]
        rows = all_data[1:]
        
        # Tự động phát hiện cột chứa tên sản phẩm
        product_col_idx = _detect_product_column(headers)
        
        # Danh sách lưu các job chụp màn hình
        screenshot_jobs = []
        processed_rows = []
        
        # Xử lý song song theo batch (3 sản phẩm cùng lúc)
        BATCH_SIZE = 3
        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch_rows = rows[batch_start:batch_start + BATCH_SIZE]
            
            tasks = []
            for row in batch_rows:
                # Trích xuất tên sản phẩm
                if product_col_idx < len(row):
                    product_name = str(row[product_col_idx]).strip()
                else:
                    product_name = str(row[0]).strip() if row else ""
                    
                if product_name:
                    tasks.append(_process_single_product(product_name))
                else:
                    async def empty_result():
                        return {"price": "", "link": "", "note": "Bỏ qua vì tên sản phẩm trống"}
                    tasks.append(empty_result())
                    
            # Chạy song song
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Ghi kết quả vào danh sách các dòng đã xử lý
            for row, result in zip(batch_rows, results):
                if isinstance(result, Exception):
                    price, link, note = "", "", "AI không tìm được giá. Vui lòng liên hệ cơ sở, hệ thống buôn bán."
                else:
                    price = result.get("price", "")
                    link = result.get("link", "")
                    note = result.get("note", "")
                    
                # Thu thập link hợp lệ để chụp màn hình
                if link and link.startswith("http"):
                    # Xác định lại tên sản phẩm chính xác
                    if product_col_idx < len(row):
                        prod_name = str(row[product_col_idx]).strip()
                    else:
                        prod_name = str(row[0]).strip() if row else ""
                    if not prod_name:
                        prod_name = "product"
                    screenshot_jobs.append({"product_name": prod_name, "url": link})
                    
                # Định dạng giá cho Excel/CSV (luôn hiển thị dấu chấm và căn trái)
                if price and price not in ("Không đủ dữ liệu", "Không có dữ liệu"):
                    import re
                    num_str = re.sub(r'[^\d]', '', price)
                    if num_str:
                        formatted = f"{int(num_str):,}".replace(",", ".")
                        excel_price = f'="{formatted}"'
                    else:
                        excel_price = f'="{price}"'
                else:
                    excel_price = price
                    
                # Định dạng link cho Excel/CSV
                if link and link.startswith("http"):
                    excel_link = f'=HYPERLINK("{link}","{link}")'
                else:
                    excel_link = link
                    
                processed_rows.append(row + [excel_price, excel_link, note])
                
        # Thêm tác vụ chụp ảnh màn hình tuần tự vào background task (giới hạn tối đa 30 jobs)
        if screenshot_jobs and background_tasks:
            background_tasks.add_task(take_batch_screenshots_sync, screenshot_jobs[:30])
            
        output_headers = headers + ["Gia_du_kien", "Link_tham_khao", "Ghi_chu"]
        
        if is_excel:
            # Tạo DataFrame và ghi ra file Excel
            out_df = pd.DataFrame(processed_rows, columns=output_headers)
            out_buffer = io.BytesIO()
            out_df.to_excel(out_buffer, index=False, engine='openpyxl')
            out_buffer.seek(0)
            
            return StreamingResponse(
                out_buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=batch_valuation_result.xlsx"}
            )
        else:
            # Ghi ra file CSV
            output = io.StringIO()
            writer = csv.writer(output)
            output.write('\ufeff')  # BOM cho tiếng Việt hiển thị tốt trong Excel
            writer.writerow(output_headers)
            writer.writerows(processed_rows)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
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