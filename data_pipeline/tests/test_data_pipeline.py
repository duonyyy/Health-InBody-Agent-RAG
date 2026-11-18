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

    assert res["ok"] is True
    assert res["status"] == "dry_run"
    assert res["dry_run"] is True
    assert res["indexed_points"] == 0
    assert res["validated_points"] == 1
    assert res["topology_verified"] is False


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

    # Seed document without a managed review record must NOT self-certify as approved/guideline
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
    assert seed["metadata"]["medical_review_status"] == "provisional"
    assert seed["metadata"]["review_verification_status"] == "unreviewed"
    assert seed["metadata"]["source_tier"] is None
    assert seed["metadata"]["source_tier_verified"] is False
    assert seed["metadata"]["published_at"] is None
    assert seed["metadata"]["reviewed_at"] is None
    assert seed["metadata"]["publisher"] is None
    assert seed["metadata"]["review_id"] is None


def test_seed_internal_curated_url_and_missing_dates_are_not_fabricated():
    seed = seed_document({
        "doc_id": "seed_curated_01",
        "title": "Nguyên tắc tập luyện",
        "content": "Tăng cơ cần tập kháng lực đều đặn, ăn đủ năng lượng và ngủ phục hồi.",
        "content_type": "exercise",
        "source_name": "Sports nutrition principles",
        "source_url": "internal_curated",
    })
    assert seed["metadata"]["source_url"] is None
    assert seed["metadata"]["publisher"] is None
    assert seed["metadata"]["source_tier"] is None
    assert seed["metadata"]["published_at"] is None
    assert seed["metadata"]["reviewed_at"] is None
    assert seed["metadata"]["medical_review_status"] == "provisional"
    assert seed["metadata"]["review_verification_status"] == "unreviewed"


def test_provenance_preserved_across_seed_chunk_bm25_and_qdrant_payload(tmp_path: Path):
    from data_pipeline.src.processors.provenance_bridge import compute_document_content_hash

    content = "Mỡ nội tạng nằm quanh các cơ quan trong ổ bụng và cần theo dõi định kỳ."
    content_hash = compute_document_content_hash(content)
    synthetic_registry = {
        "schema_version": 1,
        "registry_version": "test-synthetic",
        "is_synthetic_fixture": True,
        "reviewers": {
            "clinician-syn-1": {"name": "Synthetic Reviewer", "role": "clinical_reviewer", "active": True}
        },
        "reviews": [
            {
                "review_id": "rev-syn-001",
                "document_id": "seed_verified_01",
                "reviewer_id": "clinician-syn-1",
                "review_role": "clinical_reviewer",
                "review_scope": "inbody_metric",
                "reviewed_at": "2026-11-18T00:00:00Z",
                "content_hash": content_hash,
                "document_version": "1.0",
                "decision": "approved",
                "notes": "Synthetic test review matching exact content hash.",
                "verified_source_tier": "clinic_education",
                "verified_publisher": "Synthetic Clinical Board",
                "verified_source_url": "https://example.org/visceral-fat",
                "verified_published_at": "2025-06-01",
                "is_synthetic_fixture": True,
            }
        ],
    }

    doc = seed_document(
        {
            "doc_id": "seed_verified_01",
            "title": "Mỡ nội tạng",
            "content": content,
            "content_type": "inbody_metric",
        },
        review_registry=synthetic_registry,
        allow_synthetic_registry=True,
    )
    assert doc["metadata"]["medical_review_status"] == "approved"
    assert doc["metadata"]["review_verification_status"] == "verified"
    assert doc["metadata"]["review_id"] == "rev-syn-001"
    assert doc["metadata"]["source_tier"] == "clinic_education"

    chunks = chunk_document(doc, chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["document_id"] == "seed_verified_01"
    assert chunk["review_id"] == "rev-syn-001"
    assert chunk["review_verification_status"] == "verified"
    assert chunk["medical_review_status"] == "approved"
    assert chunk["document_content_hash"] == content_hash

    snapshot_file = tmp_path / "bm25_prov.json.gz"
    export_bm25_snapshot(
        chunks=chunks,
        output_path=snapshot_file,
        collection_name="test_collection",
        corpus_version="test.2",
    )
    with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
        snap = json.load(f)
    snap_doc = snap["documents"][0]
    assert snap_doc["document_id"] == "seed_verified_01"
    assert snap_doc["chunk_id"] == chunk["chunk_id"]
    assert snap_doc["review_id"] == "rev-syn-001"
    assert snap_doc["medical_review_status"] == "approved"
    assert snap_doc["review_verification_status"] == "verified"
    assert snap_doc["source_tier"] == "clinic_education"
    assert snap_doc["corpus_version"] == "test.2"

    # Qdrant payload check via mock upsert
    captured_points = []

    class FakeQdrantClient:
        def get_aliases(self):
            alias = type("Alias", (), {"alias_name": "nmk_chatbot_active", "collection_name": "prod_v0"})()
            return type("Resp", (), {"aliases": [alias]})()

        def upsert(self, collection_name, points, wait=True):
            captured_points.extend(points)
            return type("UpdateResult", (), {"status": "completed", "operation_id": 1})()

    class FakeEmbedder:
        def embed_texts(self, texts, dry_run=False):
            return [[0.1] * 8 for _ in texts]

    indexer = QdrantIndexer(vector_size=8, lock_dir=tmp_path / "locks")
    indexer._client = FakeQdrantClient()
    embedder = FakeEmbedder()
    res = indexer.index_chunks(
        chunks=chunks,
        embedder=embedder,
        collection_name="test_collection",
        batch_size=10,
        skip_existing=False,
        dry_run=False,
        corpus_version="test.2",
    )
    assert res["ok"] is True
    assert res["status"] == "committed"
    assert len(captured_points) == 1
    q_payload = captured_points[0].payload
    assert q_payload["document_id"] == "seed_verified_01"
    assert q_payload["review_id"] == "rev-syn-001"
    assert q_payload["review_verification_status"] == "verified"
    assert q_payload["medical_review_status"] == "approved"
    assert q_payload["source_tier"] == "clinic_education"


def test_raw_loader_does_not_default_medical_review_status_to_approved(tmp_path: Path):
    from data_pipeline.src.ingestion.raw_loader import merge_inbody_medical_knowledge

    raw_dir = tmp_path / "raw"
    kb_dir = raw_dir / "kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "sample.json").write_text(
        json.dumps(
            {
                "source_id": "sample_kb",
                "documents": [
                    {
                        "doc_id": "raw-unreviewed-01",
                        "title": "Sample",
                        "content": "Nội dung đủ dài để kiểm tra raw loader không tự gán approved.",
                        "content_type": "inbody_metric",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    records = list(
        merge_inbody_medical_knowledge(
            {"source_id": "sample_kb", "path": "kb", "pipeline_role": "rag_corpus"},
            raw_dir,
        )
    )
    assert len(records) == 1
    assert records[0]["metadata"]["medical_review_status"] is None
    normalized = normalize_document(records[0])
    assert normalized is not None
    assert normalized["metadata"]["medical_review_status"] == "unreviewed"
    assert normalized["metadata"]["review_verification_status"] == "unreviewed"



