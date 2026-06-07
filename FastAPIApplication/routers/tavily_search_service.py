import os
import re
import json
import logging
import time
import unicodedata
from typing import List, Dict, Tuple, Any
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tavily import TavilyClient
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path

# ================= CẤU HÌNH =================
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "dummy")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Chặn domain tuyệt đối
BLOCKED_DOMAINS = {
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "reddit.com", "wikipedia.org", "vnexpress.net",
    "dantri.com.vn", "tuoitre.vn", "thanhnien.vn", "vietnamnet.vn",
    "kenh14.vn", "cafef.vn", "tinhte.vn", "genk.vn", "soha.vn",
    "cashify.vn"
}

SHOP_GROUPS = {
    "phone": ["thegioididong.com", "dienmayxanh.com", "cellphones.com.vn", "viettelstore.vn", "hoanghamobile.com", "fptshop.com.vn", "demobile.vn"],
    "laptop": ["gearvn.com", "hacom.vn", "anphatpc.com.vn", "phongvu.vn", "laptop88.vn", "nguyenkim.com"],
    "camera": ["zshop.vn", "binhminhdigital.com", "mayanh24h.com", "hoanghuycamera.com"],
    "audio": ["sudio.com.vn", "tai-nghe.com", "hangdinh.com"],
    "default": []
}

CATEGORY_KEYWORDS = {
    "phone": ["điện thoại", "smartphone", "iphone", "samsung", "oppo", "xiaomi", "realme"],
    "laptop": ["laptop", "notebook", "macbook", "gaming laptop", "ultrabook"],
    "camera": ["máy ảnh", "camera", "lens", "ống kính", "mirrorless", "dslr"],
    "audio": ["tai nghe", "loa", "headphone", "earphone", "airpods", "bluetooth"]
}

FORBIDDEN_URL_PATTERNS = [
    "/category/", "/categories/", "/danh-muc/", "/collection/", "/collections/",
    "/search", "?q=", "/tin-tuc/", "/news/", "/article/", "/blog/",
    "/tag/", "/author/", "/page/", "/pagination/"
]
PDP_URL_PATTERNS = [".html", ".htm", "/p/", "/product/", "/products/", "/san-pham/", "/item/", "/detail/"]
SPEC_KEYWORDS = ["thông số kỹ thuật", "cpu", "ram", "rom", "màn hình", "camera", "pin", "kích thước", "trọng lượng", "bảo hành"]
PRODUCT_META_KEYS = ["sku", "gtin", "mpn", "model", "barcode", "ean", "upc"]
MODEL_PATTERNS = [
    r'\b\d+\s*(?:gb|tb)\b', r'\ba\d{4}\b', r'[a-z]{2,}\d{2,}', r'\b\d+(?:\.\d+)?(?:-inch|")\b'
]

def detect_category(query: str) -> str:
    q = query.lower()
    for cat, kw_list in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in kw_list):
            return cat
    return "default"

def has_specific_model(query: str) -> bool:
    return any(re.search(p, query.lower()) for p in MODEL_PATTERNS)

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_ecommerce_page(html: str) -> int:
    signals = 0
    h = html.lower()
    if "add to cart" in h or "thêm vào giỏ" in h:
        signals += 1
    if "mua ngay" in h:
        signals += 1
    if "còn hàng" in h or "in stock" in h:
        signals += 1
    if "giỏ hàng" in h or "shopping cart" in h:
        signals += 1
    if signals >= 2:
        return 10
    elif signals == 1:
        return 5
    return 0

def fetch_links_from_shops(query: str, shops: List[str], max_per_shop: int = 3) -> List[Dict]:
    all_products = []
    try:
        # Gộp tất cả shop vào 1 request duy nhất bằng include_domains để tiết kiệm Quota
        response = tavily.search(
            query=f"{query} giá bán", 
            search_depth="advanced", 
            max_results=max_per_shop * len(shops), 
            include_domains=shops
        )
        for r in response.get("results", []):
            url = r.get("url")
            if not url:
                continue
            domain = urlparse(url).netloc.lower().replace("www.", "")
            all_products.append({"name": r.get("title", query), "shop": domain, "link": url, "content": r.get("content", "")})
    except Exception as e:
        logger.error(f"Tavily error (combined shops): {e}")
    return all_products

def fetch_links_from_tavily_general(query: str, max_results: int = 20) -> List[Dict]:
    try:
        resp = tavily.search(query=f"{query} mua tại Việt Nam", search_depth="advanced", max_results=max_results)
    except Exception as e:
        logger.error(f"Tavily error: {e}")
        return []
    products = []
    for r in resp.get("results", []):
        url = r.get("url")
        if not url:
            continue
        domain = urlparse(url).netloc.lower().replace("www.", "")
        if domain in BLOCKED_DOMAINS or any(domain.endswith(f".{bad}") for bad in BLOCKED_DOMAINS):
            continue
        if any(bad in domain for bad in ["shopee", "lazada", "tiki", "sendo"]):
            continue
        products.append({"name": r.get("title", query), "shop": domain, "link": url, "content": r.get("content", "")})
    return products

# ================= PDP SCORING =================
def url_pdp_score(url: str, normalized_query: str) -> int:
    url_lower = url.lower()
    for pat in FORBIDDEN_URL_PATTERNS:
        if pat in url_lower:
            return -1000
    score = 0
    for pat in PDP_URL_PATTERNS:
        if pat in url_lower:
            score += 20
            break
    path = urlparse(url).path
    slug = path.split("/")[-1].split(".")[0]
    slug_norm = normalize_text(slug)
    query_norm = normalized_query
    q_words = set(query_norm.split())
    s_words = set(slug_norm.split())
    if q_words:
        matched = len(s_words.intersection(q_words))
        ratio = matched / len(q_words)
        if ratio >= 0.7:
            score += 30
        elif ratio >= 0.5:
            score += 15
        elif ratio >= 0.3:
            score += 5
    if re.search(r'[a-z]{2,}\d{2,}', slug):
        score += 15
    return score

def structured_data_score(soup: BeautifulSoup, html: str) -> Tuple[int, int]:
    schema_count = 0
    score = 0
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            def count(obj):
                c = 0
                if isinstance(obj, dict):
                    if obj.get("@type") == "Product" or obj.get("type") == "Product":
                        c += 1
                    for v in obj.values():
                        c += count(v)
                elif isinstance(obj, list):
                    for item in obj:
                        c += count(item)
                return c
            cnt = count(data)
            schema_count += cnt
            if cnt > 0:
                score += 50
        except:
            pass
    if re.search(r'schema\.org/Product', html, re.IGNORECASE):
        score += 30
        schema_count += len(re.findall(r'itemscope.*?itemtype=".*?schema\.org/Product"', html, re.I))
    return score, schema_count

def product_metadata_score(html: str) -> int:
    score = 0
    h = html.lower()
    for key in PRODUCT_META_KEYS:
        if key in h:
            score += 10
    return min(score, 30)

def spec_sheet_score(html: str) -> int:
    h = html.lower()
    count = sum(1 for kw in SPEC_KEYWORDS if kw in h)
    return min(count * 2, 10)

def vietnamese_shop_boost(domain: str, html: str) -> int:
    domain_clean = domain.lower().replace("www.", "")
    trusted = [shop for group in SHOP_GROUPS.values() for shop in group]
    boost = 5 if any(shop in domain_clean for shop in trusted) else 0
    boost += 2 if domain_clean.endswith(".vn") else 0
    if re.search(r'\d{1,3}(?:[.,]\d{3})*(?:\.\d+)?\s?(?:vnđ|vnd|₫|đ)', html.lower()):
        boost += 3
    return boost

def extract_prices(html: str) -> List[str]:
    pat = r'\d{1,3}(?:[.,]\d{3})*(?:\.\d+)?\s?(?:đ|vnđ|vnd|₫|\$|usd|eur|€|£|¥)'
    matches = re.findall(pat, html.lower())
    unique = {re.sub(r'[^\d.,]', '', m) for m in matches}
    return list(unique)

def breadcrumb_quality(soup: BeautifulSoup) -> int:
    for selector in [".breadcrumb", ".breadcrumbs", "[class*='breadcrumb']", "nav.breadcrumb"]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(separator=" ", strip=True)
            parts = text.split()
            if parts and len(parts[-1].split()) <= 2:
                return -20
            return 0
    return 0

def title_match_score(title: str, normalized_query: str) -> float:
    q_words = set(normalized_query.split())
    if not q_words:
        return 1.0
    t_norm = normalize_text(title)
    t_words = set(t_norm.split())
    matched = len(q_words & t_words)
    return matched / len(q_words)

def count_product_items(html: str) -> int:
    patterns = [
        r'class=["\'][^"\']*product-item[^"\']*["\']',
        r'data-product-id=["\'][^"\']+["\']',
        r'itemtype=["\'][^"\']*schema\.org/Product["\']',
        r'<div[^>]*class="[^"]*product[^"]*"[^>]*>',
    ]
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, html, re.I))
    return total

def check_link_alive(url: str, product_name: str, content: str = "", timeout: int = 15) -> Dict:
    result = {"url": url, "shop": urlparse(url).netloc.lower().replace("www.", ""), "name": product_name, "score": -999, "content": content}
    try:
        domain_clean = result["shop"]
        if domain_clean in BLOCKED_DOMAINS or any(domain_clean.endswith(f".{bad}") for bad in BLOCKED_DOMAINS):
            result["score"] = -9999
            return result

        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, allow_redirects=True)
            html = r.text[:300000] if r.status_code == 200 else ""
        except Exception as e:
            logger.debug(f"Request failed for {url}: {e}")
            html = ""
        
        # Nếu không scrape được, vẫn cho điểm cơ bản để không bị loại, vì ta có raw_content từ Tavily
        base_fallback_score = 30 if not html else 0
        soup = BeautifulSoup(html, "html.parser")

        # TRÍCH XUẤT GIÁ TỪ SCHEMA.ORG NẾU CÓ
        schema_price = ""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and (item.get("@type") == "Product" or item.get("type") == "Product"):
                        offers = item.get("offers")
                        if isinstance(offers, dict) and offers.get("price"):
                            schema_price = str(offers.get("price"))
                        elif isinstance(offers, list) and len(offers) > 0 and isinstance(offers[0], dict):
                            schema_price = str(offers[0].get("price", ""))
            except:
                pass

        normalized_query = normalize_text(product_name)
        specific = has_specific_model(product_name)

        url_score = url_pdp_score(url, normalized_query)
        if url_score < -100:
            result["score"] = url_score
            return result

        schema_points, schema_count = structured_data_score(soup, html)
        meta_points = product_metadata_score(html)
        spec_points = spec_sheet_score(html)
        vn_boost = vietnamese_shop_boost(result["shop"], html)
        ecom_bonus = is_ecommerce_page(html)

        title = soup.title.string if soup.title else product_name
        title_ratio = title_match_score(title, normalized_query)

        bread_penalty = breadcrumb_quality(soup)

        product_count = count_product_items(html)
        price_count = len(extract_prices(html))

        confidence = 0
        confidence += url_score if url_score > 0 else 0
        confidence += schema_points
        confidence += meta_points
        confidence += spec_points
        confidence += vn_boost
        confidence += ecom_bonus
        confidence += bread_penalty
        confidence += base_fallback_score

        if title_ratio >= 0.7:
            confidence += 20
        elif title_ratio >= 0.5:
            confidence += 10
        elif title_ratio >= 0.3:
            confidence += 5
        else:
            confidence -= 10

        if product_count > 10:
            confidence -= 30
        elif product_count > 5:
            confidence -= 15
        elif product_count > 2:
            confidence -= 5

        if price_count > 20:
            confidence -= 30
        elif price_count > 10:
            confidence -= 15
        elif price_count > 6:
            confidence -= 5

        if schema_count >= 1 and price_count <= 10:
            confidence += 15

        if specific and title_ratio >= 0.5:
            confidence += 15

        result["score"] = confidence

        # CRAWL BẰNG REGEX (product_name, current_price, original_price)
        # 1. Product Name
        crawled_name = ""
        name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if name_match:
            crawled_name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()
        if not crawled_name:
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_match:
                crawled_name = title_match.group(1).strip()
        if not crawled_name:
            crawled_name = product_name
        
        crawled_name = " ".join(crawled_name.split())

        # KIỂM TRA CHẶT CHẼ DÒNG SẢN PHẨM BẰNG TỪ KHÓA
        variant_modifiers = ["pro max", "pro", "plus", "air", "mini", "ultra", "max"]
        query_lower = product_name.lower()
        crawled_lower = crawled_name.lower()
        
        for mod in variant_modifiers:
            has_in_query = bool(re.search(rf'\b{mod}\b', query_lower))
            has_in_crawled = bool(re.search(rf'\b{mod}\b', crawled_lower))
            
            if has_in_query and not has_in_crawled:
                result["score"] = -100
                return result
            if not has_in_query and has_in_crawled:
                result["score"] = -100
                return result

        # 2. Prices
        price_pattern = r'((?:\d{1,3}[.,])+\d{3})\s*(?:đ|vnđ|vnd|₫|đồng)'
        original_price = ""
        current_price = ""

        # Original price: <del> or <s>
        del_matches = re.findall(r'<(?:del|strike|s)[^>]*>(.*?)</(?:del|strike|s)>', html, re.IGNORECASE | re.DOTALL)
        for dm in del_matches:
            pm = re.search(price_pattern, dm, re.IGNORECASE)
            if pm:
                original_price = pm.group(1)
                break

        # Current price: special classes
        cur_matches = re.findall(r'<[^>]*class="[^"]*(?:special|current|new|giakm|price-main|price)[^"]*"[^>]*>(.*?)</[^>]+>', html, re.IGNORECASE | re.DOTALL)
        for cm in cur_matches:
            if '<del' in cm.lower() or '<s' in cm.lower():
                continue
            pm = re.search(price_pattern, cm, re.IGNORECASE)
            if pm:
                current_price = pm.group(1)
                break

        # Fallback if not found
        if not current_price or not original_price:
            all_prices = re.findall(price_pattern, html, re.IGNORECASE)
            seen = set()
            unique_prices = []
            for p in all_prices:
                if p not in seen:
                    unique_prices.append(p)
                    seen.add(p)
            
            if unique_prices:
                numeric_prices = [(int(re.sub(r'[^\d]', '', p)), p) for p in unique_prices]
                # Lọc bỏ các giá quá vô lý (như 350đ, hoặc 50.000đ phí ship)
                numeric_prices = [np for np in numeric_prices if np[0] >= 50000]
                numeric_prices.sort(key=lambda x: x[0], reverse=True) # Sort descending
                
                # Nguồn fallback thường chứa nhiều giá rác, ưu tiên lấy giá cao (vì giá thấp thường là rác/phụ kiện)
                if not current_price and numeric_prices:
                    current_price = numeric_prices[-1][1] if len(numeric_prices) == 1 else numeric_prices[len(numeric_prices)//2][1]
                if not original_price and len(numeric_prices) > 1:
                    original_price = numeric_prices[0][1]

        # ÉP GIÁ VÀO CONTENT CHO OLLAMA ĐỌC ĐƯỢC CHÍNH XÁC
        extra_info = []
        extra_info.append(f"Tên sản phẩm trên web: {crawled_name}")
        if current_price:
            extra_info.append(f"Giá hiện tại (current_price): {current_price} VNĐ")
        if original_price:
            extra_info.append(f"Giá gốc (original_price): {original_price} VNĐ")
            
        if raw_content:
            clean_raw = raw_content[:200].replace('\n', ' ')
            extra_info.append(f"Nội dung mô tả thêm: {clean_raw}")
        
        if extra_info:
            result["content"] = "\n".join(extra_info)

        return result
    except Exception as e:
        logger.debug(f"Error parsing {url}: {e}")
        # Dù lỗi parse, nếu có raw_content thì vẫn giữ lại link
        if result.get("content"):
            result["score"] = max(result.get("score", 0), 25)
        else:
            result["score"] = -50
        return result

def verify_links_parallel(products: List[Dict], query: str, target_count: int = 5) -> List[Dict]:
    scored = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        future_to_prod = {ex.submit(check_link_alive, p["link"], query, p.get("content", "")): p for p in products}
        for future in as_completed(future_to_prod):
            prod = future_to_prod[future]
            res = future.result()
            if res["score"] >= 20:
                scored.append({
                    "name": prod["name"],
                    "shop": prod["shop"],
                    "link": prod["link"],
                    "content": res.get("content", ""),
                    "score": res["score"]
                })
    scored.sort(key=lambda x: x["score"], reverse=True)
    seen = set()
    unique = []
    for item in scored:
        if item["shop"] not in seen and len(unique) < target_count:
            unique.append(item)
            seen.add(item["shop"])
    return unique

def search_product_no_ai(query: str, target_count: int = 5) -> List[Dict]:
    cat = detect_category(query)
    shops = SHOP_GROUPS.get(cat, [])
    products = []
    if shops:
        logger.info(f"Danh mục '{cat}', tìm trong {len(shops)} shop")
        products = fetch_links_from_shops(query, shops, max_per_shop=3)
    if len(products) < target_count:
        logger.info("Bổ sung tìm kiếm chung")
        products += fetch_links_from_tavily_general(query, max_results=25)
    if not products:
        return [{"error": "Không tìm thấy link nào"}]
    valid = verify_links_parallel(products, query, target_count)
    if not valid:
        return [{"error": "Không tìm thấy trang sản phẩm phù hợp"}]
    return valid

# ================= API VÀ CÁC HÀM CŨ =================

def search_and_price_product(
    product_name: str,
    category_hint: str = "general",
) -> str:
    """
    Tìm kiếm Internet bằng Tavily và trả về text formatted cho LLM prompt.
    Tương thích output format với hàm search_on_internet() cũ.
    """
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    if tavily.api_key == "dummy" and os.environ.get("TAVILY_API_KEY"):
        tavily.api_key = os.environ.get("TAVILY_API_KEY")

    if not tavily.api_key or tavily.api_key == "dummy":
        return "Không tìm thấy thông tin trên Internet do chưa cấu hình Tavily API key."

    try:
        # Dùng logic mới
        results = search_product_no_ai(product_name, target_count=6)

        if not results or "error" in results[0]:
            return "Không tìm thấy thông tin trên Internet."

        formatted = []
        for idx, item in enumerate(results[:6], start=1):
            content = item.get("content", "")
            
            # Content is already strictly from our regex crawler
            #content = item.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
                    
            url = item.get("link", "")

            formatted.append(
                f"[{idx}] Nguồn tham khảo\nURL: {url}\n{content}"
            )

        if not formatted:
            return "Không tìm thấy thông tin trên Internet."

        return "\n\n".join(formatted)
    except Exception as e:
        return f"Lỗi khi tìm kiếm trên Internet: {str(e)}"

def search_and_price_product_batch(
    product_name: str,
) -> Dict[str, Any]:
    """
    Tìm kiếm Internet cho 1 sản phẩm trong batch.
    Sử dụng Tavily + LLM (Ollama) để trích xuất giá.
    """
    from langchain_ollama import ChatOllama
    from routers.domain_registry import detect_category_from_keywords

    if tavily.api_key == "dummy" and os.environ.get("TAVILY_API_KEY"):
        tavily.api_key = os.environ.get("TAVILY_API_KEY")

    if not tavily.api_key or tavily.api_key == "dummy":
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    plain = product_name.lower().strip()
    normalized = unicodedata.normalize("NFD", plain)
    no_accent = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    no_accent = no_accent.replace("đ", "d").replace("Đ", "D")
    no_accent = re.sub(r"[^a-z0-9]+", " ", no_accent).strip()

    category_hint = detect_category_from_keywords(no_accent)

    results = search_product_no_ai(product_name, target_count=5)

    if not results or "error" in results[0]:
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}

    formatted = []
    for idx, item in enumerate(results[:5], start=1):
        content = item.get("content", "")
        if len(content) > 300:
            content = content[:300] + "..."
        url = item.get("link", "")
        source = item.get("shop", "tavily")
        formatted.append(
            f"[{idx}] (Nguồn: {source})\nURL: {url}\n{content}"
        )

    internet_data = "\n\n".join(formatted)

    llm = ChatOllama(
        model="llama3.2",
        temperature=0,
        format="json",
        num_predict=512,
    )

    prompt = f"""Bạn là một chuyên gia đánh giá và bóc tách dữ liệu.
Nhiệm vụ của bạn là lấy giá cho sản phẩm cần tìm: "{product_name}"

Dữ liệu crawl được bằng Regex từ các nguồn:
{internet_data}

QUY TẮC BẮT BUỘC KHÔNG ĐƯỢC VI PHẠM:
1. Bạn phải kiểm tra xem "Tên sản phẩm trên web" có đúng là sản phẩm cần tìm hay không.
2. Nếu ĐÚNG sản phẩm:
   - Ưu tiên lấy "Giá hiện tại (current_price)" hoặc "Giá khuyến mãi".
   - Nếu không có, hãy lấy "Giá gốc (original_price)".
   - Nếu không có cả hai, chỉ lấy giá từ "Nội dung mô tả thêm" NẾU nó là giá của chính sản phẩm đó.
3. TUYỆT ĐỐI KHÔNG LẤY các con số chỉ thông số kỹ thuật (như 250GB, 880g, 15.6 inch, v.v.) làm giá tiền!
4. CẨN THẬN VỚI PHỤ KIỆN / SẢN PHẨM MUA KÈM:
   - Trong dữ liệu thường có lẫn giá của phụ kiện (ví dụ: Chuột, Balo, Tai nghe, Bao da...). TUYỆT ĐỐI KHÔNG LẤY CÁC MỨC GIÁ NÀY!
   - (Mẹo: Một chiếc Laptop thường có giá từ 8 triệu đến 50 triệu. Nếu bạn thấy giá chỉ vài trăm nghìn như 250.000đ hoặc 578.000đ, đó CHẮC CHẮN là giá phụ kiện, phải BỎ QUA).
5. Nếu SAI sản phẩm hoặc không tìm thấy mức giá nào hợp lý:
   - Bỏ qua, KHÔNG lấy giá.
6. URL phải dẫn thẳng đến trang chi tiết của đúng sản phẩm này.

Trả về kết quả ĐÚNG định dạng JSON sau (nếu tìm thấy giá hợp lệ):
{{
  "final_price": "số tiền (ví dụ: 12.990.000)",
  "url": "link sản phẩm (bắt đầu bằng https://)",
  "description": "tên sản phẩm trên web"
}}
Nếu không có nguồn nào khớp sản phẩm, trả về các trường rỗng."""

    try:
        response = llm.invoke(prompt)
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

        # POST-PROCESSING: CHẶN ĐỨNG GIÁ PHỤ KIỆN BỊ NHẬN NHẦM
        if price:
            numeric_val = int(re.sub(r'[^\d]', '', price)) if re.sub(r'[^\d]', '', price) else 0
            cat_lower = product_name.lower()
            
            # Laptop, MacBook, Điện thoại thường không thể có giá dưới 1 triệu
            if any(k in cat_lower for k in ["laptop", "macbook", "điện thoại", "iphone", "samsung galaxy", "redmi note", "màn hình"]):
                if numeric_val < 1000000:
                    price = ""
            # Đồng hồ, Máy tính bảng, Tai nghe, Loa không thể có giá dưới 100k, chặn số lượng RAM/SSD ảo
            elif any(k in cat_lower for k in ["đồng hồ", "smartwatch", "máy tính bảng", "ipad", "tai nghe", "loa", "watch"]):
                if numeric_val < 100000:
                    price = ""
            # Loại bỏ hoàn toàn mọi con số ảo dưới 10.000 (Ví dụ 250, 880)
            if numeric_val < 10000:
                price = ""

        if url and not url.startswith("http"):
            url = ""

        return {
            "price": price,
            "url": url,
            "description": desc,
            "confidence": "trung bình" if price else "thấp",
        }
    except Exception as e:
        logger.debug(f"[BatchSearch] LLM parse error: {str(e)}")
        return {"price": "", "url": "", "description": "", "confidence": "thấp"}
