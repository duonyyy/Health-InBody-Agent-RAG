"""Unit tests for pure BM25 lexical functions (rag.bm25).

Adheres to:
- Pure deterministic logic testing (no network, I/O, or global state).
- AGENTS.md rule 8 (medical safety must filter out recipes).
"""
import pytest
from rag.bm25 import (
    build_bm25_index,
    compute_bm25_score,
    detect_content_type,
    extract_document_text,
    get_bm25_candidate_indices,
    is_recipe_document,
    matches_document_filters,
    normalize_lexical_text,
    normalize_search_document,
    score_bm25_corpus,
    tokenize,
)


def test_normalize_lexical_text_vietnamese_and_special_chars():
    """Verify Vietnamese accent striping and 'đ' replacement."""
    assert normalize_lexical_text("Đường huyết và Cân nặng") == "duong huyet va can nang"
    assert normalize_lexical_text("Đi bộ 30 phút mỗi ngày") == "di bo 30 phut moi ngay"
    assert normalize_lexical_text("") == ""
    assert normalize_lexical_text(None) == ""


def test_tokenize_extracts_words():
    """Verify word tokenization splits on non-word boundaries."""
    tokens = tokenize("Chỉ số BMI: 22.5 kg/m2! Đạt chuẩn?")
    assert tokens == ["chi", "so", "bmi", "22", "5", "kg", "m2", "dat", "chuan"]


def test_extract_document_text_combines_fields():
    doc1 = {"title": "Tiêu đề", "content": "Nội dung chi tiết", "source": "sach_y_khoa"}
    assert extract_document_text(doc1) == "Tiêu đề\nNội dung chi tiết\nsach_y_khoa"

    # Fallback to question / page_content / source_file
    doc2 = {"question": "Hỏi đáp", "page_content": "Trang 1", "source_file": "doc.pdf"}
    assert extract_document_text(doc2) == "Hỏi đáp\nTrang 1\ndoc.pdf"

    # Empty doc
    assert extract_document_text({}) == ""


def test_detect_content_type_heuristics():
    assert detect_content_type("Chỉ số BMI và mỡ nội tạng InBody") == "inbody_metric"
    assert detect_content_type("Tính lượng calo và protein cần nạp") == "nutrition"
    assert detect_content_type("Lịch tập cardio kháng lực tăng cơ") == "exercise"
    assert detect_content_type("Triệu chứng khó thở cần gặp bác sĩ gấp") == "medical_safety"
    assert detect_content_type("Thời tiết hôm nay thế nào") == "general_health"


def test_is_recipe_document_detection():
    # Explicit flag
    assert is_recipe_document({"is_recipe": True, "content": "text"}) is True
    assert is_recipe_document({"metadata": {"is_recipe": True}}) is True
    assert is_recipe_document({"metadata": {"document_kind": "recipe"}}) is True

    # Marker in content or title
    assert is_recipe_document({"content": "Nguyên liệu: 200g ức gà, muỗng cà phê muối"}) is True
    assert is_recipe_document({"title": "Công thức nấu súp gà ngô non", "content": "Rất ngon"}) is True
    assert is_recipe_document({"content": "Hầm 45 phút trên lửa nhỏ"}) is True

    # Non-recipe clinical advice
    assert is_recipe_document({"title": "Chế độ ăn cho người tiểu đường", "content": "Cần kiểm soát lượng carb"}) is False


def test_matches_document_filters_medical_safety_excludes_recipes():
    """AGENTS.md rule 8: Medical safety query must filter out recipes."""
    recipe_doc = {
        "content_type": "medical_safety",
        "title": "Công thức nấu cháo yến mạch",
        "content": "Nguyên liệu: yến mạch, sữa tươi.",
    }
    safety_doc = {
        "content_type": "medical_safety",
        "title": "Cảnh báo dùng thuốc hạ đường huyết",
        "content": "Cần tham khảo ý kiến bác sĩ chuyên khoa.",
    }

    filters = {"content_type": "medical_safety"}
    assert matches_document_filters(safety_doc, filters) is True
    assert matches_document_filters(recipe_doc, filters) is False


def test_matches_document_filters_ranges_and_operators():
    doc = {"content_type": "nutrition", "score": 85, "level": "medium"}

    assert matches_document_filters(doc, {"content_type": "nutrition"}) is True
    assert matches_document_filters(doc, {"content_type": ["nutrition", "exercise"]}) is True
    assert matches_document_filters(doc, {"content_type": "exercise"}) is False

    # Ranges
    assert matches_document_filters(doc, {"score": {"gte": 80, "lte": 90}}) is True
    assert matches_document_filters(doc, {"score": {"gt": 85}}) is False
    assert matches_document_filters(doc, {"score": {"lt": 80}}) is False

    # Non-existent field in range filter
    assert matches_document_filters(doc, {"missing_key": {"gte": 10}}) is False


def test_normalize_search_document_fields():
    raw_doc = {
        "id": "item-101",
        "question": "BMI là gì?",
        "page_content": "BMI là chỉ số khối cơ thể.",
        "metadata": {
            "source_file": "inbody_guide.pdf",
            "document_id": "guide-01",
            "chunk_id": "c-01",
        },
    }
    normalized = normalize_search_document(raw_doc, index=0)
    assert normalized is not None
    assert normalized["doc_id"] == "item-101"
    assert normalized["document_id"] == "guide-01"
    assert normalized["chunk_id"] == "c-01"
    assert normalized["content_type"] == "inbody_metric"
    assert normalized["domain"] == "health_inbody"
    assert "guide.pdf" in normalized["source"]

    # Empty document returns None
    assert normalize_search_document({"title": "", "content": ""}, index=1) is None


def test_build_bm25_index_and_scoring():
    docs = [
        {"doc_id": "1", "content": "Tập luyện kháng lực giúp tăng cơ bắp hiệu quả.", "content_type": "exercise"},
        {"doc_id": "2", "content": "Chế độ dinh dưỡng giàu protein hỗ trợ phục hồi cơ bắp.", "content_type": "nutrition"},
        {"doc_id": "3", "content": "Đo chỉ số InBody để biết phần trăm mỡ và khối lượng cơ.", "content_type": "inbody_metric"},
    ]

    index = build_bm25_index(docs)
    assert index["doc_count"] == 3
    assert index["avg_doc_len"] > 0
    assert "exercise" in index["content_type_indices"]

    # Score query against docs
    q_tokens = tokenize("tăng cơ bắp kháng lực")
    score_doc1 = compute_bm25_score(q_tokens, 0, index)
    score_doc2 = compute_bm25_score(q_tokens, 1, index)
    score_doc3 = compute_bm25_score(q_tokens, 2, index)

    # Doc 1 has both "khang luc" and "tang co bap", so it should score highest
    assert score_doc1 > score_doc2
    assert score_doc1 > score_doc3

    # Out of bounds doc index returns 0.0
    assert compute_bm25_score(q_tokens, 999, index) == 0.0


def test_get_bm25_candidate_indices():
    index = {
        "content_type_indices": {
            "exercise": [0, 2],
            "nutrition": [1],
        }
    }
    # No filters -> all indices
    assert list(get_bm25_candidate_indices(3, index, None)) == [0, 1, 2]

    # Specific content_type filter
    candidates = get_bm25_candidate_indices(3, index, {"content_type": "exercise"})
    assert candidates == [0, 2]

    # Multiple content_types in list
    multi_candidates = get_bm25_candidate_indices(3, index, {"content_type": ["exercise", "nutrition"]})
    assert multi_candidates == [0, 1, 2]


def test_score_bm25_corpus_pure_execution():
    docs = [
        {"doc_id": "doc1", "content": "Tập squat để phát triển cơ đùi và cơ mông.", "content_type": "exercise"},
        {"doc_id": "doc2", "content": "Tập deadlift để tăng sức mạnh toàn thân.", "content_type": "exercise"},
        {"doc_id": "doc3", "content": "Thực đơn 2000 calo giàu đạm.", "content_type": "nutrition"},
    ]
    bm25_idx = build_bm25_index(docs)

    results = score_bm25_corpus(docs, bm25_idx, "bài tập squat đùi", limit=2)
    assert len(results) == 2
    assert results[0]["doc_id"] == "doc1"
    assert results[1]["doc_id"] == "doc2"
    assert results[0]["bm25_score"] > results[1]["bm25_score"]
    assert results[0]["search_method"] == "bm25"
    assert results[0]["retrieval_mode"] == "bm25_only"

    # Filter excludes doc1
    filtered_results = score_bm25_corpus(docs, bm25_idx, "bài tập squat đùi", filters={"content_type": "nutrition"})
    assert len(filtered_results) == 0
