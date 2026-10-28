"""Unit tests for Parent-Child (Small-to-Big Retrieval with Deduplication)."""
import pytest
from rag import search


def test_expand_parent_documents_deduplicates_by_parent_id():
    """Verify that multiple child chunks from the same parent are deduplicated into 1 parent doc with highest score."""
    child_docs = [
        {
            "doc_id": "doc1-chunk-001",
            "chunk_id": "doc1-chunk-001",
            "parent_id": "doc1-parent-01",
            "parent_title": "Bài tập Squat",
            "parent_content": "Toàn văn hướng dẫn Squat 2000 ký tự...",
            "content": "Child 1: tư thế chân",
            "title": "Squat tư thế chân",
            "hybrid_score": 0.95,
        },
        {
            "doc_id": "doc1-chunk-002",
            "chunk_id": "doc1-chunk-002",
            "parent_id": "doc1-parent-01",
            "parent_title": "Bài tập Squat",
            "parent_content": "Toàn văn hướng dẫn Squat 2000 ký tự...",
            "content": "Child 2: cách hít thở",
            "title": "Squat cách hít thở",
            "hybrid_score": 0.75,
        },
        {
            "doc_id": "doc2-chunk-001",
            "chunk_id": "doc2-chunk-001",
            "parent_id": "doc2-parent-01",
            "parent_title": "Bài tập Deadlift",
            "parent_content": "Toàn văn hướng dẫn Deadlift 1800 ký tự...",
            "content": "Child 3: vị trí thanh đòn",
            "title": "Deadlift vị trí thanh đòn",
            "hybrid_score": 0.88,
        },
    ]

    expanded = search.expand_parent_documents(child_docs, max_parents=5)
    assert len(expanded) == 2, f"Expected 2 unique parent docs, got {len(expanded)}"

    # First parent should be doc1 with the highest score from child 1 (0.95)
    p1 = expanded[0]
    assert p1["parent_id"] == "doc1-parent-01"
    assert p1["content"] == "Toàn văn hướng dẫn Squat 2000 ký tự..."
    assert p1["title"] == "Bài tập Squat"
    assert p1["hybrid_score"] == 0.95
    assert p1["child_chunk_id"] == "doc1-chunk-001"
    assert p1["is_expanded_parent"] is True

    # Second parent should be doc2 with score 0.88
    p2 = expanded[1]
    assert p2["parent_id"] == "doc2-parent-01"
    assert p2["content"] == "Toàn văn hướng dẫn Deadlift 1800 ký tự..."
    assert p2["title"] == "Bài tập Deadlift"
    assert p2["hybrid_score"] == 0.88


def test_expand_parent_documents_fallback_for_legacy_chunks():
    """Verify fallback behavior when chunks do not have parent_id or parent_content."""
    legacy_docs = [
        {
            "doc_id": "legacy-01",
            "title": "Legacy chunk without parent",
            "content": "Nội dung cũ",
            "hybrid_score": 0.9,
        },
        {
            "doc_id": "legacy-02",
            "title": "Legacy chunk 2",
            "content": "Nội dung cũ 2",
            "hybrid_score": 0.8,
        },
    ]

    expanded = search.expand_parent_documents(legacy_docs, max_parents=5)
    assert len(expanded) == 2
    assert expanded[0]["content"] == "Nội dung cũ"
    assert expanded[1]["content"] == "Nội dung cũ 2"


def test_hybrid_search_with_parent_expansion(monkeypatch):
    """Verify hybrid_search automatically performs parent expansion when enabled."""
    mock_bm25_results = [
        {
            "doc_id": "child-001",
            "chunk_id": "child-001",
            "parent_id": "parent-A",
            "parent_title": "Parent Section A",
            "parent_content": "Full text of Section A with 1500 chars...",
            "content": "Child 1 of A",
            "bm25_score": 3.0,
            "content_type": "exercise",
        },
        {
            "doc_id": "child-002",
            "chunk_id": "child-002",
            "parent_id": "parent-A",
            "parent_title": "Parent Section A",
            "parent_content": "Full text of Section A with 1500 chars...",
            "content": "Child 2 of A",
            "bm25_score": 2.5,
            "content_type": "exercise",
        },
        {
            "doc_id": "child-003",
            "chunk_id": "child-003",
            "parent_id": "parent-B",
            "parent_title": "Parent Section B",
            "parent_content": "Full text of Section B with 1200 chars...",
            "content": "Child 1 of B",
            "bm25_score": 2.0,
            "content_type": "exercise",
        },
    ]

    monkeypatch.setattr(search, "bm25_search", lambda *args, **kwargs: mock_bm25_results)
    monkeypatch.setattr(search, "vector_search_fallback", lambda *args, **kwargs: [])

    # Search with expand_parents=True (default)
    results = search.hybrid_search("luyện tập thể hình", limit=5, use_rerank=False, expand_parents=True)
    assert len(results) == 2, f"Expected 2 unique parents, got {len(results)}"
    assert results[0]["content"] == "Full text of Section A with 1500 chars..."
    assert results[1]["content"] == "Full text of Section B with 1200 chars..."

    # Search with expand_parents=False (returns raw child chunks)
    raw_results = search.hybrid_search("luyện tập thể hình", limit=5, use_rerank=False, expand_parents=False)
    assert len(raw_results) == 3
    assert raw_results[0]["content"] == "Child 1 of A"
