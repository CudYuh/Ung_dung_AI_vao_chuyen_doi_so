"""
Tavily Search Service
======================
Sử dụng Tavily API để tìm kiếm giá sản phẩm trên Internet.

Chiến lược:
1. Tìm kiếm ưu tiên trên whitelist domains (domain_registry.json)
2. Lọc bỏ link bài báo / tin tức / blog / review
3. Chỉ giữ link trang bán hàng thực sự
4. Trích xuất giá chính xác (giá sau giảm nếu có khuyến mãi)

Thay thế cho Google Search Grounding.
"""

import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ---------------------------------------------------------------------------
# Danh sách domain tin tức / bài báo / blog CẦN LOẠI TRỪ
# ---------------------------------------------------------------------------
NEWS_DOMAINS = {
    # Báo chí / Tin tức Việt Nam
    "vnexpress.net",
    "dantri.com.vn",
    "thanhnien.vn",
    "tuoitre.vn",
    "zing.vn",
    "zingnews.vn",
    "kenh14.vn",
    "24h.com.vn",
    "baomoi.com",
    "cafef.vn",
    "vov.vn",
    "vtv.vn",
    "nhandan.vn",
    "laodong.vn",
    "vietnamnet.vn",
    "soha.vn",
    "doisongphapluat.com",
    "nguoiduatin.vn",
    "congluan.vn",
    "anninhthudo.vn",
    "vietgiaitri.com",
    "kienthuc.net.vn",
    # Blog / Review / Công nghệ
    "tinhte.vn",
    "genk.vn",
    "techz.vn",
    "vietcetera.com",
    "voz.vn",
    "otofun.net",
    # Mạng xã hội / Video / Wiki
    "wikipedia.org",
    "youtube.com",
    "facebook.com",
    "tiktok.com",
    "reddit.com",
    "quora.com",
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "zalo.me",
    # Trang so sánh giá (không phải trang bán hàng trực tiếp)
    "websosanh.vn",
    "priceprice.com",
}

# Path patterns cho bài viết / tin tức (không phải trang sản phẩm)
NEWS_PATH_PATTERNS = [
    "/tin-tuc/",
    "/bai-viet/",
    "/news/",
    "/blog/",
    "/review/",
    "/danh-gia/",
    "/so-sanh/",
    "/cam-nang/",
    "/kinh-nghiem/",
    "/huong-dan/",
    "/meo-vat/",
    "/article/",
    "/post/",
    "/tag/",
    "/category/",
    "/author/",
    "/wiki/",
    "/video/",
    "/podcast/",
    "/phong-su/",
    "/su-kien/",
    "/goc-nhin/",
    "/y-kien/",
    "/binh-luan/",
    "/thu-thuat/",
    "/kinh-te/",
    "/xa-hoi/",
    "/the-gioi/",
    "/giai-tri/",
    "/the-thao/",
    "/khoa-hoc/",
    "/cong-nghe/",  # Chỉ khi trong context báo chí
    "/search",
    "/tim-kiem",
    "/danh-muc",
    "/collections/",
    "/cua-hang/",
    "/tags/",
    "/c/",
    "/cat/",
    "/loai/",
    "/thuong-hieu/",
    "/brand/",
    "/product-category/",
    "/danh-sach/",
    "/dien-thoai/",
    "/may-tinh-bang/",
    "/laptop/",
    "/dong-ho/",
]


# ---------------------------------------------------------------------------
# Utility: phân tích domain từ URL
# ---------------------------------------------------------------------------
def _extract_domain(url: str) -> str:
    """Trích xuất domain gốc từ URL (bỏ www.)."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _extract_path(url: str) -> str:
    """Trích xuất path từ URL."""
    try:
        parsed = urlparse(url)
        return parsed.path.lower()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Hàm check link: is_valid_shopping_link
# ---------------------------------------------------------------------------
def is_valid_shopping_link(url: str) -> bool:
    """
    Kiểm tra URL có phải link trang bán hàng thực sự hay không.

    Loại bỏ:
    - URL thuộc domain tin tức / bài báo / blog / review
    - URL có path pattern của bài viết (tin-tuc, blog, review, ...)
    - URL là trang chủ (chỉ có domain, không có path sản phẩm)
    - URL không hợp lệ (không bắt đầu bằng http)

    Giữ lại:
    - URL của trang bán hàng có path cụ thể đến sản phẩm

    Returns:
        True nếu URL hợp lệ (link trang bán hàng), False nếu không.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # Phải bắt đầu bằng http
    if not url.startswith("http"):
        return False

    domain = _extract_domain(url)
    path = _extract_path(url)

    if not domain:
        return False

    # ----- Bước 1: Loại bỏ domain tin tức / blog -----
    for news_domain in NEWS_DOMAINS:
        if domain == news_domain or domain.endswith("." + news_domain):
            return False

    # ----- Bước 2: Loại bỏ URL có path pattern bài viết hoặc danh mục/tìm kiếm -----
    for pattern in NEWS_PATH_PATTERNS:
        if pattern in path:
            return False

    # ----- Bước 2.5: Loại bỏ URL có tham số query của chức năng tìm kiếm -----
    try:
        parsed_url = urlparse(url)
        query_string = parsed_url.query.lower()
        if "q=" in query_string or "keyword=" in query_string or "tu-khoa=" in query_string or "search=" in query_string:
            return False
    except Exception:
        pass

    # ----- Bước 3: Loại bỏ URL là trang chủ -----
    # Trang chủ: path rỗng hoặc chỉ là "/"
    clean_path = path.rstrip("/")
    if not clean_path or clean_path == "":
        return False

    # ----- Bước 4: URL pass hết bộ lọc → hợp lệ -----
    return True


def filter_valid_shopping_links(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Lọc danh sách kết quả tìm kiếm, chỉ giữ lại link trang bán hàng hợp lệ.

    Args:
        items: Danh sách dict có key "url"

    Returns:
        Danh sách đã lọc chỉ chứa link trang bán hàng.
    """
    filtered = []
    for item in items:
        url = item.get("url", "")
        if is_valid_shopping_link(url):
            filtered.append(item)
        else:
            if url:
                print(f"[LinkFilter] Loại bỏ URL không hợp lệ: {url}")
    return filtered


# ---------------------------------------------------------------------------
# Rate limiter cho Tavily API (thread-safe)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Trích xuất kết quả từ Tavily response
# ---------------------------------------------------------------------------
def extract_tavily_results(raw_results: Any) -> List[Dict[str, str]]:
    """
    Parse kết quả từ Tavily Search thành list chuẩn.

    Returns:
        List[{"title": "...", "content": "...", "url": "..."}]
    """
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


# ---------------------------------------------------------------------------
# Tìm kiếm sản phẩm trên Internet bằng Tavily
# ---------------------------------------------------------------------------
def search_product_tavily(
    product_name: str,
    category_hint: str = "general",
    max_queries: int = 3,
) -> List[Dict[str, str]]:
    """
    Tìm kiếm sản phẩm trên Internet bằng Tavily API.
    Ưu tiên whitelist domains theo category.

    Args:
        product_name: Tên sản phẩm cần tìm
        category_hint: Danh mục sản phẩm (smartphone, laptop, ...)
        max_queries: Số lượng query tối đa gửi đi

    Returns:
        List[{"title": "...", "content": "...", "url": "..."}]
        Đã qua bộ lọc is_valid_shopping_link().
    """
    from langchain_tavily import TavilySearch
    from routers.domain_registry import get_domains_for_category

    if not os.environ.get("TAVILY_API_KEY"):
        print("[TavilySearch] ERROR: TAVILY_API_KEY not found in .env")
        return []

    # Lấy domain ưu tiên theo category
    priority_domains = get_domains_for_category(category_hint)
    print(f"[TavilySearch] Product: '{product_name}', Category: '{category_hint}', "
          f"Whitelist domains: {len(priority_domains)} → {priority_domains[:5]}")

    # Tạo danh sách queries
    queries = _build_search_queries(product_name, category_hint)

    all_items: List[Dict[str, str]] = []

    # ----- Phase 1: Tìm trên whitelist domains -----
    try:
        if priority_domains:
            tavily_search = TavilySearch(
                max_results=5,
                include_domains=priority_domains,
            )
        else:
            tavily_search = TavilySearch(max_results=5)
    except Exception as e:
        print(f"[TavilySearch] ERROR khởi tạo: {str(e)}")
        return []

    for query in queries[:max_queries]:
        for attempt in range(3):
            try:
                raw_results = _rate_limited_tavily_call(tavily_search, query)
                items = extract_tavily_results(raw_results)

                for item in items:
                    item["query"] = query
                    item["source"] = "tavily_whitelist"
                    all_items.append(item)
                break
            except Exception as e:
                wait_time = 2 * (attempt + 1)  # 2s, 4s, 6s
                print(f"[TavilySearch] Retry {attempt+1}/3 cho query '{query}': {str(e)}")
                time.sleep(wait_time)
                continue

        if len(all_items) >= 6:
            break

    print(f"[TavilySearch] Phase 1 (whitelist): {len(all_items)} kết quả thô")

    # ----- Lọc link hợp lệ -----
    valid_items = filter_valid_shopping_links(all_items)
    print(f"[TavilySearch] Sau khi lọc link: {len(valid_items)} kết quả hợp lệ")

    # ----- Phase 2: Fallback nếu không đủ kết quả -----
    if len(valid_items) < 2 and priority_domains:
        print("[TavilySearch] Phase 2: Fallback tìm không giới hạn domain...")
        try:
            tavily_fallback = TavilySearch(max_results=5)
            for query in queries[:2]:
                for attempt in range(2):
                    try:
                        raw_results = _rate_limited_tavily_call(tavily_fallback, query)
                        items = extract_tavily_results(raw_results)
                        for item in items:
                            item["query"] = query
                            item["source"] = "tavily_fallback"
                            all_items.append(item)
                        break
                    except Exception:
                        time.sleep(2 * (attempt + 1))
                        continue
                if len(all_items) >= 8:
                    break
        except Exception:
            pass

        # Lọc lại toàn bộ
        valid_items = filter_valid_shopping_links(all_items)
        print(f"[TavilySearch] Sau fallback + lọc: {len(valid_items)} kết quả hợp lệ")

    # Deduplicate theo URL
    seen_urls: set = set()
    deduped: List[Dict[str, str]] = []
    for item in valid_items:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(item)
        elif not url:
            deduped.append(item)

    return deduped[:8]


def _build_search_queries(product_name: str, category_hint: str) -> List[str]:
    """Tạo danh sách search queries tối ưu theo category."""
    base = product_name.strip()

    queries = [
        f"giá {base} mới nhất Việt Nam",
        f"{base} giá chính hãng Việt Nam",
        f"{base} giá bán",
    ]

    if category_hint == "motorbike":
        queries.extend([
            f"giá xe {base} Honda Việt Nam",
            f"{base} giá lăn bánh 2024 2025",
        ])
    elif category_hint == "smartphone":
        queries.extend([
            f"{base} giá CellphoneS FPT Shop Thế Giới Di Động",
            f"{base} VN/A giá chính hãng",
        ])
    elif category_hint == "laptop":
        queries.extend([
            f"{base} giá laptop chính hãng Việt Nam",
        ])
    elif category_hint == "car":
        queries.extend([
            f"giá xe {base} lăn bánh 2025",
            f"{base} giá niêm yết đại lý chính hãng",
        ])
    elif category_hint == "air_conditioner":
        queries.extend([
            f"{base} giá điều hòa Điện Máy Xanh Nguyễn Kim",
        ])
    elif category_hint == "printer":
        queries.extend([
            f"{base} giá máy in chính hãng",
        ])

    return list(dict.fromkeys(queries))  # Deduplicate giữ thứ tự


# ---------------------------------------------------------------------------
# Hàm tổng hợp: search_and_price_product (cho định giá đơn lẻ)
# ---------------------------------------------------------------------------
def search_and_price_product(
    product_name: str,
    category_hint: str = "general",
) -> str:
    """
    Tìm kiếm Internet bằng Tavily và trả về text formatted cho LLM prompt.
    Tương thích output format với hàm search_on_internet() cũ.

    Ưu tiên whitelist domains, lọc bỏ bài báo/tin tức,
    giá phải đúng với giá trên link (giá sau giảm nếu có khuyến mãi).

    Returns:
        str: Kết quả dạng text đã format, sẵn sàng đưa vào prompt LLM.
    """
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    if not os.environ.get("TAVILY_API_KEY"):
        print("[SearchAndPrice] ERROR: TAVILY_API_KEY not found in .env")
        return "Không tìm thấy thông tin trên Internet do chưa cấu hình Tavily API key."

    print(f"[SearchAndPrice] Product: '{product_name}', Category: '{category_hint}'")

    try:
        # Tìm kiếm qua Tavily (đã lọc link)
        results = search_product_tavily(product_name, category_hint, max_queries=3)

        if not results:
            print("[SearchAndPrice] Không tìm được kết quả hợp lệ.")
            return "Không tìm thấy thông tin trên Internet."

        # Format kết quả cho LLM prompt
        formatted = []
        for idx, item in enumerate(results[:6], start=1):
            title = item.get("title") or "Nguồn tham khảo"
            content = item.get("content") or ""
            if len(content) > 300:
                content = content[:300] + "..."
            url = item.get("url") or ""

            formatted.append(
                f"[{idx}] {title}\nURL: {url}\n{content}"
            )

        if not formatted:
            print("[SearchAndPrice] Không có kết quả sau format.")
            return "Không tìm thấy thông tin trên Internet."

        print(f"[SearchAndPrice] SUCCESS: {len(formatted)} kết quả formatted")
        return "\n\n".join(formatted)

    except Exception as e:
        print(f"[SearchAndPrice] EXCEPTION: {type(e).__name__}: {str(e)}")
        return f"Lỗi khi tìm kiếm trên Internet: {str(e)}"


# ---------------------------------------------------------------------------
# Hàm tổng hợp: search_and_price_product_batch (cho định giá hàng loạt)
# ---------------------------------------------------------------------------
def search_and_price_product_batch(
    product_name: str,
) -> Dict[str, Any]:
    """
    Tìm kiếm Internet cho 1 sản phẩm trong batch.
    Sử dụng Tavily + LLM (Ollama) để trích xuất giá.

    Ưu tiên whitelist domains, lọc link bài báo, giá phải chính xác.

    Returns:
        {"price": str, "url": str, "description": str, "confidence": str}
    """
    from langchain_ollama import ChatOllama
    from routers.domain_registry import detect_category_from_keywords

    if not os.environ.get("TAVILY_API_KEY"):
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    # Detect category
    plain = product_name.lower().strip()
    normalized = unicodedata.normalize("NFD", plain)
    no_accent = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    no_accent = no_accent.replace("đ", "d").replace("Đ", "D")
    no_accent = re.sub(r"[^a-z0-9]+", " ", no_accent).strip()

    category_hint = detect_category_from_keywords(no_accent)

    # Tìm kiếm qua Tavily (đã lọc link)
    results = search_product_tavily(product_name, category_hint, max_queries=2)

    if not results:
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    # Format kết quả cho LLM
    formatted = []
    for idx, item in enumerate(results[:5], start=1):
        title = item.get("title") or ""
        content = item.get("content") or ""
        if len(content) > 300:
            content = content[:300] + "..."
        url = item.get("url") or ""
        source = item.get("source") or "tavily"
        formatted.append(
            f"[{idx}] (Nguồn: {source}) {title}\nURL: {url}\n{content}"
        )

    internet_data = "\n\n".join(formatted)

    # Dùng LLM để trích xuất giá
    llm = ChatOllama(
        model="qwen2.5:3b",
        temperature=0,
        format="json",
        num_predict=256,
    )

    prompt = f"""Bạn là một chuyên gia bóc tách thông tin giá cả. Hãy tìm giá bán thực tế của "{product_name}" từ dữ liệu sau.

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM:
1. NẾU CÓ NHIỀU MỨC GIÁ, BẠN BẮT BUỘC PHẢI LẤY MỨC GIÁ THẤP NHẤT (ĐÂY CHÍNH LÀ GIÁ ĐÃ GIẢM/GIÁ KHUYẾN MÃI).
2. TUYỆT ĐỐI KHÔNG lấy giá gốc (giá niêm yết cũ cao hơn).
3. URL phải dẫn thẳng đến trang chi tiết của đúng sản phẩm này. Không lấy trang danh mục hay trang tìm kiếm.
4. Chỉ lấy giá của sản phẩm chính, không lấy giá của phụ kiện hay bản dung lượng khác không liên quan.

Dữ liệu:
{internet_data}

Trả về kết quả ĐÚNG định dạng JSON sau:
{{
  "final_price": "số tiền (ví dụ: 12.990.000)",
  "url": "link sản phẩm (bắt đầu bằng https://)",
  "description": "tên sản phẩm thực tế"
}}"""

    try:
        response = llm.invoke(prompt)
        # Parse JSON
        clean_output = (response.content or "").strip()
        if clean_output.startswith("```json"):
            clean_output = clean_output[7:]
        if clean_output.startswith("```"):
            clean_output = clean_output[3:]
        if clean_output.endswith("```"):
            clean_output = clean_output[:-3]
        clean_output = clean_output.strip()

        match = re.search(r"\{[\s\S]*?\}", clean_output)
        if match:
            clean_output = match.group(0)

        result = json.loads(clean_output)

        price = str(result.get("final_price", "")).strip()
        url = str(result.get("url", "")).strip()
        desc = str(result.get("description", "")).strip()

        # Validate URL qua bộ lọc
        if url and not is_valid_shopping_link(url):
            print(f"[BatchSearch] LLM trả URL không hợp lệ, thử lấy từ kết quả Tavily: {url}")
            # Fallback: lấy URL đầu tiên từ kết quả Tavily đã lọc
            url = results[0].get("url", "") if results else ""

        if url and not url.startswith("http"):
            url = ""

        return {
            "price": price,
            "url": url,
            "description": desc,
            "confidence": "trung bình" if price else "thấp",
        }
    except Exception as e:
        print(f"[BatchSearch] LLM parse error: {str(e)}")
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}
