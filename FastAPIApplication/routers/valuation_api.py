import csv
import io
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from pydantic import BaseModel
from sqlalchemy import String, cast, or_

from database import session_local
from models import Product
from services.llm_wiki.legal_rules import load_legal_rules_for_ai


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
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

        normalized_quotes.append(
            {
                "description": str(quote.get("description") or "Nguồn tham khảo").strip(),
                "price": str(quote.get("price") or "Không rõ").strip(),
                "url": str(quote.get("url") or "").strip(),
            }
        )

    final_price = str(result.get("final_price") or "").strip()
    basis = str(result.get("basis") or "").strip()
    confidence = str(result.get("confidence") or "thấp").strip().lower()
    reason = str(result.get("reason") or "").strip()

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
        tavily_search = TavilySearch(max_results=5)
    except Exception as e:
        return f"Không khởi tạo được công cụ tìm kiếm Internet: {str(e)}"

    queries = build_internet_queries(product_name, category_hint)
    all_items: List[Dict[str, str]] = []

    for query in queries[:7]:
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

    if not all_items:
        return "Không tìm thấy thông tin trên Internet."

    formatted = []

    for idx, item in enumerate(all_items[:12], start=1):
        title = item.get("title") or "Nguồn tham khảo"
        content = item.get("content") or ""
        url = item.get("url") or ""
        query = item.get("query") or ""

        formatted.append(
            f"[Nguồn {idx}]\n"
            f"Truy vấn: {query}\n"
            f"Tiêu đề: {title}\n"
            f"Nội dung: {content}\n"
            f"URL: {url}"
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
        legal_rules = load_legal_rules_for_ai()

        if db_result["found"]:
            data_source = "database_internal"
            internet_data = "Không cần tìm Internet vì đã có dữ liệu nội bộ."
        else:
            data_source = "internet_ai"
            internet_data = search_on_internet(product_name, category_hint)

        raw_data = (
            f"[Truy vấn người dùng]\n{user_query}\n\n"
            f"[Truy vấn đã chuẩn hóa]\n{product_name}\n\n"
            f"[Giả định xử lý]\n{json.dumps(assumptions, ensure_ascii=False)}\n\n"
            f"[Cơ sở dữ liệu nội bộ]\n{db_result['data']}\n\n"
            f"[Kho tri thức nội bộ]\n{knowledge_data}\n\n"
            f"[Luật và chuẩn mực định giá]\n{legal_rules}\n\n"
            f"[Kết quả tìm kiếm Internet]\n{internet_data}"
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

        llm = ChatGroq(
            temperature=0,
            model="llama-3.3-70b-versatile",
        ).bind(
            response_format={"type": "json_object"}
        )

        prompt = f"""
Bạn là chuyên gia hỗ trợ định giá tài sản doanh nghiệp tại Việt Nam.

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
6. Không được bịa giá nếu dữ liệu không có số tiền cụ thể.
7. Không được trả final_price rỗng, không được chỉ trả "VND" hoặc "VNĐ".
8. Nếu không đủ dữ liệu, final_price phải là "Không đủ dữ liệu định giá".
9. confidence chỉ được là một trong ba giá trị: "cao", "trung bình", "thấp".
10. legal_compliance phải nêu hệ thống đã tuân thủ quy tắc nào.
11. BẮT BUỘC chỉ đưa ra 2 đến 3 nguồn tham khảo giá (reference_quotes).
12. Các nguồn tham khảo Internet phải ưu tiên chọn lọc từ các shop, sàn thương mại điện tử, hoặc hệ thống bán lẻ uy tín (như Shopee Mall, LazMall, Tiki, Thế Giới Di Động, FPT Shop, CellphoneS, Điện Máy Xanh, Nguyễn Kim...).

Trả về DUY NHẤT một JSON object theo định dạng:

{{
  "reference_quotes": [
    {{
      "description": "Mô tả ngắn gọn nguồn tham khảo hoặc sản phẩm tham chiếu",
      "price": "Mức giá bằng VND, ví dụ: 62.700.000",
      "url": "URL hoặc tên nguồn"
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

@router.post("/valuate")
async def valuate_product(request: ValuationRequest):
    return await run_in_threadpool(sync_valuate_product, request)

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
            output = io.StringIO()
            writer = csv.writer(output)
            
            headers = next(reader, None)
            if headers is None:
                yield "File CSV trống."
                return
            
            # Thêm BOM để Excel đọc được tiếng Việt
            yield '\ufeff'
                
            output_headers = headers + ["Gia_du_kien", "Link_tham_khao", "Ghi_chu"]
            writer.writerow(output_headers)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            
            for row in reader:
                if not row or not any(row):
                    continue
                    
                product_name = row[0].strip()
                if not product_name:
                    writer.writerow(row + ["", "", "Bỏ qua vì tên sản phẩm trống"])
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
                    continue
                    
                try:
                    db_result = await run_in_threadpool(search_in_db, product_name)
                    
                    if db_result["found"] and len(db_result["items"]) > 0:
                        p = db_result["items"][0]
                        price = str(p.price)
                        link = str(p.source)
                        note = "Có sẵn trong DB"
                    else:
                        req = ValuationRequest(product_name=product_name)
                        res = await run_in_threadpool(sync_valuate_product, req)
                        
                        if res.get("status") == "success":
                            val = res.get("valuation_result", {})
                            price = str(val.get("final_price", ""))
                            
                            quotes = val.get("reference_quotes", [])
                            link = str(quotes[0].get("url", "")) if quotes else ""
                            note = "Tìm bằng AI & Đã lưu DB"
                            
                            if has_price_number(price):
                                def save_to_db_sync(prod_name, prc, lnk, basis):
                                    db = session_local()
                                    try:
                                        from sqlalchemy import func
                                        from datetime import datetime
                                        from services.llm_wiki.framework import sync_product_to_wiki
                                        
                                        max_id = db.query(func.max(Product.id)).scalar() or 0
                                        new_id = int(max_id) + 1
                                        
                                        new_product = Product(
                                            id=new_id,
                                            name=prod_name,
                                            price=prc,
                                            source=lnk,
                                            specifications=basis,
                                            category="Tài sản định giá (Batch)",
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
                                        res.get("product") or product_name,
                                        price,
                                        link or "Internet AI",
                                        str(val.get("basis", ""))[:500]
                                    )
                                except Exception as db_err:
                                    note += f" (Lỗi lưu DB: {str(db_err)})"
                        else:
                            price = ""
                            link = ""
                            note = res.get("error", "Lỗi định giá AI")
                            
                except Exception as e:
                    price = ""
                    link = ""
                    note = str(e)
                    
                writer.writerow(row + [price, link, note])
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