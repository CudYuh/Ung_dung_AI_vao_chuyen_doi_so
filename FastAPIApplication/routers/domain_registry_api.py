"""
Domain Registry API Router
===========================
API endpoints cho quản lý domain ưu tiên theo danh mục sản phẩm.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.domain_registry import (
    add_category,
    add_domain,
    delete_category,
    get_all_categories,
    get_domains_for_category,
    remove_domain,
    update_category,
)


router = APIRouter(
    prefix="/api/v1/domains",
    tags=["Domain Registry"],
)


# ---------- Pydantic Models ----------


class DomainAction(BaseModel):
    domain: str


class CategoryCreate(BaseModel):
    key: str
    label: str
    domains: List[str] = []


class CategoryUpdate(BaseModel):
    label: Optional[str] = None
    domains: Optional[List[str]] = None


# ---------- Endpoints ----------


@router.get("/")
async def list_categories():
    """Lấy toàn bộ danh sách category và domain."""
    categories = get_all_categories()
    result = []
    for key, data in categories.items():
        result.append({
            "key": key,
            "label": data.get("label", key),
            "domains": data.get("domains", []),
            "domain_count": len(data.get("domains", [])),
        })
    return {"status": "success", "categories": result}


@router.get("/{category}")
async def get_category_domains(category: str):
    """Lấy danh sách domain cho 1 category."""
    domains = get_domains_for_category(category)
    categories = get_all_categories()
    cat_data = categories.get(category, {})
    return {
        "status": "success",
        "category": category,
        "label": cat_data.get("label", category),
        "domains": domains,
    }


@router.post("/")
async def create_category(body: CategoryCreate):
    """Tạo category mới."""
    success = add_category(body.key, body.label, body.domains)
    if not success:
        raise HTTPException(
            status_code=409,
            detail=f"Category '{body.key}' đã tồn tại.",
        )
    return {
        "status": "success",
        "message": f"Đã tạo category '{body.key}' với {len(body.domains)} domain.",
    }


@router.put("/{category}")
async def modify_category(category: str, body: CategoryUpdate):
    """Cập nhật label hoặc danh sách domain của category."""
    success = update_category(category, label=body.label, domains=body.domains)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category}' không tồn tại.",
        )
    return {
        "status": "success",
        "message": f"Đã cập nhật category '{category}'.",
    }


@router.delete("/{category}")
async def remove_category(category: str):
    """Xóa 1 category."""
    success = delete_category(category)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category}' không tồn tại.",
        )
    return {
        "status": "success",
        "message": f"Đã xóa category '{category}'.",
    }


@router.post("/{category}/domains")
async def add_domain_to_category(category: str, body: DomainAction):
    """Thêm domain vào category."""
    success = add_domain(category, body.domain)
    if not success:
        raise HTTPException(
            status_code=409,
            detail=f"Domain '{body.domain}' đã tồn tại trong category '{category}'.",
        )
    return {
        "status": "success",
        "message": f"Đã thêm '{body.domain}' vào category '{category}'.",
    }


@router.delete("/{category}/domains")
async def remove_domain_from_category(category: str, body: DomainAction):
    """Xóa domain khỏi category."""
    success = remove_domain(category, body.domain)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Domain '{body.domain}' không tồn tại trong category '{category}'.",
        )
    return {
        "status": "success",
        "message": f"Đã xóa '{body.domain}' khỏi category '{category}'.",
    }
