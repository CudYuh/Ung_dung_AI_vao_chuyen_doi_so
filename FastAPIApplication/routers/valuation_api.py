import csv
import io
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch
from pydantic import BaseModel
from sqlalchemy import String, cast, or_

from database import session_local
from models import Product
from services.llm_wiki.legal_rules import load_legal_rules_for_ai


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
    category_hint = "general"
    assumptions: List[str] = []

    if re.search(r"\bip\s*\d+", plain):
        number = re.findall(r"\d+", plain)
        if number:
            normalized = f"iPhone {number[0]}"
            category_hint = "smartphone"
            assumptions.append(f"Người dùng nhập '{original}', hệ thống hiểu là '{normalized}'.")

    elif "iphone" in plain:
        category_hint = "smartphone"

    elif "sh mode" in plain:
        normalized = "Honda SH Mode 125 2024 2025"
        category_hint = "motorbike"
        assumptions.append(
            "Người dùng nhập SH Mode, hệ thống mở rộng thành Honda SH Mode 125 đời 2024/2025 để tìm giá tham khảo."
        )

    elif "vision" in plain:
        normalized = "Honda Vision 110 2024 2025"
        category_hint = "motorbike"
        assumptions.append(
            "Người dùng nhập Vision, hệ thống mở rộng thành Honda Vision 110 đời 2024/2025."
        )

    elif "air blade" in plain or "airblade" in plain:
        normalized = "Honda Air Blade 125 160 2024 2025"
        category_hint = "motorbike"
        assumptions.append(
            "Người dùng nhập Air Blade, hệ thống mở rộng thành Honda Air Blade 125/160 đời 2024/2025."
        )

    elif "xe may" in plain or "xe ga" in plain:
        category_hint = "motorbike"

    elif "may in" in plain:
        category_hint = "printer"

        if "canon" in plain:
            normalized = f"{original} chính hãng Việt Nam"

    elif "laptop" in plain:
        category_hint = "laptop"

    elif "dieu hoa" in plain or "may lanh" in plain:
        category_hint = "air_conditioner"

    elif "camera" in plain:
        category_hint = "camera"

    elif "ban" in plain:
        category_hint = "furniture"

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

    if len(prices) < 2:
        return {
            "consistent": False,
            "prices": prices,
            "deviation_pct": 0,
            "avg_price": prices[0] if prices else 0,
            "status": "insufficient",
            "suggested_price": prices[0] if prices else None,
            "message": "Chỉ tìm được 1 nguồn giá, cần ít nhất 2 nguồn để đối chiếu.",
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

    for quote in reference_quotes[:3]:
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


def search_in_db(product_name: str) -> Dict[str, Any]:
    db = session_local()

    try:
        search_query = f"%{product_name}%"

        products = db.query(Product).filter(
            or_(
                Product.name.ilike(search_query),
                Product.specifications.ilike(search_query),
                cast(Product.category, String).ilike(search_query),
                cast(Product.certificate_number, String).ilike(search_query),
            )
        ).all()

        if not products:
            return {
                "found": False,
                "data": f"Không tìm thấy '{product_name}' trong cơ sở dữ liệu nội bộ.",
                "items": [],
            }

        result_lines = [f"Tìm thấy {len(products)} kết quả trong cơ sở dữ liệu nội bộ:"]

        for p in products[:8]:
            result_lines.append(
                f"- Tên: {p.name} | Giá thẩm định: {p.price} VND "
                f"| Đơn vị: {p.unit} | Thông số: {p.specifications} "
                f"| Nguồn: {p.source} | Ngày: {p.appraisal_date}"
            )

        return {
            "found": True,
            "data": "\n".join(result_lines),
            "items": products[:8],
        }

    except Exception as e:
        return {
            "found": False,
            "data": f"Lỗi khi truy vấn cơ sở dữ liệu: {str(e)}",
            "items": [],
        }

    finally:
        db.close()


KNOWLEDGE_STOPWORDS = {
    "gia",
    "moi",
    "nhat",
    "viet",
    "nam",
    "chinh",
    "hang",
    "tham",
    "khao",
    "bao",
    "ban",
    "san",
    "pham",
    "hang",
    "hoa",
    "thiet",
    "bi",
    "may",
    "xe",
    "doi",
    "phien",
    "ban",
    "tieu",
    "chuan",
    "cao",
    "cap",
    "the",
    "thao",
    "dac",
    "biet",
    "cai",
    "bo",
    "chiec",
    "nam",
}


BRAND_TOKENS = {
    "honda",
    "iphone",
    "apple",
    "canon",
    "dell",
    "hp",
    "lenovo",
    "asus",
    "acer",
    "samsung",
    "lg",
    "sony",
    "daikin",
    "panasonic",
    "cisco",
    "hikvision",
    "dahua",
}


def short_text(value: Any, max_length: int = 350) -> str:
    text = str(value or "").strip()

    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def knowledge_query_tokens(product_name: str) -> set[str]:
    """
    Lấy token quan trọng để lọc kết quả LLM Wiki.

    Mục tiêu:
    - Bỏ các số năm như 2024, 2025 vì dễ làm match sai.
    - Bỏ token chung chung như giá, mới, Việt Nam.
    - Giữ lại brand/model quan trọng như honda, sh, mode, iphone, canon...
    """

    normalized = normalize_text(product_name)
    raw_tokens = normalized.split()

    tokens: set[str] = set()

    for token in raw_tokens:
        if not token:
            continue

        # Bỏ năm 19xx/20xx vì dễ match nhầm với sản phẩm khác
        if token.isdigit():
            number = int(token)

            if 1900 <= number <= 2099:
                continue

            # Bỏ các số quá chung chung trong truy vấn AI
            if len(token) >= 4:
                continue

        # Giữ token ngắn đặc biệt như SH, IP
        if len(token) < 3 and token not in {"sh", "ip"}:
            continue

        if token in KNOWLEDGE_STOPWORDS:
            continue

        tokens.add(token)

    return tokens


def knowledge_item_text(item: Dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                str(item.get("name") or ""),
                str(item.get("category") or ""),
                str(item.get("unit") or ""),
                str(item.get("specifications") or ""),
                str(item.get("source") or ""),
            ]
        )
    )


def is_relevant_knowledge_item(
    item: Dict[str, Any],
    core_tokens: set[str],
) -> bool:
    if not core_tokens:
        return False

    text = knowledge_item_text(item)

    if not text:
        return False

    matched_tokens = {token for token in core_tokens if token in text}

    # Nếu truy vấn có brand rõ ràng, ví dụ Honda, iPhone, Canon,
    # thì kết quả LLM Wiki bắt buộc phải chứa brand đó.
    query_brands = core_tokens & BRAND_TOKENS

    if query_brands and not any(brand in text for brand in query_brands):
        return False

    # Với truy vấn có nhiều token, cần ít nhất 2 token khớp.
    # Ví dụ Honda SH Mode phải khớp ít nhất Honda + Mode hoặc Honda + SH.
    if len(core_tokens) >= 3:
        return len(matched_tokens) >= 2

    # Với truy vấn ngắn hơn, chỉ cần 1 token khớp.
    return len(matched_tokens) >= 1


def search_in_knowledge_layer(product_name: str) -> str:
    """
    Tìm trong LLM Wiki nhưng lọc chặt để tránh kết quả không liên quan.

    Ví dụ:
    - Query: Honda SH Mode 125 2024 2025
    - Không được trả Tivi chỉ vì có năm 2024 trong thông số.
    """

    try:
        from services.llm_wiki.framework import search_wiki

        raw_results = search_wiki(product_name, limit=40)

        if not raw_results:
            return f"Không tìm thấy '{product_name}' trong kho tri thức nội bộ."

        core_tokens = knowledge_query_tokens(product_name)

        filtered_results = []

        seen_ids = set()

        for item in raw_results:
            item_id = item.get("source_id") or item.get("id") or item.get("name")

            if item_id in seen_ids:
                continue

            if not is_relevant_knowledge_item(item, core_tokens):
                continue

            seen_ids.add(item_id)
            filtered_results.append(item)

            if len(filtered_results) >= 5:
                break

        if not filtered_results:
            return (
                f"Không tìm thấy dữ liệu nội bộ phù hợp cho '{product_name}'. "
                "Kho tri thức không có vật tư tương tự đủ liên quan, hệ thống sẽ ưu tiên nguồn Internet và luật định giá."
            )

        lines = [f"Tìm thấy {len(filtered_results)} kết quả phù hợp trong kho tri thức nội bộ:"]

        for item in filtered_results:
            lines.append(
                f"- Tên: {item.get('name')} | Giá: {item.get('price')} VND "
                f"| Đơn vị: {item.get('unit')} | Nguồn: {item.get('source')} "
                f"| Ngày: {item.get('appraisal_date')} "
                f"| Thông số: {short_text(item.get('specifications'), 350)}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Không truy vấn được kho tri thức nội bộ: {str(e)}"


def extract_tavily_results(raw_results: Any) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    if isinstance(raw_results, dict):
        raw_items = raw_results.get("results") or []

        if isinstance(raw_items, list):
            iterable = raw_items
        else:
            iterable = [{"content": str(raw_items), "url": "", "title": ""}]

    elif isinstance(raw_results, list):
        iterable = raw_results

    else:
        iterable = [{"content": str(raw_results), "url": "", "title": ""}]

    for item in iterable:
        if not isinstance(item, dict):
            items.append(
                {
                    "title": "",
                    "content": str(item),
                    "url": "",
                }
            )
            continue

        title = str(item.get("title") or "")
        content = str(item.get("content") or item.get("snippet") or item.get("answer") or "")
        url = str(item.get("url") or "")

        if title.strip() or content.strip():
            items.append(
                {
                    "title": title,
                    "content": content,
                    "url": url,
                }
            )

    return items


def build_internet_queries(product_name: str, category_hint: str) -> List[str]:
    base = product_name.strip()

    queries = [
        f"giá {base} mới nhất Việt Nam",
        f"{base} giá chính hãng Việt Nam",
        f"{base} báo giá mới nhất",
        f"{base} giá tham khảo đại lý",
    ]

    if category_hint == "motorbike":
        queries.extend(
            [
                f"giá xe {base} Honda Việt Nam",
                f"{base} giá niêm yết Honda Việt Nam",
                f"{base} giá lăn bánh 2024 2025",
                f"{base} phiên bản CBS ABS giá bán",
                f"{base} giá đại lý xe máy Việt Nam",
            ]
        )

    elif category_hint == "smartphone":
        queries.extend(
            [
                f"{base} giá CellphoneS FPT Shop Thế Giới Di Động",
                f"{base} VN/A giá chính hãng Apple Việt Nam",
                f"{base} giá bán lẻ chính hãng",
            ]
        )

    elif category_hint == "printer":
        queries.extend(
            [
                f"{base} giá máy in chính hãng",
                f"{base} giá Nguyễn Kim Điện Máy Xanh",
            ]
        )

    elif category_hint == "laptop":
        queries.extend(
            [
                f"{base} giá laptop chính hãng Việt Nam",
                f"{base} giá FPT Shop CellphoneS Thế Giới Di Động",
            ]
        )

    elif category_hint == "air_conditioner":
        queries.extend(
            [
                f"{base} giá điều hòa Điện Máy Xanh Nguyễn Kim",
                f"{base} giá chính hãng Việt Nam",
            ]
        )

    return list(dict.fromkeys(queries))


def search_on_internet(product_name: str, category_hint: str) -> str:
    if not os.environ.get("TAVILY_API_KEY"):
        return "Không tìm thấy thông tin trên Internet do chưa cấu hình Tavily API key."

    try:
        tavily_search = TavilySearch(max_results=3)
    except Exception as e:
        return f"Không khởi tạo được công cụ tìm kiếm Internet: {str(e)}"

    queries = build_internet_queries(product_name, category_hint)
    all_items: List[Dict[str, str]] = []

    # Giới hạn 3 queries để tiết kiệm thời gian cho Ollama local
    for query in queries[:3]:
        try:
            raw_results = tavily_search.invoke(query)
            items = extract_tavily_results(raw_results)

            for item in items:
                item["query"] = query
                all_items.append(item)

        except Exception as e:
            all_items.append(
                {
                    "title": "Lỗi tìm kiếm",
                    "content": f"Lỗi khi tìm kiếm query '{query}': {str(e)}",
                    "url": "",
                    "query": query,
                }
            )

        # Dừng sớm nếu đã đủ kết quả
        if len(all_items) >= 6:
            break

    if not all_items:
        return "Không tìm thấy thông tin trên Internet."

    formatted = []

    # Giới hạn 6 nguồn, cắt nội dung 200 ký tự để giảm token cho model local
    for idx, item in enumerate(all_items[:6], start=1):
        title = item.get("title") or "Nguồn tham khảo"
        content = item.get("content") or ""
        if len(content) > 200:
            content = content[:200] + "..."
        url = item.get("url") or ""

        formatted.append(
            f"[{idx}] {title}\nURL: {url}\n{content}"
        )

    return "\n\n".join(formatted)


def sync_valuate_product(request: ValuationRequest):
    user_query = request.product_name.strip()
    understood = understand_product_query(user_query)

    product_name = understood["normalized"]
    category_hint = understood["category_hint"]
    assumptions = understood["assumptions"]

    try:
        db_result = search_in_db(product_name)
        knowledge_data = search_in_knowledge_layer(product_name)

        if db_result["found"]:
            data_source = "database_internal"
            internet_data = "Đã có dữ liệu nội bộ."
        else:
            data_source = "internet_ai"
            internet_data = search_on_internet(product_name, category_hint)

        # Rút gọn raw_data để giảm token cho model local
        raw_data = (
            f"[Truy vấn]\n{user_query} -> {product_name}\n\n"
            f"[DB nội bộ]\n{db_result['data']}\n\n"
            f"[Kho tri thức]\n{knowledge_data}\n\n"
            f"[Internet]\n{internet_data}"
        )

        if (
            "chưa cấu hình Tavily" in raw_data
            or "Không tìm thấy thông tin trên Internet" in raw_data
        ) and not db_result["found"]:
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
                    "Không có dữ liệu nội bộ và không có dữ liệu Internet đủ tin cậy.",
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
1. Đưa ra mức giá định giá dự kiến bằng VND nếu có đủ dữ liệu.
2. Ưu tiên dữ liệu nội bộ và kho tri thức nội bộ trước khi dùng Internet.
3. Với vật tư, thiết bị, hàng hóa phổ thông, ưu tiên cách tiếp cận từ thị trường.
4. Nếu truy vấn người dùng mơ hồ nhưng vẫn đoán được sản phẩm, phải ghi rõ giả định trong basis.
5. Nếu thiếu phiên bản, đời máy, cấu hình, tình trạng, phải ghi rõ giả định định giá.
6. KHÔNG ĐƯỢC bịa giá. GIÁ PHẢI CHÍNH XÁC Y HỆT THEO URL, không tự làm tròn.
7. Không được trả final_price rỗng, không được chỉ trả "VND" hoặc "VNĐ".
8. Nếu không đủ dữ liệu, final_price phải là "Không đủ dữ liệu định giá".
9. confidence chỉ được là một trong ba giá trị: "cao", "trung bình", "thấp".
10. legal_compliance phải nêu hệ thống đã tuân thủ quy tắc nào.
11. SỐ LƯỢNG KẾT QUẢ: ƯU TIÊN CAO NHẤT LÀ TRẢ VỀ ĐÚNG 2 NGUỒN THAM KHẢO GIÁ KHÁC NHAU. Hãy cố gắng hết sức tìm 2 kết quả. Nếu dữ liệu hoàn toàn chỉ có 1 kết quả hợp lệ thì mới được trả về 1.
12. TIÊU CHÍ CHỌN & CẤM BỊA ĐẶT: 
   - Chỉ chọn kết quả KHỚP ĐÚNG SẢN PHẨM và BẮT BUỘC PHẢI CÓ CON SỐ GIÁ TIỀN bên trong đoạn văn của kết quả đó.
   - TUYỆT ĐỐI KHÔNG LẤY GIÁ CỦA SẢN PHẨM NÀY GHÉP CHO SẢN PHẨM KHÁC. Nếu kết quả không ghi giá, BẮT BUỘC BỎ QUA.
13. URL CHÍNH XÁC: Trường "url" BẮT BUỘC phải là link hợp lệ lấy từ phần Dữ liệu (bắt đầu bằng http/https). Tuyệt đối không được bỏ trống.

Trả về DUY NHẤT một JSON object theo định dạng:

{{
  "reference_quotes": [
    {{
      "description": "Tên trang - Tên sản phẩm chính xác 1",
      "price": "Mức giá bằng VND, ví dụ: 62.700.000",
      "url": "https://url-thuc-te-cua-trang-web-1.com"
    }},
    {{
      "description": "Tên trang - Tên sản phẩm chính xác 2",
      "price": "Mức giá bằng VND, ví dụ: 63.500.000",
      "url": "https://url-thuc-te-cua-trang-web-2.com"
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


# Rate limiter cho Tavily API — đảm bảo mỗi call cách nhau ít nhất 1.5s
_tavily_lock = threading.Lock()
_tavily_last_call_time = 0.0


def _rate_limited_tavily_call(tavily_search, query: str) -> Any:
    """Gọi Tavily API với rate limit: tối thiểu 1.5s giữa các lần gọi."""
    global _tavily_last_call_time
    with _tavily_lock:
        now = time.time()
        wait = 1.5 - (now - _tavily_last_call_time)
        if wait > 0:
            time.sleep(wait)
        _tavily_last_call_time = time.time()
    return tavily_search.invoke(query)


def _search_duckduckgo(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Tìm kiếm bằng DuckDuckGo (bắt lỗi rate limit nếu có)."""
    if not DDGS:
        return []
    try:
        items = []
        with DDGS() as ddgs:
            # Dùng backend lite/html thường ổn định hơn
            results = ddgs.text(query, max_results=max_results, backend="lite")
            for r in results:
                items.append({
                    "title": r.get("title", ""),
                    "content": r.get("body", ""),
                    "url": r.get("href", "")
                })
        return items
    except Exception:
        return []


def _sync_search_internet_for_batch(product_name: str) -> Dict[str, Any]:
    """
    Tìm kiếm Internet cho 1 sản phẩm trong batch.
    Sử dụng rate limiter để tránh Tavily bị chặn.
    """
    if not os.environ.get("TAVILY_API_KEY"):
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    try:
        tavily_search = TavilySearch(max_results=5)
    except Exception:
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    # Dùng 2 queries ngắn gọn
    queries = [
        f"giá {product_name} chính hãng Việt Nam",
        f"{product_name} giá bán",
    ]

    all_items: List[Dict[str, str]] = []

    for query in queries:
        # Ưu tiên tìm bằng Tavily trước
        for attempt in range(3):
            try:
                raw_results = _rate_limited_tavily_call(tavily_search, query)
                items = extract_tavily_results(raw_results)
                for item in items:
                    item["query"] = query
                    item["source"] = "tavily"
                    all_items.append(item)
                break
            except Exception:
                wait_time = 2 * (attempt + 1)  # 2s, 4s, 6s
                time.sleep(wait_time)
                continue

        # Thoát nếu đã có đủ dữ liệu từ Tavily
        if len(all_items) >= 5:
            break

    # Nếu Tavily trả về quá ít dữ liệu (hoặc không có), dùng DuckDuckGo để bổ trợ
    if len(all_items) < 3:
        for query in queries:
            ddg_results = _search_duckduckgo(query, max_results=3)
            for r in ddg_results:
                r["query"] = query
                r["source"] = "duckduckgo"
                all_items.append(r)
            
            if len(all_items) >= 5:
                break

    if not all_items:
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    # Format kết quả cho LLM - Tối ưu hóa để tiết kiệm token
    formatted = []
    # Chỉ lấy tối đa 5 kết quả tốt nhất thay vì 10 để tiết kiệm token
    for idx, item in enumerate(all_items[:5], start=1):
        title = item.get("title") or ""
        content = item.get("content") or ""
        # Cắt ngắn nội dung còn 300 ký tự (đủ để AI đọc được giá xung quanh từ khóa)
        if len(content) > 300:
            content = content[:300] + "..."
            
        url = item.get("url") or ""
        source = item.get("source") or "unknown"
        formatted.append(
            f"[{idx}] (Nguồn: {source}) {title}\nURL: {url}\n{content}"
        )
    internet_data = "\n\n".join(formatted)

    # Dùng LLM để trích xuất giá (model nhẹ cho batch)
    llm = ChatOllama(
        model="qwen2.5:3b",
        temperature=0,
        format="json",
        num_predict=256,
    )

    prompt = f"""Trích xuất giá bán của sản phẩm "{product_name}" từ dữ liệu sau.

{internet_data}

Trả về JSON:
{{
  "final_price": "giá VND thấp nhất nếu có nhiều mức giá (chỉ trả về 1 số ví dụ: 15.990.000), hoặc ghi: Không đủ dữ liệu định giá",
  "url": "URL nguồn có giá (bắt đầu bằng https://)",
  "description": "tên nguồn"
}}"""

    try:
        response = llm.invoke(prompt)
        result = safe_json_loads(response.content)
        return {
            "price": str(result.get("final_price", "")).strip(),
            "url": str(result.get("url", "")).strip(),
            "description": str(result.get("description", "")).strip(),
            "confidence": "trung bình",
        }
    except Exception:
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}


async def _process_single_product(product_name: str) -> Dict[str, str]:
    """Xử lý 1 sản phẩm: tìm DB → nếu không có thì AI search."""
    try:
        db_result = await run_in_threadpool(search_in_db, product_name)

        if db_result["found"] and len(db_result["items"]) > 0:
            best_match = db_result["items"][0]
            product_norm = normalize_text(product_name)
            for item in db_result["items"]:
                item_norm = normalize_text(item.name or "")
                if product_norm in item_norm or item_norm in product_norm:
                    best_match = item
                    break

            price = extract_lowest_price(str(best_match.price))
            link = str(best_match.source or "")
            if not link.startswith("http"):
                link = ""
            note = "Có sẵn trong DB"
        else:
            ai_result = await run_in_threadpool(
                _sync_search_internet_for_batch, product_name
            )

            price = extract_lowest_price(ai_result.get("price", ""))
            link = ai_result.get("url", "")
            note = "AI tìm kiếm"

            if link and not link.startswith("http"):
                link = ""

            if has_price_number(price):
                note = "AI tìm kiếm & Đã lưu DB"

                def save_to_db_sync(prod_name, prc, lnk, desc):
                    db = session_local()
                    try:
                        from sqlalchemy import func
                        from datetime import datetime
                        from services.llm_wiki.framework import sync_product_to_wiki

                        max_id = db.query(func.max(Product.id)).scalar() or 0
                        new_id = float(int(max_id) + 1)

                        new_product = Product(
                            id=new_id,
                            name=prod_name,
                            price=prc,
                            source=lnk or "Internet AI",
                            specifications=desc[:500] if desc else "",
                            category=None,
                            unit="Cái",
                            appraisal_date=datetime.now().strftime("%d/%m/%Y"),
                            appraiser="AI System Batch",
                            certificate_number="AIB-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                        )
                        db.add(new_product)
                        db.commit()
                        db.refresh(new_product)

                        try:
                            sync_product_to_wiki(new_product)
                        except Exception:
                            pass
                    finally:
                        db.close()

                try:
                    await run_in_threadpool(
                        save_to_db_sync,
                        product_name,
                        price,
                        link,
                        ai_result.get("description", ""),
                    )
                except Exception:
                    pass
            else:
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

                    # Wrap link trong công thức HYPERLINK để bấm được trong Excel
                    if link and link.startswith("http"):
                        excel_link = f'=HYPERLINK("{link}","{link}")'
                    else:
                        excel_link = link

                    writer.writerow(row + [price, excel_link, note])
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