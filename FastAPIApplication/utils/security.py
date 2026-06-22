import os
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext

# Khởi tạo context mã hóa mật khẩu sử dụng bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Lấy các cấu hình từ biến môi trường hoặc dùng mặc định
SECRET_KEY = os.getenv("SECRET_KEY", "dfc86c12d4d98c257321040375a004ef4c293776dbd8f9914713a21852c00c7e")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    """Băm mật khẩu sử dụng bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu nhập vào khớp với mật khẩu đã băm."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Tạo JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict | None:
    """Giải mã và kiểm tra tính hợp lệ của token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
