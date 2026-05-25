from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


APP_DIR = Path(__file__).resolve().parents[2]

RUNTIME_DIR = APP_DIR / "llm_wiki_runtime"
WIKI_DIR = RUNTIME_DIR / "wiki"
LEGAL_DIR = WIKI_DIR / "legal_rules"

LEGAL_INDEX_FILE = LEGAL_DIR / "legal_rules_index.json"
LEGAL_SUMMARY_FILE = LEGAL_DIR / "legal_rules_summary.md"


LEGAL_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "luat_gia_2023",
        "title": "Luật Giá số 16/2023/QH15",
        "type": "Luật",
        "issuer": "Quốc hội",
        "issued_date": "19/06/2023",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?docid=208367&pageid=27160",
        "summary": (
            "Luật Giá là cơ sở pháp lý nền tảng về quản lý giá, thẩm định giá, "
            "cơ sở dữ liệu về giá, hoạt động phân tích, dự báo giá thị trường và "
            "quản lý nhà nước trong lĩnh vực giá."
        ),
        "applicable_to_system": [
            "Xác định nguyên tắc hệ thống không được tự ý bịa giá khi thiếu căn cứ.",
            "Yêu cầu dữ liệu giá và căn cứ định giá phải có khả năng lưu vết.",
            "Hỗ trợ xây dựng cơ sở dữ liệu giá và kho tri thức phục vụ định giá.",
        ],
    },
    {
        "id": "nghi_dinh_78_2024",
        "title": "Nghị định 78/2024/NĐ-CP",
        "type": "Nghị định",
        "issuer": "Chính phủ",
        "issued_date": "01/07/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://vanban.chinhphu.vn/?docid=210548&pageid=27160",
        "summary": (
            "Nghị định quy định chi tiết một số điều của Luật Giá về thẩm định giá, "
            "liên quan đến hoạt động thẩm định giá, điều kiện, hồ sơ và trách nhiệm "
            "của các chủ thể tham gia."
        ),
        "applicable_to_system": [
            "Hệ thống cần lưu lại thông tin người thẩm định/phê duyệt và chứng thư.",
            "Dữ liệu sau khi phê duyệt phải được quản lý rõ ràng trong database.",
            "Các kết quả AI chỉ là hỗ trợ tham khảo, cần có bước phê duyệt.",
        ],
    },
    {
        "id": "thong_tu_30_2024",
        "title": "Thông tư 30/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://chinhphu.vn/?classid=1&docid=210415&pageid=27160",
        "summary": (
            "Thông tư ban hành các chuẩn mực thẩm định giá Việt Nam về quy tắc đạo đức "
            "nghề nghiệp, phạm vi công việc, cơ sở giá trị thẩm định giá và hồ sơ thẩm định giá."
        ),
        "applicable_to_system": [
            "Kết quả định giá phải có căn cứ, phạm vi và nguồn dữ liệu rõ ràng.",
            "Không được trình bày kết quả AI như kết luận thẩm định chính thức nếu chưa được phê duyệt.",
            "Sau khi phê duyệt, hệ thống cần lưu hồ sơ gồm giá, căn cứ, nguồn, ngày và người phê duyệt.",
        ],
    },
    {
        "id": "thong_tu_31_2024",
        "title": "Thông tư 31/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://thuvienphapluat.vn/van-ban/Tai-chinh-nha-nuoc/Thong-tu-31-2024-TT-BTC-Chuan-muc-tham-dinh-gia-Thu-thap-thong-tin-tai-san-tham-dinh-gia-612479.aspx",
        "summary": (
            "Thông tư ban hành chuẩn mực về thu thập và phân tích thông tin về tài sản "
            "thẩm định giá."
        ),
        "applicable_to_system": [
            "AI phải thu thập và phân tích thông tin từ nhiều nguồn trước khi đề xuất giá.",
            "Nguồn dữ liệu cần được phân loại: database nội bộ, kho tri thức, Internet, nguồn tham khảo.",
            "Nếu thông tin mơ hồ hoặc thiếu thông số, AI phải nêu rõ giả định.",
        ],
    },
    {
        "id": "thong_tu_32_2024",
        "title": "Thông tư 32/2024/TT-BTC",
        "type": "Thông tư",
        "issuer": "Bộ Tài chính",
        "issued_date": "16/05/2024",
        "effective_date": "01/07/2024",
        "source_url": "https://chinhphu.vn/?classid=1&docid=210428&pageid=27160",
        "summary": (
            "Thông tư ban hành các chuẩn mực thẩm định giá Việt Nam về cách tiếp cận từ "
            "thị trường, cách tiếp cận từ chi phí và cách tiếp cận từ thu nhập."
        ),
        "applicable_to_system": [
            "Với vật tư, thiết bị, hàng hóa phổ thông, ưu tiên cách tiếp cận từ thị trường.",
            "Khi có nhiều báo giá tham khảo, AI cần so sánh, chọn nguồn phù hợp và nêu độ tin cậy.",
            "Nếu thiếu dữ liệu thị trường, AI không được tự bịa giá.",
        ],
    },
]


AI_VALUATION_RULES: List[Dict[str, Any]] = [
    {
        "id": "rule_001_no_fake_price",
        "title": "Không bịa giá khi thiếu dữ liệu",
        "priority": "critical",
        "rule": (
            "Nếu không có giá cụ thể từ database nội bộ, kho tri thức, hoặc nguồn Internet đáng tin cậy, "
            "AI phải trả về 'Không đủ dữ liệu định giá', không được tự tạo ra mức giá."
        ),
        "legal_basis": [
            "Luật Giá số 16/2023/QH15",
            "Thông tư 30/2024/TT-BTC",
            "Thông tư 31/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_002_internal_data_first",
        "title": "Ưu tiên dữ liệu nội bộ đã thẩm định",
        "priority": "high",
        "rule": (
            "Khi database nội bộ hoặc LLM Wiki có dữ liệu tương tự đã được thẩm định, AI phải ưu tiên "
            "dữ liệu này trước khi sử dụng dữ liệu Internet."
        ),
        "legal_basis": [
            "Luật Giá số 16/2023/QH15",
            "Thông tư 30/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_003_market_approach",
        "title": "Ưu tiên cách tiếp cận từ thị trường với hàng hóa phổ thông",
        "priority": "high",
        "rule": (
            "Với vật tư, thiết bị, hàng hóa, xe, máy móc phổ thông, AI cần ưu tiên cách tiếp cận từ thị trường: "
            "so sánh giá từ database, vật tư tương tự, báo giá đại lý, sàn thương mại điện tử hoặc nguồn bán hàng đáng tin cậy."
        ),
        "legal_basis": [
            "Thông tư 32/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_004_state_assumptions",
        "title": "Phải nêu giả định khi truy vấn mơ hồ",
        "priority": "high",
        "rule": (
            "Nếu người dùng nhập thiếu thông tin như đời xe, model, cấu hình, tình trạng, dung lượng, phiên bản, "
            "AI được phép mở rộng truy vấn nhưng phải ghi rõ giả định trong phần căn cứ."
        ),
        "legal_basis": [
            "Thông tư 31/2024/TT-BTC",
            "Thông tư 30/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_005_confidence_required",
        "title": "Bắt buộc có độ tin cậy",
        "priority": "medium",
        "rule": (
            "Mọi kết quả định giá phải có độ tin cậy: cao, trung bình hoặc thấp. "
            "Độ tin cậy phải dựa trên số lượng nguồn, chất lượng nguồn và mức độ khớp thông số sản phẩm."
        ),
        "legal_basis": [
            "Thông tư 30/2024/TT-BTC",
            "Thông tư 31/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_006_human_approval_required",
        "title": "AI chỉ hỗ trợ, không thay thế phê duyệt",
        "priority": "critical",
        "rule": (
            "Kết quả AI chỉ là tham khảo. Chỉ khi người dùng có thẩm quyền bấm phê duyệt thì kết quả mới được lưu vào database "
            "và trở thành dữ liệu tham chiếu cho các lần sau."
        ),
        "legal_basis": [
            "Nghị định 78/2024/NĐ-CP",
            "Thông tư 30/2024/TT-BTC",
        ],
    },
    {
        "id": "rule_007_record_after_approval",
        "title": "Lưu hồ sơ sau phê duyệt",
        "priority": "high",
        "rule": (
            "Sau khi phê duyệt, hệ thống phải lưu lại tên tài sản, giá phê duyệt, căn cứ, nguồn dữ liệu, "
            "ngày phê duyệt, người phê duyệt và đồng bộ vào LLM Wiki để tái sử dụng."
        ),
        "legal_basis": [
            "Luật Giá số 16/2023/QH15",
            "Thông tư 30/2024/TT-BTC",
        ],
    },
]


def ensure_dirs() -> None:
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    no_accent = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return no_accent.replace("đ", "d").replace("Đ", "D")


def normalize(value: str) -> str:
    value = strip_accents(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str, fallback: str = "legal_rule") -> str:
    slug = normalize(value).replace(" ", "_")
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or fallback


def write_legal_document_page(document: Dict[str, Any]) -> None:
    ensure_dirs()

    path = LEGAL_DIR / f"{document['id']}.md"

    applicable_lines = "\n".join(
        f"- {item}" for item in document.get("applicable_to_system", [])
    )

    content = f"""# {document['title']}

## Thông tin văn bản

- Loại văn bản: {document['type']}
- Cơ quan ban hành: {document['issuer']}
- Ngày ban hành: {document['issued_date']}
- Ngày có hiệu lực: {document['effective_date']}
- Nguồn tham khảo chính thức: {document['source_url']}

## Tóm tắt áp dụng

{document['summary']}

## Cách áp dụng vào hệ thống AI định giá

{applicable_lines}

## Vai trò trong LLM Wiki

Văn bản này được chuyển hóa thành tri thức pháp lý/nghiệp vụ để AI Agent sử dụng khi định giá.

LLM Wiki không thay thế văn bản pháp luật gốc.  
LLM Wiki chỉ lưu tóm tắt quy tắc áp dụng để hỗ trợ hệ thống đưa ra kết quả có căn cứ hơn.
"""

    path.write_text(content, encoding="utf-8")


def write_ai_rule_page(rule: Dict[str, Any]) -> None:
    ensure_dirs()

    path = LEGAL_DIR / f"{rule['id']}.md"

    legal_basis = "\n".join(
        f"- [[{basis}]]" for basis in rule.get("legal_basis", [])
    )

    content = f"""# {rule['title']}

## Mức ưu tiên

{rule['priority']}

## Quy tắc áp dụng cho AI

{rule['rule']}

## Căn cứ pháp lý / chuẩn mực liên quan

{legal_basis}

## Cách hệ thống sử dụng

Quy tắc này được nạp vào prompt định giá để AI kiểm tra trước khi đưa ra kết quả.

Nếu kết quả AI vi phạm quy tắc này, hệ thống phải ưu tiên an toàn:
- Không bịa giá
- Không phê duyệt tự động
- Yêu cầu bổ sung thông tin hoặc nguồn dữ liệu
"""

    path.write_text(content, encoding="utf-8")


def write_legal_summary() -> None:
    ensure_dirs()

    doc_lines = "\n".join(
        f"- {doc['title']} — hiệu lực: {doc['effective_date']}"
        for doc in LEGAL_DOCUMENTS
    )

    rule_lines = "\n".join(
        f"- [{rule['priority']}] {rule['title']}: {rule['rule']}"
        for rule in AI_VALUATION_RULES
    )

    content = f"""# Legal Rules / Chuẩn mực định giá cho AI

Cập nhật lần cuối: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

## Văn bản pháp lý và chuẩn mực sử dụng

{doc_lines}

## Quy tắc AI phải tuân thủ

{rule_lines}

## Vai trò trong hệ thống

Kho luật này là một phần của LLM Wiki Framework.

Khi AI định giá, hệ thống sẽ nạp các quy tắc này vào ngữ cảnh để:
- Ưu tiên dữ liệu nội bộ
- Ưu tiên cách tiếp cận thị trường với hàng hóa phổ thông
- Không bịa giá khi thiếu dữ liệu
- Nêu rõ giả định khi truy vấn mơ hồ
- Trả kết quả có căn cứ và độ tin cậy
- Chỉ lưu dữ liệu sau khi người dùng phê duyệt
"""

    LEGAL_SUMMARY_FILE.write_text(content, encoding="utf-8")


def ensure_legal_rules() -> Dict[str, Any]:
    ensure_dirs()

    for document in LEGAL_DOCUMENTS:
        write_legal_document_page(document)

    for rule in AI_VALUATION_RULES:
        write_ai_rule_page(rule)

    write_legal_summary()

    index_data = {
        "updated_at": datetime.now().isoformat(),
        "document_count": len(LEGAL_DOCUMENTS),
        "rule_count": len(AI_VALUATION_RULES),
        "documents": LEGAL_DOCUMENTS,
        "ai_valuation_rules": AI_VALUATION_RULES,
    }

    LEGAL_INDEX_FILE.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "success",
        "message": "Đã tạo/cập nhật kho luật định giá trong LLM Wiki",
        "document_count": len(LEGAL_DOCUMENTS),
        "rule_count": len(AI_VALUATION_RULES),
        "legal_dir": str(LEGAL_DIR),
        "summary_file": str(LEGAL_SUMMARY_FILE),
    }


def legal_rules_status() -> Dict[str, Any]:
    ready = LEGAL_INDEX_FILE.exists() and LEGAL_SUMMARY_FILE.exists()

    return {
        "ready": ready,
        "document_count": len(LEGAL_DOCUMENTS),
        "rule_count": len(AI_VALUATION_RULES),
        "legal_dir": str(LEGAL_DIR),
        "index_file": str(LEGAL_INDEX_FILE),
        "summary_file": str(LEGAL_SUMMARY_FILE),
    }


def get_legal_rules() -> Dict[str, Any]:
    ensure_legal_rules()

    return {
        "documents": LEGAL_DOCUMENTS,
        "ai_valuation_rules": AI_VALUATION_RULES,
    }


def load_legal_rules_for_ai() -> str:
    ensure_legal_rules()

    document_lines = []

    for doc in LEGAL_DOCUMENTS:
        document_lines.append(
            f"- {doc['title']} ({doc['type']}, {doc['issuer']}, hiệu lực {doc['effective_date']}): {doc['summary']}"
        )

    rule_lines = []

    for rule in AI_VALUATION_RULES:
        basis = ", ".join(rule.get("legal_basis", []))
        rule_lines.append(
            f"- [{rule['priority'].upper()}] {rule['title']}: {rule['rule']} Căn cứ: {basis}."
        )

    return (
        "[Văn bản pháp lý / chuẩn mực định giá]\n"
        + "\n".join(document_lines)
        + "\n\n[Quy tắc AI định giá phải tuân thủ]\n"
        + "\n".join(rule_lines)
    )