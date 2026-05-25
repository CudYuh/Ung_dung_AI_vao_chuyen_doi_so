from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Product


APP_DIR = Path(__file__).resolve().parents[2]

RUNTIME_DIR = APP_DIR / "llm_wiki_runtime"
WIKI_DIR = RUNTIME_DIR / "wiki"

ENTITY_DIR = WIKI_DIR / "entities" / "vat_tu"
CONCEPT_DIR = WIKI_DIR / "concepts"
GRAPH_DIR = WIKI_DIR / "graph"

INDEX_FILE = WIKI_DIR / "search_index.json"
GRAPH_FILE = GRAPH_DIR / "graph_edges.csv"
OVERVIEW_FILE = WIKI_DIR / "overview.md"
LOG_FILE = WIKI_DIR / "log.md"


CONCEPTS = [
    {
        "id": "gia_tham_chieu",
        "title": "Giá tham chiếu",
        "description": "Mức giá được hệ thống sử dụng làm căn cứ tham khảo trong quá trình định giá tài sản.",
    },
    {
        "id": "nguon_du_lieu",
        "title": "Nguồn dữ liệu",
        "description": "Nguồn hình thành thông tin định giá, có thể đến từ database nội bộ, chứng thư, Internet hoặc AI tổng hợp.",
    },
    {
        "id": "quy_tac_chon_gia",
        "title": "Quy tắc chọn giá",
        "description": "Nguyên tắc chọn giá dựa trên dữ liệu đáng tin cậy, thông số kỹ thuật, ngày thẩm định và nguồn tham chiếu.",
    },
    {
        "id": "vat_tu_tuong_tu",
        "title": "Vật tư tương tự",
        "description": "Các vật tư có tên hoặc thông số gần giống, được dùng để hỗ trợ so sánh trong định giá.",
    },
    {
        "id": "second_brain",
        "title": "Second Brain",
        "description": "Lớp tri thức giúp hệ thống lưu ngữ cảnh, liên kết concept và giải thích căn cứ định giá.",
    },
]


RELATION_LABELS = {
    "thuoc_concept": "thuộc concept",
    "co_gia": "có giá",
    "co_don_vi_tinh": "có đơn vị tính",
    "co_ngay_tham_dinh": "có ngày thẩm định",
    "co_chung_thu": "có chứng thư",
    "co_nguon_du_lieu": "có nguồn dữ liệu",
    "co_nguoi_tham_dinh": "có người thẩm định",
    "co_thong_so_ky_thuat": "có thông số kỹ thuật",
    "gan_voi_vat_tu_tuong_tu": "gần với vật tư tương tự",
}


STOPWORDS = {
    "va",
    "cua",
    "cho",
    "voi",
    "the",
    "la",
    "co",
    "trong",
    "ngoai",
    "hang",
    "hoa",
    "san",
    "pham",
    "may",
    "cai",
    "bo",
    "chiec",
    "loai",
    "model",
    "cong",
    "suat",
    "dien",
    "ap",
}


def ensure_dirs() -> None:
    ENTITY_DIR.mkdir(parents=True, exist_ok=True)
    CONCEPT_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)


def text_value(value: Any, default: str = "") -> str:
    if value is None:
        return default

    value = str(value).strip()

    if value.lower() in {"nan", "none", "null"}:
        return default

    return value


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    no_accent = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return no_accent.replace("đ", "d").replace("Đ", "D")


def normalize(value: str) -> str:
    value = strip_accents(text_value(value).lower())
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def slugify(value: str, fallback: str = "vat_tu", max_length: int = 80) -> str:
    slug = normalize(value).replace(" ", "_")
    slug = re.sub(r"_+", "_", slug).strip("_")

    if not slug:
        slug = fallback

    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("_")

    return slug


def important_tokens(value: str) -> List[str]:
    tokens = [t for t in normalize(value).split() if len(t) >= 2]
    return [t for t in tokens if t not in STOPWORDS]

def clean_product_id(product: Product) -> str:
    raw_id = getattr(product, "id", None)

    if raw_id is None:
        return "unknown"

    try:
        number = float(raw_id)
        if number.is_integer():
            return str(int(number))
    except Exception:
        pass

    return slugify(str(raw_id), fallback="unknown", max_length=30)


def product_source_id(product: Product) -> str:
    safe_id = clean_product_id(product)
    safe_slug = slugify(product.name or "vat_tu", max_length=80)
    return f"vat_tu/{safe_id}_{safe_slug}"


def product_page_path(product: Product) -> Path:
    safe_id = clean_product_id(product)
    safe_slug = slugify(product.name or "vat_tu", max_length=80)
    return ENTITY_DIR / f"{safe_id}_{safe_slug}.md"





def product_to_record(product: Product) -> Dict[str, Any]:
    name = text_value(product.name, f"Vật tư #{product.id}")
    specifications = text_value(product.specifications)
    source_id = product_source_id(product)

    search_text = normalize(
        " ".join(
            [
                name,
                specifications,
                text_value(product.category),
                text_value(product.unit),
                text_value(product.price),
                text_value(product.certificate_number),
                text_value(product.source),
                text_value(product.appraiser),
            ]
        )
    )

    return {
        "id": product.id,
        "source_id": source_id,
        "name": name,
        "category": text_value(product.category),
        "unit": text_value(product.unit),
        "specifications": specifications,
        "price": text_value(product.price),
        "certificate_number": text_value(product.certificate_number),
        "appraisal_date": text_value(product.appraisal_date),
        "source": text_value(product.source),
        "appraiser": text_value(product.appraiser),
        "page_path": str(product_page_path(product).relative_to(WIKI_DIR)).replace("\\", "/"),
        "search_text": search_text,
    }


def write_concept_pages() -> None:
    ensure_dirs()

    for concept in CONCEPTS:
        path = CONCEPT_DIR / f"{concept['id']}.md"

        content = f"""# {concept['title']}

## Mô tả

{concept['description']}

## Vai trò trong hệ thống

Concept này giúp LLM Wiki chuẩn hóa ngữ cảnh nghiệp vụ và hỗ trợ AI Agent giải thích kết quả định giá.
"""

        path.write_text(content, encoding="utf-8")


def write_overview(total_products: int) -> None:
    content = f"""# LLM Wiki / Second Brain định giá vật tư

LLM Wiki là framework tri thức của hệ thống định giá.

Database lưu dữ liệu có cấu trúc.  
LLM Wiki chuyển dữ liệu đó thành entity, concept, index và graph để AI Agent có thể truy vấn và giải thích.

## Thống kê

- Tổng số vật tư được đồng bộ: {total_products}
- Tổng số concept nghiệp vụ: {len(CONCEPTS)}
- Cập nhật lần cuối: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
"""

    OVERVIEW_FILE.write_text(content, encoding="utf-8")


def write_log(message: str) -> None:
    ensure_dirs()

    line = f"- {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — {message}\n"

    if LOG_FILE.exists():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    else:
        LOG_FILE.write_text("# Log LLM Wiki\n\n" + line, encoding="utf-8")


def write_product_page(product: Product) -> Dict[str, Any]:
    ensure_dirs()

    record = product_to_record(product)
    path = product_page_path(product)

    concept_links = "\n".join(
        f"- [[{concept['title']}]]" for concept in CONCEPTS
    )

    content = f"""# {record['name']}

## Thông tin định giá

- ID database: {record['id']}
- Tên hàng hóa: {record['name']}
- Loại hàng hóa: {record['category'] or 'Chưa xác định'}
- Đơn vị tính: {record['unit'] or 'Chưa xác định'}
- Giá thẩm định: {record['price'] or 'Chưa xác định'} VND
- Ngày thẩm định: {record['appraisal_date'] or 'Chưa xác định'}
- Chứng thư thẩm định: {record['certificate_number'] or 'Chưa xác định'}
- Nguồn dữ liệu: {record['source'] or 'Chưa xác định'}
- Người thẩm định: {record['appraiser'] or 'Chưa xác định'}

## Thông số kỹ thuật

{record['specifications'] or 'Chưa có thông số kỹ thuật.'}

## Vai trò trong LLM Wiki

Trang này là entity tri thức của vật tư **{record['name']}**.

Entity này giúp hệ thống:

- Tra cứu lại thông tin định giá
- Giải thích nguồn dữ liệu
- Liên kết với concept nghiệp vụ
- Hỗ trợ AI Agent sử dụng lại tri thức trong các lần định giá sau

## Liên kết concept

{concept_links}

## Ghi chú đồng bộ

Trang được sinh tự động từ PostgreSQL thông qua LLM Wiki Framework.
"""

    path.write_text(content, encoding="utf-8")

    return record


def build_edges_for_record(record: Dict[str, Any]) -> List[Dict[str, str]]:
    source_id = record["source_id"]
    name = record["name"]

    edges: List[Dict[str, str]] = []

    for concept in CONCEPTS:
        edges.append(
            {
                "source": source_id,
                "source_label": name,
                "target": f"concept/{concept['id']}",
                "target_label": concept["title"],
                "relation": "thuoc_concept",
                "relation_label": RELATION_LABELS["thuoc_concept"],
            }
        )

    data_relations = [
        ("co_gia", "price", record.get("price")),
        ("co_don_vi_tinh", "unit", record.get("unit")),
        ("co_ngay_tham_dinh", "appraisal_date", record.get("appraisal_date")),
        ("co_chung_thu", "certificate", record.get("certificate_number")),
        ("co_nguon_du_lieu", "source", record.get("source")),
        ("co_nguoi_tham_dinh", "appraiser", record.get("appraiser")),
    ]

    for relation, data_type, value in data_relations:
        value = text_value(value)

        if not value:
            continue

        edges.append(
            {
                "source": source_id,
                "source_label": name,
                "target": f"data/{data_type}/{slugify(value, data_type)}",
                "target_label": value,
                "relation": relation,
                "relation_label": RELATION_LABELS[relation],
            }
        )

    specifications = text_value(record.get("specifications"))

    if specifications:
        short_spec = specifications

        if len(short_spec) > 120:
            short_spec = short_spec[:117] + "..."

        edges.append(
            {
                "source": source_id,
                "source_label": name,
                "target": f"data/spec/{record['id']}",
                "target_label": short_spec,
                "relation": "co_thong_so_ky_thuat",
                "relation_label": RELATION_LABELS["co_thong_so_ky_thuat"],
            }
        )

    return edges


def write_index(records: List[Dict[str, Any]]) -> None:
    ensure_dirs()
    INDEX_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_index() -> List[Dict[str, Any]]:
    if not INDEX_FILE.exists():
        return []

    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def write_graph_edges(edges: List[Dict[str, str]]) -> None:
    ensure_dirs()

    fieldnames = [
        "source",
        "source_label",
        "target",
        "target_label",
        "relation",
        "relation_label",
    ]

    with GRAPH_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(edges)


def load_graph_edges() -> List[Dict[str, str]]:
    if not GRAPH_FILE.exists():
        return []

    with GRAPH_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def rebuild_wiki_from_db(db: Session) -> Dict[str, Any]:
    ensure_dirs()
    write_concept_pages()

    products = (
        db.query(Product)
        .filter(Product.id.isnot(None))
        .order_by(Product.id.asc())
        .all()
    )

    records: List[Dict[str, Any]] = []
    edges: List[Dict[str, str]] = []
    skipped_count = 0

    for product in products:
        if product is None:
            skipped_count += 1
            continue

        if getattr(product, "id", None) is None:
            skipped_count += 1
            continue

        if not text_value(getattr(product, "name", "")):
            skipped_count += 1
            continue

        try:
            record = write_product_page(product)
            records.append(record)
            edges.extend(build_edges_for_record(record))
        except Exception as e:
            skipped_count += 1
            print(f"Skip product while building LLM Wiki: {e}")

    write_index(records)
    write_graph_edges(edges)
    write_overview(len(records))
    write_log(
        f"Rebuild toàn bộ LLM Wiki từ database: {len(records)} vật tư, {len(edges)} edges, bỏ qua {skipped_count} dòng lỗi."
    )

    return {
        "status": "success",
        "message": "Đã rebuild LLM Wiki từ database",
        "item_count": len(records),
        "concept_count": len(CONCEPTS),
        "graph_edge_count": len(edges),
        "skipped_count": skipped_count,
        "wiki_dir": str(WIKI_DIR),
    }

def sync_product_to_wiki(product: Product) -> Dict[str, Any]:
    ensure_dirs()
    write_concept_pages()

    record = write_product_page(product)

    records = load_index()
    records = [
        r for r in records
        if int(r.get("id", -1)) != int(product.id)
    ]

    records.append(record)
    records.sort(key=lambda r: int(r.get("id") or 0))

    write_index(records)

    edges = load_graph_edges()
    source_id = record["source_id"]

    edges = [
        e for e in edges
        if e.get("source") != source_id
    ]

    edges.extend(build_edges_for_record(record))
    write_graph_edges(edges)
    write_overview(len(records))
    write_log(
        f"Sync vật tư mới/cập nhật vào LLM Wiki: {record['name']} - ID {record['id']}."
    )

    return {
        "status": "success",
        "message": "Đã đồng bộ sản phẩm vào LLM Wiki",
        "item": record,
        "item_count": len(records),
        "graph_edge_count": len(edges),
    }


def score_record(record: Dict[str, Any], query: str) -> int:
    q_norm = normalize(query)

    if not q_norm:
        return 0

    search_text = record.get("search_text") or normalize(
        " ".join(
            [
                text_value(record.get("name")),
                text_value(record.get("specifications")),
                text_value(record.get("source")),
            ]
        )
    )

    score = 0

    if q_norm in search_text:
        score += 80

    for token in important_tokens(query):
        if token in search_text:
            score += 10

    name_norm = normalize(record.get("name", ""))

    if q_norm in name_norm:
        score += 50

    return score


def search_wiki(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    records = load_index()
    ranked = []

    for record in records:
        score = score_record(record, query)

        if score > 0:
            item = dict(record)
            item["score"] = score
            ranked.append(item)

    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked[:limit]


def wiki_status() -> Dict[str, Any]:
    records = load_index()
    edges = load_graph_edges()

    return {
        "ready": INDEX_FILE.exists() and GRAPH_FILE.exists(),
        "item_count": len(records),
        "concept_count": len(CONCEPTS),
        "graph_edge_count": len(edges),
        "wiki_dir": str(WIKI_DIR),
        "index_file": str(INDEX_FILE),
        "graph_file": str(GRAPH_FILE),
    }


def get_concepts() -> List[Dict[str, str]]:
    return CONCEPTS


def find_record_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    for record in load_index():
        try:
            if int(record.get("id")) == int(product_id):
                return record
        except Exception:
            continue

    return None


def find_best_record(
    query: Optional[str] = None,
    product_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if product_id is not None:
        return find_record_by_id(product_id)

    if query:
        results = search_wiki(query, limit=1)

        if results:
            return results[0]

    records = load_index()

    return records[0] if records else None


def similar_items_for_record(
    record: Dict[str, Any],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    records = load_index()

    base_tokens = set(
        important_tokens(
            record.get("name", "") + " " + record.get("specifications", "")
        )
    )

    if not base_tokens:
        return []

    ranked = []

    for other in records:
        if other.get("id") == record.get("id"):
            continue

        other_tokens = set(
            important_tokens(
                other.get("name", "") + " " + other.get("specifications", "")
            )
        )

        overlap = len(base_tokens & other_tokens)

        if overlap > 0:
            item = dict(other)
            item["similarity_score"] = overlap
            ranked.append(item)

    ranked.sort(key=lambda x: x["similarity_score"], reverse=True)

    return ranked[:limit]


def build_visual_graph(
    query: Optional[str] = None,
    product_id: Optional[int] = None,
) -> Dict[str, Any]:
    record = find_best_record(query=query, product_id=product_id)

    if not record:
        return {
            "status": "empty",
            "message": "Chưa có dữ liệu LLM Wiki. Hãy gọi /wiki/rebuild trước.",
            "center": None,
            "nodes": [],
            "edges": [],
        }

    center_id = record["source_id"]

    nodes: List[Dict[str, Any]] = [
        {
            "id": center_id,
            "label": record["name"],
            "type": "vat_tu",
            "group": "center",
            "data": record,
        }
    ]

    edges: List[Dict[str, Any]] = []

    def add_node(
        node_id: str,
        label: str,
        node_type: str,
        group: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not any(n["id"] == node_id for n in nodes):
            nodes.append(
                {
                    "id": node_id,
                    "label": label,
                    "type": node_type,
                    "group": group,
                    "data": data or {},
                }
            )

    def add_edge(
        source: str,
        target: str,
        relation: str,
        label: str,
    ) -> None:
        edge_id = f"{source}->{relation}->{target}"

        if not any(e["id"] == edge_id for e in edges):
            edges.append(
                {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "label": label,
                }
            )

    data_nodes = [
        ("price", "Giá", record.get("price"), "co_gia"),
        ("unit", "Đơn vị", record.get("unit"), "co_don_vi_tinh"),
        ("appraisal_date", "Ngày thẩm định", record.get("appraisal_date"), "co_ngay_tham_dinh"),
        ("certificate", "Chứng thư", record.get("certificate_number"), "co_chung_thu"),
        ("source", "Nguồn", record.get("source"), "co_nguon_du_lieu"),
        ("appraiser", "Người thẩm định", record.get("appraiser"), "co_nguoi_tham_dinh"),
    ]

    for key, title, value, relation in data_nodes:
        value = text_value(value)

        if not value:
            continue

        node_id = f"data/{key}/{slugify(value, key)}"

        add_node(
            node_id=node_id,
            label=f"{title}: {value}",
            node_type=key,
            group="data",
            data={
                "title": title,
                "value": value,
            },
        )

        add_edge(
            source=center_id,
            target=node_id,
            relation=relation,
            label=RELATION_LABELS[relation],
        )

    specifications = text_value(record.get("specifications"))

    if specifications:
        short_spec = specifications

        if len(short_spec) > 120:
            short_spec = short_spec[:117] + "..."

        node_id = f"data/spec/{record['id']}"

        add_node(
            node_id=node_id,
            label=f"Thông số: {short_spec}",
            node_type="specifications",
            group="data",
            data={
                "title": "Thông số kỹ thuật",
                "value": specifications,
            },
        )

        add_edge(
            source=center_id,
            target=node_id,
            relation="co_thong_so_ky_thuat",
            label=RELATION_LABELS["co_thong_so_ky_thuat"],
        )

    for concept in CONCEPTS:
        node_id = f"concept/{concept['id']}"

        add_node(
            node_id=node_id,
            label=concept["title"],
            node_type="concept",
            group="concept",
            data=concept,
        )

        add_edge(
            source=center_id,
            target=node_id,
            relation="thuoc_concept",
            label=RELATION_LABELS["thuoc_concept"],
        )

    for similar in similar_items_for_record(record, limit=3):
        node_id = similar["source_id"]

        add_node(
            node_id=node_id,
            label=similar["name"],
            node_type="vat_tu_tuong_tu",
            group="similar",
            data=similar,
        )

        add_edge(
            source=center_id,
            target=node_id,
            relation="gan_voi_vat_tu_tuong_tu",
            label=RELATION_LABELS["gan_voi_vat_tu_tuong_tu"],
        )

    return {
        "status": "success",
        "center": record,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }