import time

from agents import graph
from health.tools import check_medical_safety
from rag import search


def _state(question: str, **extra):
    state = {
        "question": question,
        "selected_agents": [graph.RAG_AGENT],
        "deadline_monotonic": time.monotonic() + 30,
        "agent_trace": [],
        "errors": [],
        "tool_results": [],
        "retrieved_docs": [],
        "safety_result": {"risk_level": "low"},
    }
    state.update(extra)
    return state


def test_additional_urgent_and_caution_phrases_are_classified_safely():
    assert check_medical_safety("Tôi bị choáng và lơ mơ sau khi tập")["risk_level"] == "urgent"
    assert check_medical_safety("Tôi đau khớp kéo dài, nên tập thế nào?")["risk_level"] == "medical_caution"
    assert check_medical_safety("Tôi đang dùng thuốc huyết áp")["risk_level"] == "medical_caution"
    assert check_medical_safety("Tính BMI 72 kg, cao 170 cm")["risk_level"] == "low"


def test_rag_evidence_is_backend_owned_and_invalid_citation_is_removed(monkeypatch):
    document = {
        "document_id": "inbody-pbf-001",
        "title": "Diễn giải PBF",
        "content": "PBF cần được đọc cùng các chỉ số thành phần cơ thể khác.",
        "source": "Health guideline",
        "source_url": "https://example.org/pbf",
        "content_type": "inbody_metric",
        "similarity_score": 0.91,
    }

    monkeypatch.setattr(graph, "hybrid_search", lambda *args, **kwargs: [document.copy()])
    monkeypatch.setattr(graph, "rerank_documents", lambda docs, *args, **kwargs: docs)
    monkeypatch.setattr(graph, "openai_chat_complete", lambda *args, **kwargs: "PBF cao hơn tham chiếu [99].")

    state = graph.rag_agent(_state("PBF nghĩa là gì?"))
    result = graph.response_composer_agent(state)

    assert result["evidence_status"] == "supported"
    assert result["evidence"] == [
        {
            "id": 1,
            "document_id": "inbody-pbf-001",
            "title": "Diễn giải PBF",
            "source": "Health guideline",
            "source_url": "https://example.org/pbf",
            "publisher": None,
            "source_tier": None,
            "published_at": None,
            "reviewed_at": None,
            "content_type": "inbody_metric",
            "excerpt": "PBF cần được đọc cùng các chỉ số thành phần cơ thể khác.",
            "retrieval_score": 0.91,
            "rerank_score": None,
        }
    ]
    assert "[99]" not in result["final_answer"]
    assert "[1] Diễn giải PBF — Health guideline" in result["final_answer"]


def test_empty_rag_context_is_explicitly_insufficient(monkeypatch):
    monkeypatch.setattr(graph, "hybrid_search", lambda *args, **kwargs: [])

    result = graph.rag_agent(_state("Protein nên ăn bao nhiêu?"))

    assert result["evidence"] == []
    assert result["evidence_status"] == "insufficient"
    assert any("Không tìm thấy tài liệu" in item for item in result["limitations"])


def test_insufficient_evidence_skips_llm_composer(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("LLM must not run without retrieval evidence")

    monkeypatch.setattr(graph, "openai_chat_complete", must_not_run)
    state = _state(
        "PBF nghĩa là gì?",
        evidence=[],
        evidence_status="insufficient",
        limitations=["Không tìm thấy tài liệu phù hợp trong kho tri thức hiện có."],
    )

    result = graph.response_composer_agent(state)

    assert "Không đủ bằng chứng" in result["final_answer"]
    assert result["errors"] == []
    assert result["agent_trace"][-1]["action"] == "compose_insufficient_evidence"


def test_agent_response_exposes_evidence_contract():
    payload = graph._response_from_state(
        {
            "final_answer": "Câu trả lời có nguồn [1].",
            "evidence_status": "supported",
            "evidence": [{"id": 1, "document_id": "doc-1"}],
            "limitations": ["Ví dụ giới hạn"],
        }
    )

    assert payload["evidence_status"] == "supported"
    assert payload["evidence"] == [{"id": 1, "document_id": "doc-1"}]
    assert payload["limitations"] == ["Ví dụ giới hạn"]


def test_composer_error_does_not_expose_provider_details(monkeypatch):
    def fail_with_internal_detail(*args, **kwargs):
        raise RuntimeError("host.docker.internal:11434 secret-provider-detail")

    monkeypatch.setattr(graph, "openai_chat_complete", fail_with_internal_detail)
    state = _state(
        "PBF nghĩa là gì?",
        evidence=[
            {
                "id": 1,
                "document_id": "doc-1",
                "title": "PBF",
                "source": "test",
                "excerpt": "PBF là tỷ lệ phần trăm mỡ cơ thể.",
            }
        ],
        evidence_status="supported",
        limitations=[],
    )

    result = graph.response_composer_agent(state)

    assert result["errors"] == ["Response composition is temporarily unavailable"]
    assert "host.docker.internal" not in " ".join(result["errors"])
    assert "secret-provider-detail" not in " ".join(result["errors"])


def test_medical_caution_retrieval_requests_medical_safety_filter(monkeypatch):
    captured = {}

    def fake_search(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(graph, "hybrid_search", fake_search)
    state = _state(
        "Tôi đang dùng thuốc, có nên thay đổi khẩu phần?",
        safety_result={"risk_level": "medical_caution"},
    )

    graph.rag_agent(state)

    assert captured["filters"] == {"content_type": "medical_safety"}


def test_retrieval_filters_follow_selected_specialists():
    assert graph._retrieval_filters(
        _state("Protein", selected_agents=[graph.NUTRITION_AGENT, graph.RAG_AGENT])
    ) == {"content_type": "nutrition"}
    assert graph._retrieval_filters(
        _state("PBF", selected_agents=[graph.INBODY_AGENT, graph.RAG_AGENT])
    ) == {"content_type": "inbody_metric"}
    assert graph._retrieval_filters(
        _state(
            "Ăn và tập",
            selected_agents=[graph.NUTRITION_AGENT, graph.TRAINING_AGENT, graph.RAG_AGENT],
        )
    ) == {"content_type": ["nutrition", "exercise"]}


def test_medical_caution_routing_skips_plan_and_web_agents():
    state = {
        "question": "Tôi đang dùng thuốc huyết áp, nên tập thế nào?",
        "history": [],
        "agent_trace": [],
        "errors": [],
        "safety_result": {"risk_level": "medical_caution"},
    }

    result = graph.supervisor_agent(state)

    assert result["selected_agents"] == [graph.RAG_AGENT]
    assert any(
        item["action"] == "restrict_medical_caution_route"
        for item in result["agent_trace"]
    )


def test_hybrid_search_filters_process_local_bm25_and_vector_results(monkeypatch):
    monkeypatch.setattr(
        search,
        "bm25_search",
        lambda *args, **kwargs: [
            {"doc_id": "recipe", "content": "Công thức salad", "content_type": "nutrition"},
            {"doc_id": "safety", "content": "Khi có triệu chứng cần đi khám", "content_type": "medical_safety"},
        ],
    )
    monkeypatch.setattr(
        search,
        "vector_search_fallback",
        lambda *args, **kwargs: [
            {
                "doc_id": "recipe-vector",
                "content": "Món ăn",
                "content_type": "nutrition",
                "similarity_score": 0.99,
            },
            {
                "doc_id": "safety-vector",
                "content": "Cần hỗ trợ y tế",
                "content_type": "medical_safety",
                "similarity_score": 0.7,
            },
        ],
    )

    results = search.hybrid_search(
        "Tôi đang dùng thuốc",
        filters={"content_type": "medical_safety"},
        use_rerank=False,
    )

    assert results
    assert {result["content_type"] for result in results} == {"medical_safety"}


def test_hybrid_skips_vector_when_bm25_covers_small_filtered_corpus(monkeypatch):
    monkeypatch.setattr(search, "_bm25_candidate_indices", lambda filters: [0, 1])
    monkeypatch.setattr(
        search,
        "bm25_search",
        lambda *args, **kwargs: [
            {
                "doc_id": "safety-1",
                "content": "Đang dùng thuốc nên hỏi bác sĩ.",
                "content_type": "medical_safety",
                "bm25_score": 2.0,
            },
            {
                "doc_id": "safety-2",
                "content": "Tập luyện thận trọng khi có bệnh nền.",
                "content_type": "medical_safety",
                "bm25_score": 1.0,
            },
        ],
    )

    def vector_must_not_run(*args, **kwargs):
        raise AssertionError("vector search should be skipped")

    monkeypatch.setattr(search, "vector_search_fallback", vector_must_not_run)

    results = search.hybrid_search(
        "Tôi đang dùng thuốc",
        filters={"content_type": "medical_safety"},
        use_rerank=False,
    )

    assert [result["doc_id"] for result in results] == ["safety-1", "safety-2"]


def test_local_filter_supports_multiple_content_types():
    assert search._matches_filters(
        {"content_type": "nutrition"},
        {"content_type": ["nutrition", "exercise"]},
    )
    assert not search._matches_filters(
        {"content_type": "medical_safety"},
        {"content_type": ["nutrition", "exercise"]},
    )


def test_bm25_tokenizer_matches_vietnamese_with_and_without_accents():
    assert search._tokenize("Đang dùng thuốc huyết áp") == search._tokenize(
        "Dang dung thuoc huyet ap"
    )


def test_composer_citation_index_does_not_duplicate_document_excerpt():
    formatted = graph._format_evidence(
        [
            {
                "id": 1,
                "document_id": "doc-1",
                "source": "unit-test",
                "title": "Safety",
                "excerpt": "Nội dung dài đã có trong phần tài liệu RAG.",
            }
        ]
    )

    assert "document_id=doc-1" in formatted
    assert "Nội dung dài" not in formatted


def test_bm25_filters_candidates_before_scoring(monkeypatch):
    documents = [
        {"doc_id": "nutrition", "content_type": "nutrition"},
        {"doc_id": "safety", "content_type": "medical_safety"},
    ]
    monkeypatch.setattr(search, "_documents", documents)
    monkeypatch.setattr(search, "_search_engine_initialized", True)
    monkeypatch.setattr(
        search,
        "_bm25_index",
        {"content_type_indices": {"nutrition": [0], "medical_safety": [1]}},
    )
    scored_indices = []

    def fake_score(query_tokens, index):
        scored_indices.append(index)
        return 1.0

    monkeypatch.setattr(search, "_bm25_score", fake_score)

    results = search.bm25_search(
        "thuốc",
        filters={"content_type": "medical_safety"},
    )

    assert scored_indices == [1]
    assert [result["doc_id"] for result in results] == ["safety"]


def test_bm25_initialization_scrolls_all_qdrant_pages(monkeypatch):
    class Point:
        def __init__(self, point_id):
            self.id = point_id
            self.payload = {"doc_id": point_id, "content": f"Nội dung {point_id}"}

    class FakeQdrant:
        def __init__(self):
            self.offsets = []

        def scroll(self, **kwargs):
            self.offsets.append(kwargs.get("offset"))
            if kwargs.get("offset") is None:
                return [Point("doc-1")], "next-page"
            return [Point("doc-2")], None

    fake_client = FakeQdrant()
    captured = {}
    monkeypatch.setattr(
        search,
        "initialize_search_index",
        lambda documents, **kwargs: captured.setdefault("documents", documents) is not None,
    )

    assert search.initialize_from_vector_store(limit=1, vector_client=fake_client) is True
    assert fake_client.offsets == [None, "next-page"]
    assert [document["doc_id"] for document in captured["documents"]] == ["doc-1", "doc-2"]


def test_bm25_snapshot_round_trip(tmp_path):
    snapshot = tmp_path / "bm25.json.gz"
    documents = [
        {
            "doc_id": "doc-1",
            "title": "Protein",
            "content": "Protein hỗ trợ duy trì khối cơ trong giai đoạn giảm mỡ.",
            "source": "unit-test",
            "content_type": "nutrition",
            "domain": "health_inbody",
        }
    ]

    assert search.initialize_search_index(documents)
    assert search.save_search_snapshot(
        snapshot,
        metadata={"qdrant_point_count": 1, "corpus_version": "test-v1"},
    )
    assert search.initialize_search_index([]) is False
    assert search.load_search_snapshot(snapshot)

    stats = search.get_search_stats()
    assert stats["documents_count"] == 1
    assert stats["bm25_persistence"] == "versioned_json_gzip_snapshot"
    assert stats["snapshot_point_count"] == 1
    assert stats["corpus_version"] == "test-v1"
