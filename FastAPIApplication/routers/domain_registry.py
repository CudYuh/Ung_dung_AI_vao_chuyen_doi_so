"""
Domain Registry Service
=======================
Quản lý danh sách domain ưu tiên theo danh mục sản phẩm.
Tavily sẽ dùng include_domains để tập trung tìm giá trên các trang này.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "domain_registry.json"

_cache: Optional[Dict[str, Any]] = None
_cache_mtime: float = 0.0
_cache_lock = threading.Lock()


def _load_registry() -> Dict[str, Any]:
    """Đọc file JSON registry. Tự động reload nếu file thay đổi trên disk."""
    global _cache, _cache_mtime
    with _cache_lock:
        if not REGISTRY_PATH.exists():
            _cache = {"_meta": {}, "categories": {}}
            return _cache
        current_mtime = REGISTRY_PATH.stat().st_mtime
        if _cache is not None and current_mtime == _cache_mtime:
            return _cache
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        _cache_mtime = current_mtime
        return _cache


def _save_registry(data: Dict[str, Any]) -> None:
    """Ghi registry ra file và invalidate cache."""
    global _cache
    with _cache_lock:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _cache = data


def invalidate_cache() -> None:
    """Xóa cache để lần gọi tiếp theo sẽ đọc lại file."""
    global _cache
    with _cache_lock:
        _cache = None


def get_all_categories() -> Dict[str, Any]:
    """Trả về toàn bộ categories và domain list."""
    registry = _load_registry()
    return registry.get("categories", {})


def get_domains_for_category(category: str) -> List[str]:
    """
    Lấy danh sách domain ưu tiên cho 1 danh mục.
    Nếu category không tồn tại, fallback về 'general'.
    """
    categories = get_all_categories()
    cat_data = categories.get(category)
    if cat_data and cat_data.get("domains"):
        return cat_data["domains"]
    # Fallback sang general
    general = categories.get("general", {})
    return general.get("domains", [])


def detect_category_from_keywords(normalized_text: str) -> str:
    """
    Tự động nhận diện category dựa trên keywords trong registry.

    Dùng normalized_text (đã bỏ dấu, viết thường) để so khớp.
    Ưu tiên keyword dài nhất khớp trước (tránh 'honda' match trước 'honda civic').
    Trả về category key, hoặc 'general' nếu không khớp.
    """
    categories = get_all_categories()

    # Tạo danh sách (keyword, category_key) sắp xếp dài nhất trước
    keyword_map: List[tuple] = []
    for cat_key, cat_data in categories.items():
        if cat_key == "general":
            continue
        for kw in cat_data.get("keywords", []):
            keyword_map.append((kw.lower().strip(), cat_key))

    # Sắp xếp keyword dài nhất lên đầu để tránh match ngắn sai
    keyword_map.sort(key=lambda x: len(x[0]), reverse=True)

    for kw, cat_key in keyword_map:
        if kw and kw in normalized_text:
            return cat_key

    return "general"


def get_category_label(category: str) -> str:
    """Lấy label hiển thị của category."""
    categories = get_all_categories()
    cat_data = categories.get(category, {})
    return cat_data.get("label", category)


def add_domain(category: str, domain: str) -> bool:
    """Thêm 1 domain vào category. Trả False nếu đã tồn tại."""
    registry = _load_registry()
    categories = registry.setdefault("categories", {})
    cat_data = categories.setdefault(category, {"label": category, "domains": []})
    domains = cat_data.setdefault("domains", [])

    domain = domain.strip().lower()
    if domain in domains:
        return False
    domains.append(domain)
    _save_registry(registry)
    return True


def remove_domain(category: str, domain: str) -> bool:
    """Xóa 1 domain khỏi category. Trả False nếu không tìm thấy."""
    registry = _load_registry()
    categories = registry.get("categories", {})
    cat_data = categories.get(category)
    if not cat_data:
        return False
    domains = cat_data.get("domains", [])
    domain = domain.strip().lower()
    if domain not in domains:
        return False
    domains.remove(domain)
    _save_registry(registry)
    return True


def add_category(category_key: str, label: str, domains: List[str]) -> bool:
    """Thêm 1 category mới. Trả False nếu đã tồn tại."""
    registry = _load_registry()
    categories = registry.setdefault("categories", {})
    if category_key in categories:
        return False
    categories[category_key] = {
        "label": label,
        "domains": [d.strip().lower() for d in domains],
    }
    _save_registry(registry)
    return True


def update_category(category_key: str, label: Optional[str] = None, domains: Optional[List[str]] = None) -> bool:
    """Cập nhật category. Trả False nếu không tồn tại."""
    registry = _load_registry()
    categories = registry.get("categories", {})
    if category_key not in categories:
        return False
    if label is not None:
        categories[category_key]["label"] = label
    if domains is not None:
        categories[category_key]["domains"] = [d.strip().lower() for d in domains]
    _save_registry(registry)
    return True


def delete_category(category_key: str) -> bool:
    """Xóa 1 category. Trả False nếu không tồn tại."""
    registry = _load_registry()
    categories = registry.get("categories", {})
    if category_key not in categories:
        return False
    del categories[category_key]
    _save_registry(registry)
    return True
