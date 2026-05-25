from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import session_local
from models import Product
from services.llm_wiki.framework import (
    build_visual_graph,
    find_record_by_id,
    get_concepts,
    load_graph_edges,
    rebuild_wiki_from_db,
    search_wiki,
    sync_product_to_wiki,
    wiki_status,
)
from services.llm_wiki.legal_rules import (
    ensure_legal_rules,
    get_legal_rules,
    legal_rules_status,
    load_legal_rules_for_ai,
)


router = APIRouter(prefix="/wiki", tags=["LLM Wiki Framework"])


def get_db():
    db = session_local()

    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


@router.get("/status")
async def get_wiki_status():
    return wiki_status()


@router.post("/rebuild")
async def rebuild_wiki(db: db_dependency):
    wiki_result = rebuild_wiki_from_db(db)
    legal_result = ensure_legal_rules()

    return {
        **wiki_result,
        "legal_rules": legal_result,
    }


@router.post("/sync-product/{product_id}")
async def sync_one_product(product_id: int, db: db_dependency):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy sản phẩm trong database",
        )

    return sync_product_to_wiki(product)


@router.get("/product/{product_id}")
async def get_product_knowledge_profile(product_id: int):
    item = find_record_by_id(product_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Chưa tìm thấy hồ sơ tri thức của sản phẩm này. Hãy rebuild hoặc sync LLM Wiki.",
        )

    return {
        "status": "success",
        "message": "Đã tìm thấy hồ sơ tri thức của sản phẩm",
        "item": item,
        "concepts": get_concepts(),
        "explanation": (
            "Hồ sơ này được sinh tự động từ database và được LLM Wiki Framework "
            "chuẩn hóa thành tri thức gồm entity, concept, nguồn dữ liệu, chứng thư "
            "và căn cứ định giá."
        ),
    }


@router.get("/search")
async def search_llm_wiki(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    return {
        "query": q,
        "results": search_wiki(q, limit=limit),
    }


@router.get("/concepts")
async def list_concepts():
    return get_concepts()


@router.get("/legal-rules/status")
async def get_legal_rules_status():
    return legal_rules_status()


@router.post("/legal-rules/rebuild")
async def rebuild_legal_rules():
    return ensure_legal_rules()


@router.get("/legal-rules")
async def list_legal_rules():
    return get_legal_rules()


@router.get("/legal-rules/summary")
async def legal_rules_summary_for_ai():
    return {
        "summary": load_legal_rules_for_ai(),
    }


# API graph giữ lại cho nội bộ nhóm/debug, không đưa ra Swagger và không hiển thị trên UI khách hàng.
@router.get("/graph", include_in_schema=False)
async def graph_edges(limit: int = Query(200, ge=1, le=5000)):
    edges = load_graph_edges()

    return {
        "total": len(edges),
        "edges": edges[:limit],
    }


# API graph visual giữ lại cho bản demo nội bộ, không đưa ra Swagger và không hiển thị trên UI khách hàng.
@router.get("/graph/visual", include_in_schema=False)
async def visual_graph(
    product_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
):
    return build_visual_graph(query=q, product_id=product_id)