from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from database import session_local
from models import Product

router = APIRouter(prefix='/products', tags=['products'])

def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/search")
async def search_products(db: db_dependency, q: str = Query(None, min_length=1)):
    if not q:
        return []
    
    # Tìm kiếm theo tên hoặc thông số kỹ thuật (case-insensitive)
    search_query = f"%{q}%"
    products = db.query(Product).filter(
        or_(
            Product.name.ilike(search_query),
            Product.specifications.ilike(search_query),
            cast(Product.category, String).ilike(search_query),
            cast(Product.certificate_number, String).ilike(search_query)
        )
    ).all()
    
    return products

@router.get("/")
async def get_all_products(db: db_dependency):
    return db.query(Product).all()
