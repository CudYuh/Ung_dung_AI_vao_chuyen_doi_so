from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Annotated
from database import session_local
from user_model import User
from utils.security import verify_password, hash_password, create_access_token

router = APIRouter(prefix="/auth", tags=["authentication"])

# Dependency để lấy database session
def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# Schema đầu vào cho đăng nhập và đăng ký
class UserAuth(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(req: UserAuth, db: db_dependency):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng"
        )
    
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng"
        )
    
    # Tạo JWT access token
    access_token = create_access_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/register")
async def register(req: UserAuth, db: db_dependency):
    # Kiểm tra xem user đã tồn tại chưa
    existing_user = db.query(User).filter(User.username == req.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đã tồn tại"
        )
    
    new_user = User(
        username=req.username,
        password_hash=hash_password(req.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "status": "success",
        "message": "Đã tạo tài khoản thành công",
        "username": new_user.username
    }
