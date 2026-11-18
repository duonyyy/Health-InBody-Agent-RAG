"""HTTP TestClient, actual search, isolated embedding and transport boundaries."""
import pytest
from fastapi.testclient import TestClient
from api import app as api
from core.execution import reset_lanes
from llm import client as llm
from rag import search
from rag.qdrant import client as qdrant
from harness.budget import BudgetExhaustedError


@pytest.mark.parametrize("case,expected", [("empty", 200), ("embedding", 503), ("dimension", 503), ("timeout", 504), ("qdrant", 503)])
def test_search_empty_and_dependency_contract(monkeypatch, case, expected):
    reset_lanes(wait=False)
    monkeypatch.setattr(api, "_resolve_expensive_caller", lambda request: (None, "synthetic"))
    async def no_rate_limit(*args):
        return None
    monkeypatch.setattr(api, "_check_rate_limit_async", no_rate_limit)
    monkeypatch.setattr(search, "_search_index_metadata", {})
    monkeypatch.setattr(search, "_documents", [])
    monkeypatch.delenv("CORPUS_RELEASE_MANIFEST_PATH", raising=False)
    monkeypatch.setenv("CORPUS_VERIFY_ALIAS_ON_SEARCH", "false")
    def embedding(*args, **kwargs):
        if case == "embedding":
            raise OSError("synthetic private provider detail")
        if case == "timeout":
            raise BudgetExhaustedError("synthetic private timeout detail")
        return [0.1] * (2 if case == "dimension" else search.DEFAULT_VECTOR_SIZE)
    monkeypatch.setattr(llm, "get_embedding", embedding)
    class Transport:
        def query_points(self, **kwargs):
            if case == "qdrant":
                raise OSError("synthetic private transport detail")
            return []
    monkeypatch.setattr(qdrant, "search_client", Transport())
    try:
        response = TestClient(api.app).post("/search", json={"query": "synthetic", "use_rerank": False})
        assert response.status_code == expected
        assert "private" not in response.text
        if case == "empty":
            assert response.json()["results"] == []
    finally:
        reset_lanes(wait=False)
