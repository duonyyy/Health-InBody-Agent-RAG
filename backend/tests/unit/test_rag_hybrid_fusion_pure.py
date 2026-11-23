"""Unit tests for pure Hybrid Fusion functions (rag.hybrid_fusion).

Adheres to:
- Deterministic score normalization and weighted fusion.
- Chunk consistency checks (preventing silent corpus mismatch).
- Small-to-big parent document expansion and deduplication.
"""
import pytest
from rag.corpus_lifecycle import CorpusReleaseMismatchError
from rag.hybrid_fusion import (
    assert_same_chunk_consistency,
    canonical_content_key,
    combine_search_results,
    expand_parent_documents,
    normalize_scores,
)


def test_normalize_scores_edge_cases():
    assert normalize_scores([]) == {}
    assert normalize_scores([(0, 0.0), (1, 0.0)]) == {0: 0.0, 1: 0.0}

    scored = [(0, 5.0), (1, 10.0), (2, 2.5)]
    normalized = normalize_scores(scored)
    assert normalized[1] == 1.0
    assert normalized[0] == 0.5
    assert normalized[2] == 0.25


def test_canonical_content_key_priorities():
    # Chunk identity with document_id and chunk_id
    doc_chunk = {"document_id": "d1", "chunk_id": "c1", "content": "test"}
    assert canonical_content_key(doc_chunk) == ("chunk", "d1", "c1")

    # Content hash identity
    doc_hash = {"document_id": "d2", "content": "Nội dung duy nhất"}
    key_hash = canonical_content_key(doc_hash)
    assert key_hash[0] == "chunk" or key_hash[0] == "content"

    # Qdrant point fallback
    doc_point = {"qdrant_point_id": "pt-999"}
    assert canonical_content_key(doc_point)[0] in ("point", "chunk", "content")


def test_assert_same_chunk_consistency_conflict_raises():
    doc_a = {
        "document_id": "d1",
        "chunk_id": "c1",
        "content_hash": "hash_aaa",
        "release_id": "rel-v1",
    }
    doc_b_same = {
        "document_id": "d1",
        "chunk_id": "c1",
        "content_hash": "hash_aaa",
        "release_id": "rel-v1",
    }
    # No error when identical
    assert_same_chunk_consistency(doc_a, doc_b_same)

    # Error when content_hash conflicts
    doc_b_conflict_content = {
        "document_id": "d1",
        "chunk_id": "c1",
        "content_hash": "hash_bbb",
        "release_id": "rel-v1",
    }
    with pytest.raises(CorpusReleaseMismatchError, match="Conflicting chunk content"):
        assert_same_chunk_consistency(doc_a, doc_b_conflict_content)

    # Error when release_id conflicts
    doc_b_conflict_release = {
        "document_id": "d1",
        "chunk_id": "c1",
        "content_hash": "hash_aaa",
        "release_id": "rel-v2",
    }
    with pytest.raises(CorpusReleaseMismatchError, match="Conflicting chunk release"):
        assert_same_chunk_consistency(doc_a, doc_b_conflict_release)


def test_combine_search_results_dense_only():
    vector_results = [
        {"document_id": "d1", "chunk_id": "c1", "similarity_score": 0.8, "content": "Hướng dẫn tập ngực"},
    ]
    combined = combine_search_results(
        bm25_results=[],
        vector_results=vector_results,
        query="tập ngực",
    )
    assert len(combined) == 1
    assert combined[0]["retrieval_mode"] == "dense_only"
    assert combined[0]["search_method"] == "vector"
    assert combined[0]["vector_score"] == 1.0
    assert combined[0]["bm25_score"] == 0.0


def test_combine_search_results_bm25_only():
    bm25_results = [
        {"document_id": "d1", "chunk_id": "c1", "bm25_score": 4.5, "content": "Chỉ số BMI chuẩn"},
    ]
    combined = combine_search_results(
        bm25_results=bm25_results,
        vector_results=[],
        query="BMI chuẩn",
    )
    assert len(combined) == 1
    assert combined[0]["retrieval_mode"] == "bm25_only"
    assert combined[0]["search_method"] == "bm25"
    assert combined[0]["bm25_score"] == 1.0
    assert combined[0]["vector_score"] == 0.0


def test_combine_search_results_hybrid_merge_and_bonus():
    bm25_results = [
        {"document_id": "d1", "chunk_id": "c1", "bm25_score": 10.0, "content": "Thực đơn giảm mỡ", "content_type": "nutrition"},
        {"document_id": "d2", "chunk_id": "c2", "bm25_score": 5.0, "content": "Tập HIIT", "content_type": "exercise"},
    ]
    vector_results = [
        {"document_id": "d1", "chunk_id": "c1", "similarity_score": 0.9, "content": "Thực đơn giảm mỡ", "content_type": "nutrition"},
        {"document_id": "d3", "chunk_id": "c3", "similarity_score": 0.7, "content": "Chế độ ngủ", "content_type": "general_health"},
    ]

    # Query matches nutrition domain -> domain bonus 0.05
    combined = combine_search_results(
        bm25_results=bm25_results,
        vector_results=vector_results,
        query="ăn uống giảm calo dinh dưỡng",
        dense_weight=0.6,
        bm25_weight=0.4,
    )

    assert len(combined) == 3
    top_doc = combined[0]
    assert top_doc["document_id"] == "d1"
    assert top_doc["search_method"] == "hybrid"
    assert top_doc["retrieval_mode"] == "hybrid"
    # d1 has: 0.6 * 1.0 (norm vec) + 0.4 * 1.0 (norm bm25) + 0.1 (hybrid bonus) + 0.05 (domain bonus) = 1.15
    assert top_doc["hybrid_score"] == 1.15

    # Check that individual non-overlap docs have retrieval_mode = "hybrid" (since both branches ran)
    d2 = next(d for d in combined if d["document_id"] == "d2")
    assert d2["search_method"] == "bm25"
    assert d2["retrieval_mode"] == "hybrid"

    d3 = next(d for d in combined if d["document_id"] == "d3")
    assert d3["search_method"] == "vector"
    assert d3["retrieval_mode"] == "hybrid"


def test_expand_parent_documents_deduplication():
    child_chunks = [
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-1",
            "parent_id": "p-1",
            "parent_content": "Toàn văn bài hướng dẫn squat",
            "parent_title": "Squat chuẩn",
            "content": "Đoạn 1",
            "hybrid_score": 0.9,
        },
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-2",
            "parent_id": "p-1",
            "parent_content": "Toàn văn bài hướng dẫn squat",
            "parent_title": "Squat chuẩn",
            "content": "Đoạn 2",
            "hybrid_score": 0.7,
        },
    ]

    expanded = expand_parent_documents(child_chunks, max_parents=5)
    assert len(expanded) == 1
    parent = expanded[0]
    assert parent["is_expanded_parent"] is True
    assert parent["parent_id"] == "p-1"
    assert parent["content"] == "Toàn văn bài hướng dẫn squat"
    assert parent["hybrid_score"] == 0.9  # Retains highest score
    assert parent["child_chunk_id"] == "chunk-1"
    assert len(parent["matched_children"]) == 2


def test_expand_parent_documents_conflicting_parent_content_raises():
    child_chunks = [
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-1",
            "parent_id": "p-1",
            "parent_content": "Nội dung version 1",
            "content": "Đoạn 1",
        },
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-2",
            "parent_id": "p-1",
            "parent_content": "Nội dung version 2 khác biệt",
            "content": "Đoạn 2",
        },
    ]

    with pytest.raises(CorpusReleaseMismatchError, match="Conflicting parent content"):
        expand_parent_documents(child_chunks)
