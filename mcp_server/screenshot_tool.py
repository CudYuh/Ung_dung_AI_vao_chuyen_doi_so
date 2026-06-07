import sys
import os
from pathlib import Path
import mcp.server.fastmcp as fastmcp

# Thêm thư mục FastAPIApplication vào sys.path để có thể import từ routers
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
fastapi_app_dir = project_root / "FastAPIApplication"
if str(fastapi_app_dir) not in sys.path:
    sys.path.insert(0, str(fastapi_app_dir))

# Khởi tạo MCP Server
mcp_server = fastmcp.FastMCP("Desktop Screenshot Tool")

@mcp_server.tool()
def take_screenshot(product_name: str, url: str = None) -> str:
    """
    Chụp toàn màn hình desktop hiện tại và lưu lại dưới tên sản phẩm.
    Nếu có url, tự động mở trang web đó trên trình duyệt rồi chụp màn hình.
    """
    try:
        from routers.valuation_api import take_desktop_screenshot_sync
        urls_list = [url] if url else None
        path = take_desktop_screenshot_sync(product_name, urls=urls_list)
        if path:
            return f"Đã chụp ảnh màn hình thành công và lưu tại: {path}"
        else:
            return "Lỗi khi chụp màn hình (không trả về đường dẫn)."
    except Exception as e:
        return f"Lỗi khi chụp màn hình: {str(e)}"

if __name__ == "__main__":
    mcp_server.run()
