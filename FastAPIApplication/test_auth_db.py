import sys
import os

# Thêm đường dẫn project vào sys.path để import đúng module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import session_local
from user_model import User
from utils.security import hash_password, verify_password

def run_test():
    print("--- BẮT ĐẦU CHẠY THỬ NGHIỆM ĐỒNG BỘ DB & AUTH ---")
    db = session_local()
    try:
        # 1. Tạo bảng tự động qua ORM
        from database import engine, base
        print("1. Đang khởi tạo/đồng bộ cấu trúc bảng (create_all)...")
        base.metadata.create_all(bind=engine)
        print("=> Đồng bộ bảng thành công!")

        # 2. Xóa user test cũ nếu có
        test_username = "test_user_ai"
        existing = db.query(User).filter(User.username == test_username).first()
        if existing:
            print(f"Dọn dẹp user test cũ: {test_username}")
            db.delete(existing)
            db.commit()

        # 3. Tạo user mới và băm mật khẩu
        raw_pass = "mypassword123"
        hashed = hash_password(raw_pass)
        print(f"2. Đang đăng ký user mới: '{test_username}'")
        print(f"   Password gốc: '{raw_pass}'")
        print(f"   Password hash: '{hashed}'")

        new_user = User(username=test_username, password_hash=hashed)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print("=> Lưu user vào database thành công!")

        # 4. Xác minh mật khẩu
        print("3. Đang kiểm tra mật khẩu đăng nhập...")
        # Lấy từ DB ra
        db_user = db.query(User).filter(User.username == test_username).first()
        is_valid = verify_password(raw_pass, db_user.password_hash)
        is_invalid = verify_password("sai_mat_khau", db_user.password_hash)

        print(f"   Nhập đúng mật khẩu '{raw_pass}': {is_valid} (Mong đợi: True)")
        print(f"   Nhập sai mật khẩu: {is_invalid} (Mong đợi: False)")

        if is_valid and not is_invalid:
            print("==> KẾT QUẢ: TẤT CẢ PHÉP THỬ THÀNH CÔNG VÀ CHÍNH XÁC!")
        else:
            print("==> KẾT QUẢ: THỬ THÀNH THẤT BẠI. CÓ LỖI XẢY RA!")

        # Dọn dẹp dữ liệu test
        db.delete(db_user)
        db.commit()
        print("Dọn dẹp hoàn tất cơ sở dữ liệu.")

    except Exception as e:
        print(f"Lỗi khi chạy thử nghiệm: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
