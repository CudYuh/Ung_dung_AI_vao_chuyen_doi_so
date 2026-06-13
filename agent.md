# Tài liệu mô tả dự án: Hệ thống AI Định giá & Hỏi đáp

Dự án này là một hệ thống web hiện đại, kết hợp sức mạnh của AI trong việc đánh giá/định giá sản phẩm (Valuation), quản lý hỏi đáp (Q&A), và xây dựng một hệ thống tri thức (Wiki/Second Brain). Dự án bao gồm hai phần chính: Backend (FastAPI) và Frontend (React).

---

## 1. Cấu trúc Code

Dự án được tổ chức thành các thư mục chính:

- **`FastAPIApplication/` (Backend)**: Thư mục chứa toàn bộ logic xử lý của hệ thống backend.
  - **`main.py`**: Điểm khởi chạy của ứng dụng (entry point), cấu hình các API Router và middleware.
  - **`database.py`**: Cấu hình kết nối tới cơ sở dữ liệu PostgreSQL bằng SQLAlchemy.
  - **`models.py`**: Định nghĩa cấu trúc các bảng (Schema) trong cơ sở dữ liệu.
  - **`routers/`**: Chứa các file định nghĩa API theo từng chức năng riêng biệt:
    - `valuation_api.py`: Các API định giá sản phẩm qua AI.
    - `tavily_search_service.py`: Tích hợp tìm kiếm thông qua Tavily.
    - `questions_and_answers.py`: API CRUD quản lý hỏi đáp.
    - `wiki.py`, `legal_knowledge.py`: API liên quan đến hệ thống tri thức (Wiki) và pháp lý.
    - `domain_registry_api.py`: API quản lý whitelist danh sách các domain uy tín.
    - `products.py`: API quản lý và tìm kiếm sản phẩm cơ bản.
  - **`services/`**: Chứa logic xử lý nghiệp vụ sâu hơn như `llm_wiki` (trích xuất và kết nối kiến thức).

- **`frontend/` (Frontend)**: Giao diện người dùng.
  - **`src/`**: Mã nguồn React.
  - **`package.json`, `vite.config.js`**: Cấu hình dependencies và quá trình build.

- **Các thư mục khác**:
  - `Kho_Tri_Thuc_Phap_Ly/`: Nơi lưu trữ văn bản, dữ liệu liên quan tới kiến thức pháp lý.
  - `mcp_server/`: Cấu hình/Thư mục chạy hệ thống Model Context Protocol (MCP).

---

## 2. Công nghệ sử dụng

**Backend:**
- **Framework Web**: `FastAPI` (nhanh, hỗ trợ async và auto-generate tài liệu API).
- **Cơ sở dữ liệu**: `PostgreSQL` kết hợp với `SQLAlchemy` (ORM) để tương tác CSDL.
- **Trí tuệ nhân tạo (AI / LLM)**: 
  - `LangChain`: Framework hỗ trợ làm việc với LLMs.
  - Tích hợp các LLMs như `OpenAI` (GPT), `Gemini` và hỗ trợ mô hình cục bộ (`Ollama`, `Qwen`).
  - Tìm kiếm thời gian thực với `Tavily Search API`.
- **Package Management**: Sử dụng `uv` để quản lý môi trường và thư viện (`pyproject.toml`, `uv.lock`).

**Frontend:**
- **Framework/Thư viện**: `React 19` xây dựng dựa trên `Vite`.
- **Styling**: `Tailwind CSS v4` (tiện dụng, dễ dàng tạo giao diện responsive).
- **Trực quan hoá dữ liệu**: Sử dụng `d3` và `react-force-graph-2d` để vẽ đồ thị mạng lưới kiến thức (Knowledge Graph).
- **Giao tiếp API**: `axios`.

---

## 3. Tính năng hiện có

1. **Hệ thống AI Định giá hàng hoá (AI Valuation System):**
   - Tự động tìm kiếm giá của một sản phẩm bất kỳ thông qua Tavily Search.
   - Sử dụng AI để đọc hiểu, trích xuất chính xác giá từ các trang web (bỏ qua giá phụ kiện, cấu hình không khớp).
   - Có thể chỉ định/ưu tiên tìm kiếm trên các tên miền (domain registry) uy tín để tăng độ chuẩn xác.
   - Hỗ trợ xử lý hàng loạt (batch) cho nhiều sản phẩm.

2. **Hệ thống Hỏi đáp (Q&A Manager):**
   - Hỗ trợ đầy đủ các thao tác CRUD (Tạo, Đọc, Cập nhật, Xóa) cho các câu hỏi và câu trả lời.
   - Khả năng tạo câu trả lời tự động và gợi ý thông qua AI.

3. **Hệ thống Tri thức (LLM Wiki / Second Brain):**
   - Tổ chức dữ liệu dưới dạng mạng lưới kiến thức.
   - Cho phép người dùng duyệt, tìm kiếm nội dung các thực thể (entities), xây dựng đồ thị quan hệ để thấy được kết nối giữa các mảng thông tin.

4. **Kiến thức pháp lý & Quản lý Sản phẩm:**
   - Cung cấp luồng tra cứu văn bản/kiến thức pháp lý.
   - Thêm mới, xét duyệt và tìm kiếm sản phẩm trong kho CSDL.

---

## 4. Cách chạy dự án

### Yêu cầu tiên quyết
- Đã cài đặt **Python 3.10+** và **uv**.
- Đã cài đặt **Node.js** và **npm**.
- Cài đặt và đang chạy **PostgreSQL** (có cấu hình CSDL `vattu_db`, tài khoản postgres/123456 ở port 5432 hoặc thay đổi theo `FastAPIApplication/database.py`).
- (Tuỳ chọn nhưng cần thiết cho AI): Các API Key (OpenAI, Gemini, Tavily) đặt trong code hoặc file `.env`.

### Khởi chạy Backend (FastAPI)

Mở Terminal và thực thi:

```bash
# 1. Cài đặt các thư viện Python (từ uv.lock / pyproject.toml)
uv sync

# 2. Kích hoạt môi trường ảo
venv\Scripts\activate

# 3. Di chuyển vào thư mục backend
cd FastAPIApplication

# 4. Chạy server ở chế độ reload (tự động cập nhật khi có thay đổi code)
uv run uvicorn main:app --reload
```
> Sau khi chạy, API Documentation (Swagger UI) sẽ có tại: `http://127.0.0.1:8000/docs`

### Khởi chạy Frontend (React / Vite)

Mở một cửa sổ Terminal mới:

```bash
# 1. Di chuyển vào thư mục frontend
cd frontend

# 2. Cài đặt các package (Lần đầu tiên chạy)
npm install

# 3. Chạy môi trường phát triển (Development server)
npm run dev
```
> Terminal sẽ hiển thị đường link local (thường là `http://localhost:5173/`), bạn hãy truy cập vào để sử dụng giao diện web.
