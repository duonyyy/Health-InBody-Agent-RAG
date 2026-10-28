"""Unit tests for data_pipeline components."""

import gzip
import json
import sys
from pathlib import Path

import pytest

DATA_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DATA_PIPELINE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DATA_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(DATA_PIPELINE_ROOT))

try:
    from data_pipeline.configs.pipeline_config import PROJECT_DOMAIN
    from data_pipeline.src.chunkers.breadcrumbs import format_breadcrumb, inject_breadcrumb
    from data_pipeline.src.chunkers.markdown_chunker import chunk_document, normalize_chunk_text
    from data_pipeline.src.embedder.client import EmbeddingClient
    from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot
    from data_pipeline.src.indexers.qdrant_indexer import QdrantIndexer
    from data_pipeline.src.ingestion.raw_loader import clean_text, compact_parts, make_record
    from data_pipeline.src.processors.corpus_processor import normalize_document, seed_document
except ImportError:
    from configs.pipeline_config import PROJECT_DOMAIN
    from src.chunkers.breadcrumbs import format_breadcrumb, inject_breadcrumb
    from src.chunkers.markdown_chunker import chunk_document, normalize_chunk_text
    from src.embedder.client import EmbeddingClient
    from src.indexers.bm25_indexer import export_bm25_snapshot
    from src.indexers.qdrant_indexer import QdrantIndexer
    from src.ingestion.raw_loader import clean_text, compact_parts, make_record
    from src.processors.corpus_processor import normalize_document, seed_document


def test_breadcrumb_formatting():
    bc = format_breadcrumb("Hướng dẫn InBody", ["Chương 1", "Chỉ số PBF"])
    assert bc == "[Hướng dẫn InBody > Chương 1 > Chỉ số PBF]"

    injected = inject_breadcrumb("PBF là phần trăm mỡ.", bc)
    assert injected.startswith("[Hướng dẫn InBody > Chương 1 > Chỉ số PBF]\n")
    assert "PBF là phần trăm mỡ." in injected


def test_markdown_chunking_with_headers():
    doc = {
        "doc_id": "test_doc_01",
        "title": "Cẩm nang Thể hình",
        "content": (
            "# PHẦN 1: KỸ THUẬT CƠ BẢN\n\n"
            "## 1.1 Khởi động đúng cách\n"
            "Khởi động khớp cổ tay, cổ chân và xoay khớp vai trước khi tập.\n\n"
            "## 1.2 Squat đúng kỹ thuật\n"
            "Giữ lưng thẳng, hạ hông xuống ngang gối và hít sâu khi hạ người xuống."
        ),
        "source": "fitness_guide",
        "content_type": "exercise",
        "domain": PROJECT_DOMAIN,
        "language": "vi",
        "metadata": {"author": "Coach"},
    }

    chunks = chunk_document(doc, chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 2

    # Check first chunk
    c1 = chunks[0]
    assert c1["doc_id"] == "test_doc_01"
    assert c1["chunk_id"] == "test_doc_01-chunk-001"
    assert "[Cẩm nang Thể hình" in c1["breadcrumb"]
    assert c1["content"].startswith("[Cẩm nang Thể hình")
    assert c1["content_type"] == "exercise"
    assert c1["domain"] == PROJECT_DOMAIN
    assert "content_hash" in c1
    assert len(c1["content_hash"]) == 64


def test_bm25_snapshot_export(tmp_path: Path):
    chunks = [
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "title": "Chỉ số BMI",
            "content": "[InBody] BMI là chỉ số khối cơ thể.",
            "source": "inbody_guide",
            "content_type": "inbody_metric",
            "domain": PROJECT_DOMAIN,
            "metadata": {},
        },
        {
            "chunk_id": "c2",
            "doc_id": "d2",
            "title": "Cảnh báo máy tạo nhịp tim",
            "content": "[Cấp cứu] Chống chỉ định tuyệt đối đo InBody với người có máy tạo nhịp tim.",
            "source": "medical_safety",
            "content_type": "medical_safety",
            "domain": PROJECT_DOMAIN,
            "metadata": {},
        },
    ]

    snapshot_file = tmp_path / "bm25_test.json.gz"
    res = export_bm25_snapshot(
        chunks=chunks,
        output_path=snapshot_file,
        collection_name="test_collection",
        corpus_version="test.1",
    )

    assert res["status"] == "ok"
    assert snapshot_file.exists()

    with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["schema_version"] == 1
    assert payload["collection_name"] == "test_collection"
    assert payload["document_count"] == 2
    assert len(payload["documents"]) == 2
    assert payload["documents"][1]["title"] == "Cảnh báo máy tạo nhịp tim"


def test_qdrant_indexer_dry_run():
    chunks = [
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "title": "Chỉ số SMM",
            "content": "[InBody] SMM là khối lượng cơ xương.",
            "source": "inbody_guide",
            "content_type": "inbody_metric",
            "domain": PROJECT_DOMAIN,
            "breadcrumb": "[InBody]",
            "content_hash": "a" * 64,
            "metadata": {},
        }
    ]

    embedder = EmbeddingClient(vector_size=1024)
    indexer = QdrantIndexer(vector_size=1024)

    res = indexer.index_chunks(
        chunks=chunks,
        embedder=embedder,
        collection_name="test_collection",
        batch_size=10,
        dry_run=True,
    )

    assert res["status"] == "ok"
    assert res["dry_run"] is True
    assert res["indexed_points"] == 1


def test_table_aware_chunking_preserves_header():
    """Verify that splitting a large table maintains the table header row and separator in all chunks."""
    table_rows = ["| Chỉ số | Phân loại | Nguy cơ |", "|---|---|---|"]
    for i in range(1, 20):
        table_rows.append(f"| BMI {i} | Nhóm mức độ {i} | Nguy cơ mức {i} |")
    table_content = "\n".join(table_rows)

    doc = {
        "doc_id": "test_table_doc",
        "title": "Bảng phân loại nguy cơ BMI",
        "content": f"# Phân loại BMI\n\n{table_content}",
        "source": "medical_guideline",
        "content_type": "inbody_metric",
        "domain": PROJECT_DOMAIN,
    }

    chunks = chunk_document(doc, chunk_size=250, chunk_overlap=0)
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"

    for idx, c in enumerate(chunks):
        content = c["content"]
        assert "| Chỉ số | Phân loại | Nguy cơ |" in content, (
            f"Chunk {idx} missing table header: {content}"
        )
        assert "|---|---|---|" in content, (
            f"Chunk {idx} missing table separator: {content}"
        )


def test_table_aware_chunking_with_preceding_caption():
    """Verify that a short caption preceding a table is attached to sub-tables."""
    caption = "Bảng 1: Phân loại theo tiêu chuẩn WPRO:"
    table_rows = ["| Phân loại | BMI |", "|---|---|"]
    for i in range(1, 15):
        table_rows.append(f"| Nhóm {i} | {i*2} |")
    table_content = "\n".join(table_rows)

    doc = {
        "doc_id": "test_caption_doc",
        "title": "Tiêu chuẩn WPRO",
        "content": f"## Tiêu chuẩn Châu Á\n\n{caption}\n{table_content}",
        "source": "who_wpro",
        "content_type": "inbody_metric",
        "domain": PROJECT_DOMAIN,
    }

    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=0)
    assert len(chunks) >= 2
    for c in chunks:
        assert "| Phân loại | BMI |" in c["content"]
        assert "|---|---|" in c["content"]


def test_mixed_prose_and_table_chunking():
    """Verify that prose before and after a table are handled cleanly."""
    intro = "Đây là đoạn giới thiệu về cách đo lường chỉ số khối cơ thể và thành phần mỡ."
    table = (
        "| Chỉ số | Ý nghĩa |\n"
        "|---|---|\n"
        "| PBF | Phần trăm mỡ |\n"
        "| SMM | Khối lượng cơ xương |"
    )
    outro = "Người dùng nên tham khảo ý kiến chuyên gia thể hình trước khi áp dụng chế độ tập."

    doc = {
        "doc_id": "test_mixed_doc",
        "title": "Chỉ số InBody cơ bản",
        "content": f"# InBody cơ bản\n\n{intro}\n\n{table}\n\n{outro}",
        "source": "inbody_intro",
        "content_type": "inbody_metric",
        "domain": PROJECT_DOMAIN,
    }

    chunks = chunk_document(doc, chunk_size=600, chunk_overlap=50)
    assert len(chunks) >= 1
    # Check that table remains intact
    found_table = any("| PBF | Phần trăm mỡ |" in c["content"] for c in chunks)
    assert found_table is True


def test_parent_child_chunking_metadata():
    """Verify that child chunks track their parent_id and parent_content accurately."""
    doc = {
        "doc_id": "fitness_guide_01",
        "title": "Giáo án Thể hình Nâng cao",
        "content": (
            "# Hướng dẫn kỹ thuật\n\n"
            "## Bài tập Squat\n"
            "Squat là vua của các bài tập thân dưới. Đứng hai chân rộng bằng vai. "
            "Hạ hông xuống ngang gối hoặc sâu hơn một chút nếu khớp hông linh hoạt. "
            "Giữ cột sống trung tính trong toàn bộ phạm vi chuyển động. "
            "Hít một hơi sâu gồng chặt cơ bụng trước khi hạ người xuống, thở ra dứt khoát khi đẩy người đứng dậy.\n\n"
            "## Bài tập Deadlift\n"
            "Deadlift giúp phát triển toàn bộ chuỗi cơ sau từ bắp chân, đùi sau đến lưng xô. "
            "Đặt thanh đòn sát cẳng chân, kéo vai về sau và siết chặt xô."
        ),
        "source": "coach_guide",
        "content_type": "exercise",
        "domain": PROJECT_DOMAIN,
    }

    # Use small chunk_size so Squat section splits into multiple child chunks
    chunks = chunk_document(doc, chunk_size=150, chunk_overlap=20)
    assert len(chunks) >= 3

    squat_chunks = [c for c in chunks if c["parent_title"] == "Bài tập Squat"]
    deadlift_chunks = [c for c in chunks if c["parent_title"] == "Bài tập Deadlift"]

    assert len(squat_chunks) >= 2, "Squat section should split into multiple child chunks"
    assert len(deadlift_chunks) >= 1

    # Verify that all child chunks of Squat share the exact same parent_id and parent_content
    squat_parent_id = squat_chunks[0]["parent_id"]
    squat_parent_content = squat_chunks[0]["parent_content"]
    assert squat_parent_id.startswith("fitness_guide_01-parent-")
    assert "Squat là vua của các bài tập" in squat_parent_content

    for sc in squat_chunks:
        assert sc["parent_id"] == squat_parent_id
        assert sc["parent_content"] == squat_parent_content
        assert sc["has_parent"] is True
        assert sc["metadata"]["parent_id"] == squat_parent_id
        assert sc["metadata"]["parent_content"] == squat_parent_content

    # Deadlift should have a distinct parent_id
    assert deadlift_chunks[0]["parent_id"] != squat_parent_id
    assert "Deadlift giúp phát triển" in deadlift_chunks[0]["parent_content"]


def test_raw_loader_helpers():
    """Verify raw loader text cleaning and record schema creation."""
    assert clean_text("  chào bạn\r\n  ") == "chào bạn"
    assert clean_text(None) == ""
    assert compact_parts(["Dòng 1", "", "  Dòng 2  "]) == "Dòng 1\nDòng 2"

    rec = make_record(
        doc_id="test_01",
        title="Tiêu đề",
        content="Nội dung kiểm thử",
        source_id="test_src",
        content_type="exercise",
        language="vi",
        pipeline_role="rag_corpus",
        metadata={"extra": 123},
    )
    assert rec["doc_id"] == "test_01"
    assert rec["domain"] == PROJECT_DOMAIN
    assert rec["metadata"]["pipeline_role"] == "rag_corpus"
    assert rec["metadata"]["extra"] == 123


def test_corpus_processor_filtering_and_seeding():
    """Verify that corpus processor gates recipes and formats seed documents correctly."""
    # Recipe record should be rejected
    recipe_record = {
        "content_type": "recommender_interaction",
        "content": "Rating 5 sao",
        "metadata": {"pipeline_role": "recommender_interaction"},
    }
    assert normalize_document(recipe_record) is None

    # Too short document should be rejected
    short_record = {
        "content_type": "nutrition",
        "content": "Quá ngắn",
        "metadata": {"pipeline_role": "rag_corpus"},
    }
    assert normalize_document(short_record) is None

    # Valid record should pass
    valid_record = {
        "doc_id": "doc_valid_01",
        "title": "Chế độ dinh dưỡng lành mạnh",
        "content": "Ăn đủ chất đạm, tinh bột phức hợp và chất béo tốt để bảo đảm sức khỏe chuyển hóa.",
        "content_type": "nutrition",
        "source": "valid_source",
        "metadata": {"pipeline_role": "rag_corpus"},
    }
    doc = normalize_document(valid_record)
    assert doc is not None
    assert doc["doc_id"] == "doc_valid_01"
    assert doc["metadata"]["embedding_dataset"] == "health_inbody_embedding_v1"

    # Seed document should have guideline tier and medical review status
    seed = seed_document({
        "doc_id": "seed_01",
        "title": "Seed Title",
        "content": "Seed content đầy đủ chi tiết cho RAG an toàn.",
        "content_type": "medical_safety",
        "source_name": "Test Hospital",
        "source_url": "https://example.com",
    })
    assert seed["source"] == "internal_seed"
    assert seed["metadata"]["medical_disclaimer_required"] is True
    assert seed["metadata"]["medical_review_status"] == "approved"



