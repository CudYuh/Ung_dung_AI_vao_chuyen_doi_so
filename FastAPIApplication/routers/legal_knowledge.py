from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.llm_wiki.legal_rules import (
    ensure_legal_rules,
    load_legal_rules_for_ai,
)

try:
    from langchain_groq import ChatGroq
except Exception:
    ChatGroq = None

try:
    from langchain_tavily import TavilySearch
except Exception:
    TavilySearch = None


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
OBSIDIAN_LEGAL_DIR = PROJECT_ROOT / "Kho_Tri_Thuc_Phap_Ly"
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


router = APIRouter(
    prefix="/knowledge",
    tags=["Employee Knowledge Base"],
)


class LegalKnowledgeQuestion(BaseModel):
    question: str = Field(..., min_length=3)


class LegalKnowledgeResponse(BaseModel):
    status: str
    question: str
    answer: str
    verification: List[str]
    used_internal_knowledge: bool
    used_tavily: bool
    sources: List[Dict[str, str]]
    confidence: str
    note: str
    raw_answer: str | None = None


OFFICIAL_DOMAINS = {
    "vanban.chinhphu.vn",
    "chinhphu.vn",
    "congbao.chinhphu.vn",
    "mof.gov.vn",
}


LEGAL_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "luat-gia-16-2023",
        "title": "Luật Giá số 16/2023/QH15",
        "document_number": "16/2023/QH15",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "19/06/2023",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?docid=208367&pageid=27160",
        "summary": (
            "Luật Giá là văn bản nền tảng điều chỉnh hoạt động quản lý giá, "
            "thẩm định giá, cơ sở dữ liệu về giá, phân tích và dự báo giá thị trường."
        ),
        "scope": [
            "Quản lý nhà nước về giá.",
            "Hoạt động thẩm định giá.",
            "Cơ sở dữ liệu về giá.",
            "Quyền, nghĩa vụ của tổ chức, cá nhân trong lĩnh vực giá.",
        ],
        "key_points": [
            "Định giá và thẩm định giá phải dựa trên dữ liệu, căn cứ và phương pháp phù hợp.",
            "Thông tin giá cần được thu thập, cập nhật và quản lý để phục vụ phân tích, dự báo.",
            "Tổ chức, cá nhân tham gia hoạt động giá phải chịu trách nhiệm về tính chính xác, trung thực của thông tin.",
            "Kết quả sử dụng trong nghiệp vụ cần có căn cứ, hồ sơ và khả năng truy vết.",
        ],
        "employee_usage": [
            "Dùng để hiểu nền tảng pháp lý chung của hoạt động giá và thẩm định giá.",
            "Khi nhân viên không chắc một thao tác có phù hợp hay không, cần đối chiếu nguyên tắc chung của Luật Giá.",
            "Khi xây dựng kho dữ liệu giá nội bộ, cần lưu nguồn, ngày thu thập, căn cứ và người phê duyệt.",
        ],
        "caution": (
            "Không dùng Luật Giá để tự suy diễn mức giá cụ thể. Khi cần áp dụng vào hồ sơ thực tế, "
            "phải đối chiếu thêm nghị định, thông tư và chuẩn mực liên quan."
        ),
    },
    {
        "id": "nghi-dinh-78-2024",
        "title": "Nghị định 78/2024/NĐ-CP",
        "document_number": "78/2024/NĐ-CP",
        "type": "Nghị định",
        "issuer": "Chính phủ",
        "issued_date": "01/07/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?docid=210548&pageid=27160",
        "summary": (
            "Nghị định quy định chi tiết một số điều của Luật Giá về thẩm định giá, "
            "liên quan đến điều kiện, hồ sơ, trình tự và trách nhiệm trong hoạt động thẩm định giá."
        ),
        "scope": [
            "Hồ sơ, trình tự, thủ tục đăng ký hành nghề thẩm định giá.",
            "Điều kiện kinh doanh dịch vụ thẩm định giá.",
            "Đình chỉ, thu hồi giấy chứng nhận đủ điều kiện kinh doanh dịch vụ thẩm định giá.",
            "Trách nhiệm của các chủ thể liên quan trong hoạt động thẩm định giá.",
        ],
        "key_points": [
            "Người hành nghề và doanh nghiệp thẩm định giá phải đáp ứng điều kiện theo quy định.",
            "Thông tin trong hồ sơ phải đầy đủ, chính xác, hợp pháp.",
            "Tổ chức/cá nhân xác nhận thông tin phải chịu trách nhiệm trước pháp luật.",
            "Hoạt động thẩm định giá không chỉ là kỹ thuật tính toán mà còn liên quan đến điều kiện pháp lý và trách nhiệm nghề nghiệp.",
        ],
        "employee_usage": [
            "Dùng để hiểu vai trò, điều kiện và trách nhiệm của người tham gia hoạt động thẩm định giá.",
            "Khi nhân viên mới hỏi ai được quyền phê duyệt, ký xác nhận hoặc chịu trách nhiệm, cần tham chiếu nhóm quy định này.",
            "Khi kiểm tra hồ sơ nội bộ, cần đảm bảo thông tin được xác nhận đầy đủ và hợp pháp.",
        ],
        "caution": (
            "Không dùng kết quả AI hoặc kho tri thức để thay thế người có thẩm quyền. "
            "Những quyết định chính thức phải do cá nhân/tổ chức đủ thẩm quyền thực hiện."
        ),
    },
    {
        "id": "thong-tu-30-2024",
        "title": "Thông tư 30/2024/TT-BTC",
        "document_number": "30/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://chinhphu.vn/?classid=1&docid=210415&pageid=27160",
        "summary": (
            "Thông tư ban hành các chuẩn mực thẩm định giá Việt Nam về quy tắc đạo đức nghề nghiệp, "
            "phạm vi công việc, cơ sở giá trị thẩm định giá và hồ sơ thẩm định giá."
        ),
        "scope": [
            "Quy tắc đạo đức nghề nghiệp thẩm định giá.",
            "Phạm vi công việc thẩm định giá.",
            "Cơ sở giá trị thẩm định giá.",
            "Hồ sơ thẩm định giá.",
        ],
        "key_points": [
            "Nhân viên cần xác định rõ phạm vi công việc trước khi xử lý nghiệp vụ.",
            "Cần xác định cơ sở giá trị phù hợp với mục đích thẩm định.",
            "Hồ sơ phải đủ thông tin để kiểm tra, giải trình và truy vết.",
            "Không được xử lý nghiệp vụ theo cảm tính hoặc thiếu căn cứ.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi hồ sơ cần lưu gì, căn cứ cần thể hiện ra sao.",
            "Dùng khi cần giải thích vì sao kết quả AI chỉ là hỗ trợ, không thay thế hồ sơ nghiệp vụ.",
            "Dùng khi cần đào tạo nhân viên mới về đạo đức nghề nghiệp và phạm vi trách nhiệm.",
        ],
        "caution": (
            "Khi trả lời câu hỏi về hồ sơ, phạm vi công việc hoặc trách nhiệm nghề nghiệp, "
            "phải nhấn mạnh việc lưu căn cứ và kiểm tra bởi người có thẩm quyền."
        ),
    },
    {
        "id": "thong-tu-31-2024",
        "title": "Thông tư 31/2024/TT-BTC",
        "document_number": "31/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=210427&orggroupid=4&pageid=27160",
        "summary": (
            "Thông tư ban hành chuẩn mực thẩm định giá Việt Nam về thu thập và phân tích thông tin "
            "về tài sản thẩm định giá."
        ),
        "scope": [
            "Thu thập thông tin về tài sản thẩm định giá.",
            "Phân tích thông tin tài sản.",
            "Đánh giá mức độ phù hợp, tin cậy và đầy đủ của dữ liệu.",
            "Xử lý tình huống thiếu thông tin hoặc thông tin chưa rõ ràng.",
        ],
        "key_points": [
            "Không nên kết luận khi thông tin tài sản chưa đủ rõ.",
            "Cần kiểm tra model, cấu hình, tình trạng, đơn vị tính, thời điểm và điều kiện giao dịch.",
            "Dữ liệu thu thập phải được phân tích, không chỉ sao chép nguồn giá.",
            "Khi thiếu dữ liệu, cần ghi rõ giả định, giới hạn và yêu cầu bổ sung thông tin.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi thiếu model, thiếu cấu hình, thiếu dữ liệu thị trường thì xử lý thế nào.",
            "Dùng để hướng dẫn kiểm tra độ tin cậy của nguồn giá.",
            "Dùng để đào tạo cách phân tích thông tin trước khi đưa vào hồ sơ hoặc đề xuất.",
        ],
        "caution": (
            "Thông tin chưa đầy đủ thì không được coi là căn cứ chắc chắn. "
            "Nếu vẫn xử lý, phải ghi rõ giả định và giới hạn sử dụng."
        ),
    },
    {
        "id": "thong-tu-32-2024",
        "title": "Thông tư 32/2024/TT-BTC",
        "document_number": "32/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=210428&orggroupid=4&pageid=27160",
        "summary": (
            "Thông tư ban hành các chuẩn mực thẩm định giá Việt Nam về cách tiếp cận từ thị trường, "
            "cách tiếp cận từ chi phí và cách tiếp cận từ thu nhập."
        ),
        "scope": [
            "Cách tiếp cận từ thị trường.",
            "Cách tiếp cận từ chi phí.",
            "Cách tiếp cận từ thu nhập.",
            "Lựa chọn cách tiếp cận phù hợp với loại tài sản và dữ liệu sẵn có.",
        ],
        "key_points": [
            "Với hàng hóa phổ thông có dữ liệu giao dịch, cách tiếp cận thị trường thường là hướng ưu tiên.",
            "Khi thiếu dữ liệu thị trường, cần xem xét phương pháp khác nếu có đủ căn cứ phù hợp.",
            "Không được tự ước lượng giá nếu không có dữ liệu, phương pháp và căn cứ rõ ràng.",
            "Cần đánh giá sự khác biệt giữa các tài sản so sánh, điều kiện giao dịch và thời điểm thu thập dữ liệu.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi khi nào dùng phương pháp thị trường, chi phí hoặc thu nhập.",
            "Dùng để giải thích vì sao cần so sánh nhiều nguồn giá và điều chỉnh theo thông số.",
            "Dùng khi xử lý tình huống nhiều nguồn giá khác nhau hoặc dữ liệu thị trường không đầy đủ.",
        ],
        "caution": (
            "Không được hiểu cách tiếp cận thị trường là lấy trung bình cơ học mọi nguồn giá. "
            "Cần phân tích mức độ tương đồng, độ tin cậy và điều kiện của từng nguồn."
        ),
    },
]
RELATED_LEGAL_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "luat-dau-thau-22-2023",
        "title": "Luật Đấu thầu số 22/2023/QH15",
        "document_number": "22/2023/QH15",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "23/06/2023",
        "effective_date": "01/01/2024",
        "source_url": "https://vanban.chinhphu.vn/?docid=208419&pageid=27160",
        "summary": (
            "Luật Đấu thầu điều chỉnh hoạt động lựa chọn nhà thầu, lựa chọn nhà đầu tư "
            "và các nguyên tắc minh bạch, cạnh tranh, hiệu quả trong mua sắm, đầu tư."
        ),
        "scope": [
            "Lựa chọn nhà thầu.",
            "Lựa chọn nhà đầu tư.",
            "Mua sắm, đấu thầu trong các dự án và gói thầu.",
            "Nguyên tắc cạnh tranh, công bằng, minh bạch và hiệu quả kinh tế.",
        ],
        "key_points": [
            "Khi định giá phục vụ gói thầu, cần hiểu yêu cầu về tính minh bạch và căn cứ của dữ liệu giá.",
            "Nguồn giá sử dụng trong hồ sơ cần có khả năng giải trình, không chọn tùy tiện.",
            "Thông tin giá liên quan đến đấu thầu cần thận trọng vì có thể ảnh hưởng đến dự toán, giá gói thầu hoặc lựa chọn nhà thầu.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về định giá liên quan đến gói thầu, báo giá, dự toán hoặc mua sắm.",
            "Dùng để giải thích vì sao nguồn giá phải rõ ràng, khách quan và có khả năng kiểm tra.",
            "Dùng khi cần phân biệt dữ liệu tham khảo nội bộ với căn cứ chính thức trong hồ sơ đấu thầu.",
        ],
        "caution": (
            "Không tự suy diễn quy định đấu thầu nếu câu hỏi liên quan trực tiếp đến thủ tục pháp lý. "
            "Cần kiểm tra văn bản gốc hoặc người phụ trách pháp chế/đấu thầu."
        ),
    },
    {
        "id": "luat-doanh-nghiep-59-2020",
        "title": "Luật Doanh nghiệp số 59/2020/QH14",
        "document_number": "59/2020/QH14",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "17/06/2020",
        "effective_date": "01/01/2021",
        "source_url": "https://vanban.chinhphu.vn/default.aspx?docid=200447&pageid=27160",
        "summary": (
            "Luật Doanh nghiệp quy định về thành lập, tổ chức quản lý, hoạt động, tổ chức lại, "
            "giải thể và quyền, nghĩa vụ của doanh nghiệp."
        ),
        "scope": [
            "Tổ chức và hoạt động của doanh nghiệp.",
            "Quyền và nghĩa vụ của doanh nghiệp.",
            "Thông tin pháp lý của doanh nghiệp.",
            "Cơ cấu quản trị và trách nhiệm của người quản lý.",
        ],
        "key_points": [
            "Khi thẩm định hoặc đánh giá thông tin doanh nghiệp, cần kiểm tra tư cách pháp lý và thông tin doanh nghiệp.",
            "Thông tin doanh nghiệp có thể ảnh hưởng đến hồ sơ, hợp đồng, trách nhiệm và năng lực cung cấp dữ liệu.",
            "Nhân viên không nên chỉ dựa vào lời khai của khách hàng mà cần kiểm tra hồ sơ pháp lý phù hợp.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về hồ sơ doanh nghiệp, năng lực pháp lý hoặc thông tin đối tác.",
            "Dùng khi cần hướng dẫn nhân viên mới kiểm tra thông tin doanh nghiệp trước khi sử dụng dữ liệu.",
            "Dùng trong tình huống định giá tài sản thuộc sở hữu doanh nghiệp hoặc phục vụ giao dịch doanh nghiệp.",
        ],
        "caution": (
            "Kho tri thức chỉ hỗ trợ hiểu nguyên tắc. Các vấn đề như tư cách đại diện, quyền ký, "
            "tranh chấp doanh nghiệp cần kiểm tra hồ sơ pháp lý cụ thể."
        ),
    },
    {
        "id": "luat-ke-toan-88-2015",
        "title": "Luật Kế toán số 88/2015/QH13",
        "document_number": "88/2015/QH13",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "20/11/2015",
        "effective_date": "01/01/2017",
        "source_url": "https://vanban.chinhphu.vn/default.aspx?docid=183198&pageid=27160",
        "summary": (
            "Luật Kế toán quy định về công tác kế toán, chứng từ, sổ sách, báo cáo tài chính, "
            "tổ chức bộ máy kế toán và quản lý nhà nước về kế toán."
        ),
        "scope": [
            "Chứng từ kế toán.",
            "Sổ kế toán và báo cáo tài chính.",
            "Tổ chức công tác kế toán.",
            "Thông tin tài chính phục vụ quản lý và kiểm tra.",
        ],
        "key_points": [
            "Khi sử dụng số liệu tài chính trong định giá, cần quan tâm đến nguồn gốc, tính hợp lệ và khả năng kiểm tra của số liệu.",
            "Chứng từ, báo cáo tài chính và dữ liệu kế toán không nên sử dụng một cách máy móc nếu chưa kiểm tra tính phù hợp.",
            "Số liệu kế toán có thể hỗ trợ nhưng không thay thế phân tích thẩm định giá.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về báo cáo tài chính, chứng từ, số liệu kế toán liên quan đến định giá.",
            "Dùng để hướng dẫn kiểm tra nguồn số liệu doanh nghiệp cung cấp.",
            "Dùng khi cần giải thích vì sao dữ liệu tài chính phải có chứng từ hoặc hồ sơ đi kèm.",
        ],
        "caution": (
            "Thông tin kế toán cần được hiểu trong bối cảnh mục đích định giá. "
            "Không tự kết luận giá trị tài sản chỉ từ một số liệu kế toán đơn lẻ."
        ),
    },
    {
        "id": "bo-luat-dan-su-91-2015",
        "title": "Bộ luật Dân sự số 91/2015/QH13",
        "document_number": "91/2015/QH13",
        "type": "Bộ luật",
        "issuer": "Quốc hội",
        "issued_date": "24/11/2015",
        "effective_date": "01/01/2017",
        "source_url": "https://vanban.chinhphu.vn/?docid=183188&pageid=27160",
        "summary": (
            "Bộ luật Dân sự quy định về địa vị pháp lý, quyền sở hữu, nghĩa vụ, hợp đồng "
            "và các giao dịch dân sự."
        ),
        "scope": [
            "Quyền sở hữu và quyền khác đối với tài sản.",
            "Giao dịch dân sự.",
            "Hợp đồng và nghĩa vụ dân sự.",
            "Trách nhiệm dân sự.",
        ],
        "key_points": [
            "Định giá tài sản thường liên quan đến quyền sở hữu, quyền sử dụng, giao dịch và hợp đồng.",
            "Trước khi sử dụng thông tin tài sản, cần xem xét người cung cấp có quyền hợp pháp hay không.",
            "Vấn đề tranh chấp, hạn chế quyền hoặc quyền của bên thứ ba có thể ảnh hưởng đến việc sử dụng kết quả định giá.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về quyền sở hữu tài sản, hợp đồng, giao dịch hoặc trách nhiệm dân sự.",
            "Dùng để giải thích vì sao cần kiểm tra giấy tờ sở hữu, hợp đồng và tình trạng pháp lý của tài sản.",
            "Dùng trong các tình huống tài sản có tranh chấp, cầm cố, thế chấp hoặc chưa rõ quyền sở hữu.",
        ],
        "caution": (
            "Các vấn đề dân sự cụ thể thường cần xem hồ sơ gốc. Kho tri thức không thay thế tư vấn pháp lý."
        ),
    },
    {
        "id": "luat-tai-san-cong-15-2017",
        "title": "Luật Quản lý, sử dụng tài sản công số 15/2017/QH14",
        "document_number": "15/2017/QH14",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "21/06/2017",
        "effective_date": "01/01/2018",
        "source_url": "https://vanban.chinhphu.vn/default.aspx?docid=190302&pageid=27160",
        "summary": (
            "Luật quy định về quản lý, sử dụng tài sản công, bao gồm nguyên tắc quản lý, "
            "khai thác, xử lý và trách nhiệm đối với tài sản thuộc sở hữu toàn dân do Nhà nước đại diện chủ sở hữu."
        ),
        "scope": [
            "Tài sản công tại cơ quan, tổ chức, đơn vị.",
            "Quản lý, sử dụng, khai thác và xử lý tài sản công.",
            "Trách nhiệm của cơ quan, tổ chức, cá nhân trong quản lý tài sản công.",
            "Thông tin, hồ sơ và nguyên tắc minh bạch trong quản lý tài sản công.",
        ],
        "key_points": [
            "Định giá tài sản công cần thận trọng hơn vì liên quan đến quản lý tài sản nhà nước.",
            "Hồ sơ, căn cứ và thẩm quyền xử lý tài sản công phải rõ ràng.",
            "Không được dùng kết quả tham khảo không kiểm chứng để thay thế quy trình xử lý tài sản công.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về tài sản của cơ quan nhà nước, đơn vị sự nghiệp hoặc tài sản công.",
            "Dùng để nhắc nhân viên kiểm tra thẩm quyền, hồ sơ và mục đích sử dụng kết quả định giá.",
            "Dùng khi phân biệt tài sản doanh nghiệp thông thường với tài sản công.",
        ],
        "caution": (
            "Với tài sản công, cần kiểm tra quy định chuyên ngành và thẩm quyền cụ thể trước khi sử dụng kết quả."
        ),
    },
    {
        "id": "luat-quan-ly-thue-38-2019",
        "title": "Luật Quản lý thuế số 38/2019/QH14",
        "document_number": "38/2019/QH14",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "13/06/2019",
        "effective_date": "01/07/2020",
        "source_url": "https://vanban.chinhphu.vn/?docid=197312&pageid=27160",
        "summary": (
            "Luật Quản lý thuế quy định về quản lý các loại thuế, hồ sơ thuế, nghĩa vụ của người nộp thuế "
            "và trách nhiệm của cơ quan, tổ chức, cá nhân liên quan."
        ),
        "scope": [
            "Quản lý thuế.",
            "Hồ sơ, nghĩa vụ và trách nhiệm thuế.",
            "Thông tin phục vụ quản lý thuế.",
            "Trách nhiệm của tổ chức, cá nhân liên quan đến nghĩa vụ thuế.",
        ],
        "key_points": [
            "Một số nghiệp vụ định giá có thể liên quan đến hóa đơn, chứng từ, nghĩa vụ thuế hoặc dữ liệu tài chính.",
            "Khi sử dụng giá, doanh thu, chi phí hoặc chứng từ, cần quan tâm đến tính hợp lệ của nguồn thông tin.",
            "Không nên tư vấn thuế cụ thể nếu không có đủ căn cứ và chuyên môn phù hợp.",
        ],
        "employee_usage": [
            "Dùng khi nhân viên hỏi về hóa đơn, chứng từ, thuế, dữ liệu tài chính liên quan đến định giá.",
            "Dùng để nhắc nhân viên phân biệt giữa giá tham khảo, giá giao dịch và thông tin dùng cho nghĩa vụ thuế.",
            "Dùng khi cần hướng dẫn kiểm tra hồ sơ thuế ở mức tra cứu nội bộ.",
        ],
        "caution": (
            "Các câu hỏi về nghĩa vụ thuế cụ thể cần kiểm tra văn bản thuế hiện hành và người phụ trách chuyên môn."
        ),
    },
]
def get_all_legal_documents() -> List[Dict[str, Any]]:
    """
    Trả về toàn bộ văn bản trong Kho tri thức:
    - Nhóm lõi về giá/thẩm định giá
    - Nhóm mở rộng liên quan đến doanh nghiệp, kế toán, đấu thầu, tài sản công, thuế, dân sự
    """

    return LEGAL_DOCUMENTS + RELATED_LEGAL_DOCUMENTS
def select_relevant_legal_documents(question: str) -> List[Dict[str, Any]]:
    """
    Chọn nhóm văn bản liên quan nhất theo câu hỏi của nhân viên.
    Mục tiêu: tránh câu nào cũng mặc định nhắc Luật Giá + Thông tư 30/31/32.
    """

    q = question.lower()
    all_docs = get_all_legal_documents()

    selected_ids: set[str] = set()

    def add(doc_id: str):
        selected_ids.add(doc_id)

    # Nhóm định giá / thẩm định giá lõi
    valuation_keywords = [
        "định giá",
        "thẩm định giá",
        "giá trị",
        "giá thị trường",
        "phương pháp thị trường",
        "phương pháp chi phí",
        "phương pháp thu nhập",
        "hồ sơ thẩm định",
        "nguồn giá",
        "dữ liệu thị trường",
        "tài sản thiếu model",
        "thiếu dữ liệu",
        "ước lượng giá",
    ]

    if any(keyword in q for keyword in valuation_keywords):
        add("luat-gia-16-2023")
        add("nghi-dinh-78-2024")
        add("thong-tu-30-2024")
        add("thong-tu-31-2024")
        add("thong-tu-32-2024")

    # Đấu thầu
    if any(keyword in q for keyword in ["đấu thầu", "gói thầu", "nhà thầu", "dự toán", "mua sắm"]):
        add("luat-dau-thau-22-2023")
        add("luat-gia-16-2023")
        add("thong-tu-32-2024")

    # Kế toán / báo cáo tài chính
    if any(keyword in q for keyword in ["kế toán", "báo cáo tài chính", "chứng từ", "sổ sách", "doanh thu", "chi phí", "dòng tiền"]):
        add("luat-ke-toan-88-2015")
        add("thong-tu-30-2024")
        add("thong-tu-31-2024")

    # Doanh nghiệp / pháp nhân
    if any(keyword in q for keyword in ["doanh nghiệp", "pháp nhân", "đại diện pháp luật", "đăng ký kinh doanh", "công ty"]):
        add("luat-doanh-nghiep-59-2020")
        add("bo-luat-dan-su-91-2015")

    # Hợp đồng / giao dịch / quyền sở hữu
    if any(keyword in q for keyword in ["hợp đồng", "giao dịch", "quyền sở hữu", "tranh chấp", "thế chấp", "cầm cố"]):
        add("bo-luat-dan-su-91-2015")
        add("luat-gia-16-2023")

    # Tài sản công
    if any(keyword in q for keyword in ["tài sản công", "nhà nước", "đơn vị sự nghiệp", "cơ quan nhà nước"]):
        add("luat-tai-san-cong-15-2017")
        add("luat-gia-16-2023")
        add("nghi-dinh-78-2024")

    # Thuế / hóa đơn
    if any(keyword in q for keyword in ["thuế", "hóa đơn", "nghĩa vụ thuế", "quản lý thuế"]):
        add("luat-quan-ly-thue-38-2019")
        add("luat-ke-toan-88-2015")

    # Câu hỏi tổng quan cho nhân viên mới
    if any(keyword in q for keyword in ["mới vào", "nhân viên mới", "học luật nào", "bắt đầu", "cần học"]):
        add("luat-gia-16-2023")
        add("nghi-dinh-78-2024")
        add("thong-tu-30-2024")
        add("thong-tu-31-2024")
        add("thong-tu-32-2024")
        add("luat-doanh-nghiep-59-2020")
        add("luat-ke-toan-88-2015")
        add("bo-luat-dan-su-91-2015")

    selected_docs = [
        doc for doc in all_docs
        if doc.get("id") in selected_ids
    ]

    if selected_docs:
        return selected_docs

    # Nếu không đoán được chủ đề, dùng nhóm lõi nhưng không liệt kê quá nhiều.
    return [
        doc for doc in all_docs
        if doc.get("id") in {
            "luat-gia-16-2023",
            "nghi-dinh-78-2024",
            "thong-tu-30-2024",
            "thong-tu-31-2024",
            "thong-tu-32-2024",
        }
    ]


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question or "").strip()


def should_use_tavily(question: str) -> bool:
    q = (question or "").lower().strip()

    keywords = [
        "hôm nay",
        "hiện nay",
        "bây giờ",
        "mới nhất",
        "văn bản mới",
        "văn bản nào mới",
        "quy định mới",
        "luật mới",
        "nghị định mới",
        "thông tư mới",
        "vừa ban hành",
        "mới ban hành",
        "cập nhật",
        "sau năm 2024",
        "sau 2024",
        "năm 2025",
        "năm 2026",
        "còn hiệu lực",
        "hết hiệu lực",
        "thay thế",
        "sửa đổi",
        "bổ sung",
        "nguồn chính thức",
        "link chính thức",
        "tra cứu văn bản",
        "tra cứu internet",
        "tra cứu web",
        "tìm trên internet",
        "kiểm tra internet",
        "nguồn ngoài",
        "thuế",
        "đấu thầu",
        "hợp đồng",
        "kế toán",
        "bảo hiểm",
        "doanh nghiệp",
        "tài chính",
        "lao động",
        "xử phạt",
        "hành chính",
    ]

    return any(keyword in q for keyword in keywords)


def safe_json_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    cleaned = text.strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}

    return {}


def is_official_source(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return domain in OFFICIAL_DOMAINS
    except Exception:
        return False


def calculate_confidence(
    question: str,
    verification: List[str],
    sources: List[Dict[str, str]],
    answer: str,
) -> str:
    """
    Không để AI tự quyết định hoàn toàn độ tin cậy.
    Backend tự tính dựa trên căn cứ nội bộ, nguồn ngoài và mức độ xác minh.
    """

    q = question.lower()
    text = answer.lower()

    uncertainty_signals = [
        "không chắc",
        "chưa đủ dữ liệu",
        "cần kiểm tra",
        "cần đối chiếu",
        "chưa có nguồn",
        "không tìm được",
        "không đủ căn cứ",
    ]

    if any(signal in text for signal in uncertainty_signals):
        return "trung bình"

    official_source_count = sum(
        1 for source in sources if is_official_source(source.get("url", ""))
    )

    needs_external = should_use_tavily(q)

    if needs_external:
        if official_source_count >= 2:
            return "cao"

        if official_source_count == 1 or sources:
            return "trung bình"

        return "thấp"

    if len(verification) >= 2:
        return "cao"

    if verification:
        return "trung bình"

    return "thấp"


def format_sources_for_prompt(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return "Không sử dụng nguồn Internet ngoài."

    lines = []

    for index, source in enumerate(sources, start=1):
        lines.append(
            "\n".join(
                [
                    f"[Nguồn ngoài {index}]",
                    f"Tiêu đề: {source.get('title', 'Không rõ')}",
                    f"URL: {source.get('url', 'Không rõ')}",
                    f"Nội dung tóm tắt: {source.get('content', 'Không rõ')}",
                ]
            )
        )

    return "\n\n".join(lines)


def search_external_legal_sources(question: str) -> List[Dict[str, str]]:
    if TavilySearch is None:
        return []

    if not os.environ.get("TAVILY_API_KEY"):
        return []

    if "đấu thầu" in question.lower() or "gói thầu" in question.lower():
        search_query = (
            "Luật Đấu thầu số 22/2023/QH15 hiệu lực 01/01/2024 "
            "site:vanban.chinhphu.vn OR site:chinhphu.vn"
        )
    elif "kế toán" in question.lower() or "báo cáo tài chính" in question.lower():
        search_query = (
            "Luật Kế toán số 88/2015/QH13 hiệu lực 01/01/2017 "
            "site:vanban.chinhphu.vn OR site:chinhphu.vn"
        )
    else:
        search_query = (
            f"{question} luật định giá thẩm định giá văn bản pháp luật Việt Nam "
            f"site:vanban.chinhphu.vn OR site:mof.gov.vn OR site:chinhphu.vn"
        )

    try:
        tavily = TavilySearch(
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )

        result = tavily.invoke({"query": search_query})

        if isinstance(result, dict):
            raw_results = result.get("results") or []
        elif isinstance(result, list):
            raw_results = result
        else:
            raw_results = []

        sources: List[Dict[str, str]] = []

        for item in raw_results[:5]:
            if not isinstance(item, dict):
                continue

            url = str(item.get("url") or "")
            title = str(item.get("title") or "Nguồn tham khảo")
            content = str(
                item.get("content")
                or item.get("raw_content")
                or item.get("snippet")
                or ""
            )

            if not url and not content:
                continue
            
            # Chỉ nhận nguồn chính thống để tránh đưa bài blog/tạp chí không đáng tin vào Kho tri thức.
            if url and not is_official_source(url):
                continue
                        # Loại các kết quả quá cũ khi câu hỏi đang cần luật hiện hành.
            # Ví dụ: câu hỏi về đấu thầu hiện nay không nên ưu tiên Luật Đấu thầu 2005.
            combined_text = f"{title} {url} {content}".lower()

            outdated_signals = [
                "61/2005",
                "luật đấu thầu 2005",
                "2005/qh11",
            ]

            if any(signal in combined_text for signal in outdated_signals):
                continue
            sources.append(
                {
                    "title": title,
                    "url": url,
                    "content": content[:900],
                    "official": "true" if is_official_source(url) else "false",
                }
            )

        return sources

    except Exception:
        return []


def build_legal_documents() -> List[Dict[str, Any]]:
    ensure_legal_rules()
    return get_all_legal_documents()


def fallback_answer(question: str) -> LegalKnowledgeResponse:
    titles = [doc["title"] for doc in get_all_legal_documents()]

    answer = f"""
Backend chưa gọi được Groq nên hệ thống đang trả lời ở chế độ dự phòng.

Với câu hỏi: "{question}", nhân viên không nên tự kết luận nếu chưa có đủ căn cứ. Cách xử lý an toàn là kiểm tra lại thông tin tài sản, nguồn dữ liệu, thời điểm thu thập, điều kiện giao dịch, văn bản áp dụng và thẩm quyền phê duyệt. Nếu thông tin chưa đầy đủ hoặc có nhiều cách hiểu, cần ghi rõ giả định xử lý, giới hạn sử dụng và chuyển người có thẩm quyền kiểm tra.

Các văn bản đang có trong Kho tri thức gồm: {", ".join(titles)}.

Để hệ thống trả lời chi tiết theo từng câu hỏi, hãy kiểm tra file FastAPIApplication/.env và đảm bảo đã có GROQ_API_KEY.
""".strip()

    return LegalKnowledgeResponse(
        status="fallback",
        question=question,
        answer=answer,
        verification=titles,
        used_internal_knowledge=True,
        used_tavily=False,
        sources=[],
        confidence="thấp",
        note="Câu trả lời dự phòng vì Groq chưa hoạt động.",
        raw_answer=None,
    )

def slugify_note_name(name: str) -> str:
    text = name.strip().lower()

    vietnamese_map = {
        "à": "a", "á": "a", "ạ": "a", "ả": "a", "ã": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ậ": "a", "ẩ": "a", "ẫ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ặ": "a", "ẳ": "a", "ẵ": "a",
        "è": "e", "é": "e", "ẹ": "e", "ẻ": "e", "ẽ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ệ": "e", "ể": "e", "ễ": "e",
        "ì": "i", "í": "i", "ị": "i", "ỉ": "i", "ĩ": "i",
        "ò": "o", "ó": "o", "ọ": "o", "ỏ": "o", "õ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ộ": "o", "ổ": "o", "ỗ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ợ": "o", "ở": "o", "ỡ": "o",
        "ù": "u", "ú": "u", "ụ": "u", "ủ": "u", "ũ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ự": "u", "ử": "u", "ữ": "u",
        "ỳ": "y", "ý": "y", "ỵ": "y", "ỷ": "y", "ỹ": "y",
        "đ": "d",
    }

    for source, target in vietnamese_map.items():
        text = text.replace(source, target)

    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")

    return text or "note"


def infer_obsidian_node_type(note_name: str, content: str) -> str:
    name = note_name.lower()

    if note_name.startswith("00_"):
        return "root"

    if note_name.startswith(("01_", "02_", "03_", "04_")):
        return "group"

    if (
        "luật" in name
        or "nghị định" in name
        or "thông tư" in name
        or "bộ luật" in name
    ):
        return "document"

    situation_keywords = [
        "thiếu",
        "nhiều nguồn",
        "định giá liên quan",
        "dùng báo cáo",
        "kiểm tra",
        "hợp đồng",
        "tài sản công",
        "thuế",
    ]

    if any(keyword in name for keyword in situation_keywords):
        return "situation"

    return "topic"


def extract_note_title(note_name: str, content: str) -> str:
    for line in content.splitlines():
        line = line.strip()

        if line.startswith("# "):
            return line.replace("# ", "").strip()

    return note_name


def extract_note_summary(content: str, max_length: int = 420) -> str:
    lines = []

    for raw_line in content.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if line.startswith("- [["):
            continue

        if line.startswith("[["):
            continue

        lines.append(line)

        if len(" ".join(lines)) >= max_length:
            break

    summary = " ".join(lines).strip()

    if len(summary) > max_length:
        summary = summary[: max_length - 3] + "..."

    return summary or "Ghi chú tri thức pháp lý trong Obsidian."


def extract_obsidian_links(content: str) -> List[str]:
    links = re.findall(r"\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", content)

    cleaned_links = []

    for link in links:
        note_name = link.strip()

        if note_name and note_name not in cleaned_links:
            cleaned_links.append(note_name)

    return cleaned_links


def build_obsidian_legal_graph() -> Dict[str, Any]:
    """
    Đọc folder Kho_Tri_Thuc_Phap_Ly được tạo bằng Obsidian.
    Mỗi file .md là một node.
    Mỗi liên kết [[...]] là một edge.
    """

    if not OBSIDIAN_LEGAL_DIR.exists():
        return {
            "status": "error",
            "message": f"Không tìm thấy folder Obsidian: {OBSIDIAN_LEGAL_DIR}",
            "folder": str(OBSIDIAN_LEGAL_DIR),
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        }

    markdown_files = sorted(OBSIDIAN_LEGAL_DIR.rglob("*.md"))

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    note_name_to_id: Dict[str, str] = {}

    for file_path in markdown_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8-sig", errors="ignore")

        note_name = file_path.stem
        node_id = slugify_note_name(note_name)

        note_name_to_id[note_name] = node_id

        nodes_by_id[node_id] = {
            "id": node_id,
            "label": extract_note_title(note_name, content),
            "file_name": file_path.name,
            "relative_path": str(file_path.relative_to(OBSIDIAN_LEGAL_DIR)),
            "type": infer_obsidian_node_type(note_name, content),
            "summary": extract_note_summary(content),
            "content": content,
        }

    edges: List[Dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    for file_path in markdown_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8-sig", errors="ignore")

        source_name = file_path.stem
        source_id = note_name_to_id.get(source_name, slugify_note_name(source_name))

        for target_name in extract_obsidian_links(content):
            target_id = note_name_to_id.get(target_name, slugify_note_name(target_name))

            if target_id not in nodes_by_id:
                nodes_by_id[target_id] = {
                    "id": target_id,
                    "label": target_name,
                    "file_name": f"{target_name}.md",
                    "relative_path": f"{target_name}.md",
                    "type": "missing",
                    "summary": "Node này được liên kết trong Obsidian nhưng chưa có file nội dung.",
                    "content": "",
                }

            edge_key = (source_id, target_id)

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)

            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "label": "liên kết",
                }
            )

    nodes = list(nodes_by_id.values())

    root_node = next(
        (node for node in nodes if node["type"] == "root"),
        None,
    )

    return {
        "status": "success",
        "folder": str(OBSIDIAN_LEGAL_DIR),
        "root_id": root_node["id"] if root_node else None,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }

@router.get("/legal-documents")
async def legal_documents():
    return {
        "status": "success",
        "documents": build_legal_documents(),
    }
@router.get("/obsidian-legal-graph")
async def obsidian_legal_graph():
    return build_obsidian_legal_graph()

@router.post("/legal-qa", response_model=LegalKnowledgeResponse)
async def legal_qa(payload: LegalKnowledgeQuestion):
    question = normalize_question(payload.question)

    ensure_legal_rules()

    legal_context = load_legal_rules_for_ai()
    relevant_documents = select_relevant_legal_documents(question)
    need_tavily = should_use_tavily(question)
    external_sources = search_external_legal_sources(question) if need_tavily else []
    source_context = format_sources_for_prompt(external_sources)

    print(
        f"[LEGAL_QA] need_tavily={need_tavily}, "
        f"source_count={len(external_sources)}, "
        f"question={question}"
    )

    if ChatGroq is None or not os.environ.get("GROQ_API_KEY"):
        return fallback_answer(question)

    system_prompt = """
Bạn là trợ lý Kho tri thức pháp lý và nghiệp vụ nội bộ cho nhân viên công ty định giá/thẩm định giá.

Vai trò:
- Giúp nhân viên mới hiểu luật, chuẩn mực, quy trình và cách xử lý tình huống.
- Giúp nhân viên cũ tra cứu, đối chiếu và mở rộng hiểu biết về các văn bản liên quan.
- Có thể hỗ trợ các luật liên quan như thuế, đấu thầu, hợp đồng, kế toán, doanh nghiệp, tài chính nếu câu hỏi liên quan đến hoạt động định giá.
- Không thực hiện định giá sản phẩm cụ thể.
- Không đưa ra giá chốt.
- Không phê duyệt giá.
- Không thay thế người thẩm định, chuyên gia pháp lý hoặc người có thẩm quyền.

Nguyên tắc:
- Trả lời đầy đủ, có cấu trúc, đủ chi tiết để đào tạo nhân viên.
- Không trả lời chung chung.
- Không bịa số điều, số khoản nếu không có trong ngữ cảnh.
- Nếu chỉ có căn cứ ở mức văn bản, hãy nói "căn cứ theo nhóm quy định/chuẩn mực", không tự bịa điều khoản.
- Nếu thiếu dữ liệu xác minh, phải nói rõ cần kiểm tra văn bản gốc hoặc nguồn chính thức.
- Câu trả lời phải tự chứa phần căn cứ xác minh trong nội dung trả lời.
- Chỉ nhắc các văn bản thật sự liên quan đến câu hỏi.
- Nếu câu hỏi về báo cáo tài chính, chứng từ, số liệu kế toán thì phải xem xét Luật Kế toán.
- Nếu câu hỏi về đấu thầu, gói thầu, mua sắm thì phải xem xét Luật Đấu thầu.
- Nếu câu hỏi về doanh nghiệp, pháp nhân, đại diện pháp luật thì phải xem xét Luật Doanh nghiệp.
- Nếu câu hỏi về hợp đồng, giao dịch, quyền sở hữu thì phải xem xét Bộ luật Dân sự.
- Không mặc định liệt kê Luật Giá, Nghị định 78 và Thông tư 30/31/32 cho mọi câu hỏi.
- Nếu câu hỏi hỏi tổng quan cho nhân viên mới, hãy trả lời theo lộ trình học:
  1. Nhóm luật lõi về giá và thẩm định giá.
  2. Nhóm luật nền tảng liên quan đến doanh nghiệp, kế toán, hợp đồng, tài sản.
  3. Nhóm luật chuyên ngành chỉ học khi gặp tình huống như đấu thầu, tài sản công, thuế.
- Không mặc định liệt kê Luật Giá, Nghị định 78 và các Thông tư 30/31/32 nếu câu hỏi đang thuộc nhóm luật khác như đấu thầu, doanh nghiệp, kế toán, tài sản công, thuế hoặc dân sự.
- Trả lời bằng tiếng Việt.
- Trả JSON hợp lệ, không bọc markdown.

Schema JSON bắt buộc:
{
  "answer": "câu trả lời đầy đủ, chi tiết, có căn cứ xác minh, có hướng xử lý và cảnh báo rủi ro",
  "verification": ["các văn bản hoặc nguồn xác minh đã dùng"],
  "note": "lưu ý sử dụng hoặc giới hạn của câu trả lời"
}
"""

    human_prompt = f"""
[Câu hỏi của nhân viên]
{question}

[Kho luật và chuẩn mực nội bộ từ LLM Wiki]
{legal_context}

[Thông tin chi tiết các văn bản liên quan nhất với câu hỏi]
{json.dumps(relevant_documents, ensure_ascii=False)}

[Nguồn ngoài từ Tavily nếu hệ thống thấy cần]
{source_context}

Yêu cầu:
- Phần "answer" là nội dung chính để hiển thị cho nhân viên.
- Trả lời chi tiết, không quá ngắn.
- Trong answer phải có:
  1. Cách hiểu đúng của vấn đề.
  2. Căn cứ xác minh theo văn bản/chuẩn mực liên quan.
  3. Cách áp dụng trong công việc.
  4. Rủi ro nếu làm sai.
  5. Kết luận thực hành cho nhân viên.

- Nếu câu hỏi là câu tổng quan cho nhân viên mới, không chỉ liệt kê 5 văn bản lõi.
  Hãy chia thành các nhóm:
  + Nhóm bắt buộc học trước: Luật Giá, Nghị định 78/2024/NĐ-CP, Thông tư 30/2024/TT-BTC, Thông tư 31/2024/TT-BTC, Thông tư 32/2024/TT-BTC.
  + Nhóm nên học thêm: Luật Doanh nghiệp, Luật Kế toán, Bộ luật Dân sự.
  + Nhóm học theo tình huống: Luật Đấu thầu, Luật Quản lý sử dụng tài sản công, Luật Quản lý thuế.
- Không can thiệp vào module định giá sản phẩm.
- Không đưa ra kết quả giá sản phẩm.
"""

    try:
        llm = ChatGroq(
            model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0.15,
            max_retries=2,
        )

        response = llm.invoke(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )

        raw_text = getattr(response, "content", str(response))
        parsed = safe_json_from_text(raw_text)

        if not parsed:
            answer = raw_text
            verification: List[str] = []
            confidence = calculate_confidence(question, verification, external_sources, answer)

            return LegalKnowledgeResponse(
                status="success",
                question=question,
                answer=answer,
                verification=verification,
                used_internal_knowledge=True,
                used_tavily=need_tavily,
                sources=external_sources,
                confidence=confidence,
                note=(
                    "Câu trả lời được tạo bởi AI để hỗ trợ nội bộ. "
                    + (
                        "Câu hỏi đã kích hoạt tra cứu nguồn ngoài; cần kiểm tra danh sách nguồn trả về."
                        if need_tavily
                        else "Cần kiểm tra văn bản pháp luật gốc khi sử dụng chính thức."
                    )
                ),
                raw_answer=raw_text,
            )

        answer = str(parsed.get("answer") or "").strip()
        verification = [
            str(item)
            for item in parsed.get("verification", [])
            if str(item).strip()
        ]

        confidence = calculate_confidence(
            question=question,
            verification=verification,
            sources=external_sources,
            answer=answer,
        )

        return LegalKnowledgeResponse(
            status="success",
            question=question,
            answer=answer,
            verification=verification,
            used_internal_knowledge=True,
            used_tavily=need_tavily,
            sources=external_sources,
            confidence=confidence,
            note=str(
                parsed.get("note")
                or (
                    "Câu hỏi đã kích hoạt tra cứu nguồn ngoài. "
                    "Nếu danh sách nguồn trống, hệ thống chưa tìm được nguồn chính thống phù hợp."
                    if need_tavily
                    else "Kho tri thức chỉ hỗ trợ tra cứu nội bộ, không thay thế văn bản pháp luật gốc hoặc người có thẩm quyền."
                )
            ),
        )

    except Exception as exc:
        fallback = fallback_answer(question)
        fallback.raw_answer = f"Groq error: {str(exc)}"
        return fallback