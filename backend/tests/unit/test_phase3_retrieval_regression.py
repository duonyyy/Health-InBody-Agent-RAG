import time

import pytest

from agents import graph
from rag import search
from rag.qdrant import client as qdrant_client
from rag.retrieval_errors import RetrievalDependencyError


def test_raw_search_happens_before_rewrite(monkeypatch):
    events = []
    monkeypatch.setattr(graph, "RAG_MAX_RETRIEVAL_QUERIES", 2)
    monkeypatch.setattr(graph, "hybrid_search", lambda query, **kw: events.append(("search", query)) or [])
    monkeypatch.setattr(graph, "rewrite_query_to_multi_queries", lambda query, **kw: events.append(("rewrite", query)) or ["query khác"])
    state = {"question": "Câu hỏi gốc", "selected_agents": [graph.RAG_AGENT],
             "deadline_monotonic": time.monotonic() + 60, "agent_trace": [], "errors": []}
    graph.rag_agent(state)
    assert events[:2] == [("search", "Câu hỏi gốc"), ("rewrite", "Câu hỏi gốc")]


def test_hybrid_sends_raw_query_to_both_branches(monkeypatch):
    events = []
    monkeypatch.setattr(search, "_search_index_metadata", {})
    monkeypatch.delenv("CORPUS_RELEASE_MANIFEST_PATH", raising=False)
    monkeypatch.setenv("CORPUS_VERIFY_ALIAS_ON_SEARCH", "false")
    monkeypatch.setattr(search, "bm25_search", lambda query, **kw: events.append(("bm25", query)) or [])
    monkeypatch.setattr(search, "vector_search_fallback", lambda query, **kw: events.append(("dense", query)) or [])
    monkeypatch.setattr(search, "expand_health_query", lambda query: query + " expanded")
    search.hybrid_search("Câu hỏi gốc", use_rerank=False, expand_parents=False)
    assert events == [("bm25", "Câu hỏi gốc"), ("dense", "Câu hỏi gốc")]


def test_fusion_keeps_local_chunk_ids_in_separate_documents():
    hits = [
        {"document_id": "d1", "chunk_id": "1", "content": "first", "bm25_score": 2},
        {"document_id": "d1", "chunk_id": "2", "content": "second", "bm25_score": 1},
        {"document_id": "d2", "chunk_id": "1", "content": "third", "bm25_score": 1},
    ]
    assert len(search.combine_search_results(hits, [], "question")) == 3


def test_fusion_refuses_conflicting_chunk_content():
    first = {"document_id": "d1", "chunk_id": "1", "content": "first", "bm25_score": 1}
    second = {"document_id": "d1", "chunk_id": "1", "content": "changed", "similarity_score": 1}
    with pytest.raises(search.CorpusReleaseMismatchError):
        search.combine_search_results([first], [second], "question")


def test_embedding_failure_is_not_healthy_empty(monkeypatch):
    monkeypatch.setattr(search, "_get_embedding", lambda *args, **kwargs: None)
    with pytest.raises(RetrievalDependencyError, match="embedding_unavailable"):
        search.vector_search_fallback("synthetic query")


def test_qdrant_failure_is_not_healthy_empty():
    class Broken:
        def query_points(self, **kwargs):
            raise OSError("offline")

    with pytest.raises(RetrievalDependencyError, match="qdrant_unavailable"):
        qdrant_client.search_vector("synthetic", [0.1], qdrant_client=Broken(), raise_on_error=True)


@pytest.mark.parametrize("vector", [[], [float("nan")], [float("inf")], "invalid"])
def test_invalid_embedding_is_rejected(monkeypatch, vector):
    monkeypatch.setattr(search, "_get_embedding", lambda *args, **kwargs: vector)
    with pytest.raises(RetrievalDependencyError, match="invalid_embedding"):
        search.vector_search_fallback("synthetic query")


def test_dependency_failure_marks_consumer_degraded(monkeypatch):
    monkeypatch.setattr(graph, "RAG_MAX_RETRIEVAL_QUERIES", 1)
    def broken(*args, **kwargs):
        raise RetrievalDependencyError("embedding_unavailable")
    monkeypatch.setattr(graph, "hybrid_search", broken)
    state = {"question": "synthetic", "selected_agents": [graph.RAG_AGENT],
             "deadline_monotonic": time.monotonic() + 60, "agent_trace": [], "errors": []}
    result = graph.rag_agent(state)
    assert result["retrieved_docs"] == []
    assert graph._response_from_state(result)["status"] == "degraded"
    assert "embedding_unavailable" in result["errors"][0]


def test_release_change_between_queries_is_refused_even_after_empty(monkeypatch):
    monkeypatch.setattr(search, "_search_index_metadata", {"physical_collection": "v1"})
    target = ["v1"]
    monkeypatch.setattr(search, "verify_runtime_release_sync", lambda **kw: {"synced": True, "pinned_collection": target[0]})
    calls = []
    monkeypatch.setattr(search, "bm25_search", lambda *a, **kw: [])
    monkeypatch.setattr(search, "vector_search_fallback", lambda *a, **kw: calls.append(kw["collection_name"]) or [])
    context = {}
    assert search.hybrid_search("raw", request_context=context, use_rerank=False) == []
    target[0] = "v2"
    with pytest.raises(search.CorpusReleaseMismatchError):
        search.hybrid_search("rewrite", request_context=context, use_rerank=False)
    assert calls == ["v1"]


def test_wrong_embedding_dimension_never_calls_qdrant(monkeypatch):
    monkeypatch.setattr(search, "_get_embedding", lambda *a, **kw: [0.1, 0.2])
    with pytest.raises(RetrievalDependencyError, match="invalid_embedding"):
        search.vector_search_fallback("synthetic")


def test_parent_keeps_matched_child_provenance_and_scopes_local_parent_id():
    docs = [{"document_id": doc, "chunk_id": chunk, "parent_id": "p1", "parent_content": "parent " + doc,
             "content": chunk} for doc, chunk in [("d1", "c1"), ("d1", "c2"), ("d2", "c1")]]
    result = search.expand_parent_documents(docs)
    assert len(result) == 2
    assert result[0]["child_chunk_id"] == "c1"
    assert {c["chunk_id"] for c in result[0]["matched_children"]} == {"c1", "c2"}
    assert result[1]["document_id"] == "d2"
    assert docs[0]["content"] == "c1"


def test_legacy_celery_rag_task_urgent_bypasses_rewrite_and_retrieval(monkeypatch):
    from jobs import tasks
    def forbidden(*args, **kwargs):
        raise AssertionError("urgent reached dependency")
    for module in (tasks, graph):
        for name in ("hybrid_search", "rewrite_query_to_multi_queries", "rerank_documents"):
            monkeypatch.setattr(module, name, forbidden)
    answer = tasks.bot_rag_answer_message.run([], "Tôi đau ngực và khó thở")
    assert isinstance(answer, str)
    assert "dừng tập" in answer.lower()


@pytest.mark.parametrize("rewritten", [[], ["raw", "raw"], None])
def test_empty_or_duplicate_rewrite_never_repeats_raw(monkeypatch, rewritten):
    calls = []
    monkeypatch.setattr(graph, "RAG_MAX_RETRIEVAL_QUERIES", 3)
    monkeypatch.setattr(graph, "hybrid_search", lambda q, **kw: calls.append(q) or [])
    monkeypatch.setattr(graph, "rewrite_query_to_multi_queries", lambda *a, **kw: rewritten)
    graph.rag_agent({"question": "raw", "selected_agents": [graph.RAG_AGENT],
                     "deadline_monotonic": time.monotonic() + 60, "agent_trace": [], "errors": []})
    assert calls == ["raw"]
