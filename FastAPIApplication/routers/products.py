from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from pydantic import BaseModel
from datetime import datetime

from database import session_local
from models import Product
from services.llm_wiki.framework import sync_product_to_wiki


router = APIRouter(prefix="/products", tags=["products"])


class ProductApproveRequest(BaseModel):
    name: str
    price: str
    source: str
    specifications: str = ""
    category: str = "Tài sản định giá"
    unit: str = "Cái"


def get_db():
    db = session_local()

    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


@router.get("/search")
async def search_products(
    db: db_dependency,
    q: str = Query(None, min_length=1),
):
    if not q:
        return []

    search_query = f"%{q}%"

    products = db.query(Product).filter(
        or_(
            Product.name.ilike(search_query),
            Product.specifications.ilike(search_query),
            cast(Product.category, String).ilike(search_query),
            cast(Product.certificate_number, String).ilike(search_query),
        )
    ).all()

    return products


@router.get("/")
async def get_all_products(db: db_dependency):
    return db.query(Product).all()


@router.post("/approve")
async def approve_product(
    req: ProductApproveRequest,
    db: db_dependency,
):
    from sqlalchemy import func

    max_id = db.query(func.max(Product.id)).scalar() or 0
    new_id = int(max_id) + 1

    new_product = Product(
        id=new_id,
        name=req.name,
        price=req.price,
        source=req.source,
        specifications=req.specifications,
        category=None,
        unit=req.unit,
        appraisal_date=datetime.now().strftime("%d/%m/%Y"),
        appraiser="AI System",
        certificate_number="AI-" + datetime.now().strftime("%Y%m%d%H%M"),
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    wiki_sync_result = None

    try:
        wiki_sync_result = sync_product_to_wiki(new_product)
    except Exception as e:
        wiki_sync_result = {
            "status": "error",
            "message": f"Sản phẩm đã lưu database nhưng chưa sync được sang LLM Wiki: {str(e)}",
        }

    return {
        "status": "success",
        "message": "Đã phê duyệt giá",
        "data": {
            "id": new_product.id,
            "name": new_product.name,
            "price": new_product.price,
            "source": new_product.source,
            "specifications": new_product.specifications,
            "category": new_product.category,
            "unit": new_product.unit,
            "appraisal_date": new_product.appraisal_date,
            "appraiser": new_product.appraiser,
            "certificate_number": new_product.certificate_number,
        },
        "wiki_sync": wiki_sync_result,
    }