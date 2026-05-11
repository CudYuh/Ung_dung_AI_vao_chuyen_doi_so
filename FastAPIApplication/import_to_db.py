
import pandas as pd
from sqlalchemy import create_engine

# 1. Thông tin cấu hình (Sửa lại cho đúng với máy của bạn)
FILE_PATH = 'data.csv'
DB_URL = "postgresql://postgres:123456@localhost:5432/vattu_db" # Thay 123456 bằng mật khẩu thật

def import_data():
    try:
        print(f"1. Đang đọc file: {FILE_PATH}...")
        # Đọc file CSV, bỏ qua các dòng trống
        df = pd.read_csv(FILE_PATH, skip_blank_lines=True)
        
        # Xóa các dòng mà toàn bộ các cột đều rỗng (nếu có do lỗi xuất file từ Google Sheets)
        df = df.dropna(how='all')

        print(f"2. Đã tải {len(df)} dòng dữ liệu.")
        print(f"   Các cột tìm thấy: {list(df.columns)}")

        print("3. Đang kết nối đến PostgreSQL...")
        engine = create_engine(DB_URL)

        # 4. Lưu vào Database
        # Tên bảng sẽ là: danh_muc_vat_tu
        table_name = "danh_muc_vat_tu"
        
        print(f"4. Đang đẩy dữ liệu vào bảng '{table_name}'...")
        # if_exists='replace': Xóa bảng cũ (nếu có) và tạo bảng mới hoàn toàn
        # index=False: Không đẩy cái cột số thứ tự (0, 1, 2...) của Pandas vào DB
        df.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

        print("✅ HOÀN TẤT! Dữ liệu đã nằm an toàn trong Database.")
        
    except Exception as e:
        print("❌ CÓ LỖI XẢY RA:")
        print(e)

if __name__ == "__main__":
    import_data()
