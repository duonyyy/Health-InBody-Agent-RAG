"""Phase 3 regression tests: end-to-end deadlines (R02) and load/event-loop isolation (R03).

All tests run in-process with deterministic synthetic mocks — no external network or paid providers.
"""

import asyncio
import os
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from agents import composer, graph
from api import app as api_app
from core import cache as cache_mod
from core import execution as exec_mod
from core import rate_limit as rl_mod
from harness.budget import (
    BudgetExhaustedError,
    RequestBudget,
    retryable_llm_error,
)
from integrations import tavily as tavily_mod
from jobs import tasks as tasks_mod
from llm import client as llm_client
from llm import embedding as embedding_mod
from memory import chat as chat_mod
from memory import store as memory_store
from persistence import personalization_service as profiles
from rag import rerank as rerank_mod
from rag import search as search_mod
from rag.qdrant import client as qdrant_mod


@pytest.fixture(autouse=True)
def _reset_phase3_runtime(monkeypatch):
    """Ensure clean lanes, rate limits, and non-blocking cache for every test."""
    exec_mod.reset_lanes(wait=False)
    rl_mod.reset_local_rate_limits()
    monkeypatch.setattr(cache_mod, "get_redis_client", lambda *a, **k: None)
    monkeypatch.setattr(rl_mod, "get_redis_client", lambda *a, **k: None)
    yield
    exec_mod.reset_lanes(wait=False)
    rl_mod.reset_local_rate_limits()


# ---------------------------------------------------------------------------
# A. Budget & Transport Propagation (R02)
# ---------------------------------------------------------------------------


def test_openai_chat_passes_timeout_disables_sdk_retries_and_honors_wall_time(monkeypatch):
    init_calls = []
    options_calls = []
    create_calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            timeout = kwargs.get("timeout")
            assert timeout is not None and 0 < timeout <= 0.12
            # Simulate a slow upstream that respects transport timeout.
            time.sleep(min(timeout, 0.08))
            raise TimeoutError("simulated openai transport timeout")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            init_calls.append(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

        def with_options(self, **kwargs):
            options_calls.append(kwargs)
            return self

    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_client, "OPENAI_API_KEY", "sk-synthetic")
    monkeypatch.setattr(llm_client, "OPENAI_MODEL", "synthetic-model")
    monkeypatch.setattr(
        llm_client,
        "get_openai_client",
        lambda timeout=None, max_retries=0: FakeOpenAI(timeout=timeout, max_retries=max_retries),
    )

    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        llm_client.openai_chat_complete([{"role": "user", "content": "hi"}], timeout=0.10)
    elapsed = time.monotonic() - t0

    assert len(init_calls) == 1
    assert init_calls[0]["max_retries"] == 0
    assert 0 < init_calls[0]["timeout"] <= 0.10
    assert len(options_calls) == 1
    assert options_calls[0]["max_retries"] == 0
    assert 0 < options_calls[0]["timeout"] <= 0.10
    assert len(create_calls) == 1
    assert 0 < create_calls[0]["timeout"] <= 0.10
    assert elapsed < 0.35


def test_custom_provider_uses_remaining_timeout_instead_of_global_llm_timeout(monkeypatch):
    captured = []

    def fake_post(url, **kwargs):
        captured.append(kwargs.get("timeout"))
        timeout = kwargs.get("timeout")
        assert timeout is not None and timeout <= 0.15
        time.sleep(min(timeout, 0.05))
        raise TimeoutError("simulated custom provider timeout")

    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "custom")
    monkeypatch.setattr(llm_client, "VIETNAMESE_LLM_API_URL", "http://127.0.0.1:9999/v1/chat")
    monkeypatch.setattr(llm_client, "OPENAI_API_KEY", None)
    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        llm_client.openai_chat_complete([{"role": "user", "content": "hi"}], timeout=0.12)
    elapsed = time.monotonic() - t0

    assert len(captured) == 1
    assert 0 < captured[0] <= 0.12
    assert elapsed < 0.30


def test_fallback_skips_when_primary_exhausts_budget_and_shares_remaining_when_available(monkeypatch):
    fallback_timeouts = []

    class FakeCompletions:
        def create(self, **kwargs):
            fallback_timeouts.append(kwargs.get("timeout"))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback ok"))])

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_client, "OLLAMA_MODEL", "synthetic-ollama")
    monkeypatch.setattr(llm_client, "OPENAI_API_KEY", "sk-synthetic")
    monkeypatch.setattr(llm_client, "OPENAI_MODEL", "synthetic-openai")
    monkeypatch.setattr(llm_client, "get_openai_client", lambda *a, **k: fake_openai)

    # Case 1: primary burns > full budget -> fallback MUST NOT be called.
    def burn_all(url, **kwargs):
        time.sleep(0.12)
        raise ConnectionError("primary failed late")

    monkeypatch.setattr(llm_client.requests, "post", burn_all)
    with pytest.raises(BudgetExhaustedError):
        llm_client.openai_chat_complete([{"role": "user", "content": "hi"}], timeout=0.10)
    assert fallback_timeouts == []

    # Case 2: primary burns ~0.12s of 0.45s budget -> fallback receives <= remaining (~0.33s), not 0.45s!
    def burn_partial(url, **kwargs):
        time.sleep(0.12)
        raise ConnectionError("primary failed early")

    monkeypatch.setattr(llm_client.requests, "post", burn_partial)
    answer = llm_client.openai_chat_complete([{"role": "user", "content": "hi"}], timeout=0.45)
    assert answer == "fallback ok"
    assert len(fallback_timeouts) == 1
    assert 0.05 <= fallback_timeouts[0] < 0.36


def test_composer_retry_shares_deadline_and_never_retries_auth_or_validation_errors(monkeypatch):
    # Non-retryable classification checks
    class AuthenticationError(Exception):
        status_code = 401

    class BadRequestError(Exception):
        status_code = 400

    assert not retryable_llm_error(AuthenticationError("invalid api key"))
    assert not retryable_llm_error(BadRequestError("bad payload"))
    assert not retryable_llm_error(BudgetExhaustedError("expired"))
    assert not retryable_llm_error(PermissionError("forbidden"))
    assert retryable_llm_error(TimeoutError("socket timed out"))
    assert retryable_llm_error(ConnectionError("reset"))

    # Retry within tight shared budget: attempt 1 consumes almost all budget -> attempt 2 NOT dispatched!
    timeouts = []

    def slow_fail(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        time.sleep(0.28)
        raise TimeoutError("transient timeout")

    monkeypatch.setattr(graph, "openai_chat_complete", slow_fail)
    monkeypatch.setattr(composer, "AGENT_RETRY_BACKOFF_SECONDS", 0.05)

    t0 = time.monotonic()
    state = {
        "question": "Gợi ý dinh dưỡng",
        "selected_agents": [graph.NUTRITION_AGENT],
        "deadline_monotonic": time.monotonic() + 0.55,
        "retrieved_docs": [],
        "evidence": [],
        "tool_results": [],
        "safety_result": {"risk_level": "low"},
        "agent_trace": [],
        "errors": [],
        "limitations": [],
    }
    result = graph.response_composer_agent(state)
    elapsed = time.monotonic() - t0

    assert len(timeouts) == 1
    assert timeouts[0] < 0.45
    assert elapsed < 0.65
    assert any("deadline" in err.lower() for err in result["errors"])


def test_remaining_budget_decreases_across_stages_and_skips_exhausted_downstream(monkeypatch):
    stage_calls = []

    def fake_search(query, **kwargs):
        stage_calls.append(("search", kwargs.get("embedding_timeout"), kwargs.get("deadline_monotonic")))
        return [{"doc_id": "d1", "content": "BMI là chỉ số khối cơ thể.", "source": "s1"}]

    def fake_rerank(docs, query, **kwargs):
        stage_calls.append(("rerank", kwargs.get("timeout"), kwargs.get("deadline_monotonic")))
        return docs

    def fake_tavily(query, **kwargs):
        stage_calls.append(("tavily", kwargs.get("timeout"), kwargs.get("deadline_monotonic")))
        return "web ok"

    monkeypatch.setattr(graph, "hybrid_search", fake_search)
    monkeypatch.setattr(graph, "rerank_documents", fake_rerank)
    monkeypatch.setattr(graph, "tavily_search_health", fake_tavily)

    # Tight deadline (16s total, composer reserve = 15s -> 1s left for web/rerank, 0 for embedding since reserve=20s)
    state = {
        "question": "BMI mới nhất 2026 là gì?",
        "selected_agents": [graph.RAG_AGENT, graph.WEB_SEARCH_AGENT],
        "selected_capabilities": [graph.RAG_AGENT, graph.WEB_SEARCH_AGENT],
        "deadline_monotonic": time.monotonic() + 16.0,
        "retrieved_docs": [],
        "evidence": [],
        "tool_results": [],
        "safety_result": {"risk_level": "low"},
        "agent_trace": [],
        "errors": [],
        "limitations": [],
    }
    state = graph.rag_agent(state)
    state = graph.web_search_agent(state)

    # Search was skipped because remaining (16s) <= composer(15s) + qdrant(5s) = 20s
    assert not any(name == "search" for name, _, _ in stage_calls)
    # Web search ran with <= 1.0s (16s - 15s composer reserve)
    web_calls = [item for item in stage_calls if item[0] == "tavily"]
    assert len(web_calls) == 1
    assert 0 < web_calls[0][1] <= 1.1

    # Already exhausted deadline: web search MUST NOT call Tavily at all.
    stage_calls.clear()
    exhausted_state = {
        "question": "Tin mới nhất 2026",
        "selected_agents": [graph.WEB_SEARCH_AGENT],
        "deadline_monotonic": time.monotonic() + 0.5,  # well below 15s composer reserve
        "tool_results": [],
        "agent_trace": [],
        "errors": [],
    }
    graph.web_search_agent(exhausted_state)
    assert stage_calls == []
    assert any("deadline" in err.lower() for err in exhausted_state["errors"])


def test_embedding_lazy_init_never_calls_unbudgeted_health_probe(monkeypatch):
    monkeypatch.setattr(embedding_mod, "_embedding_service", None)

    def forbidden_get(*args, **kwargs):
        raise AssertionError("Lazy embedding init must not invoke unbudgeted /health probe")

    post_timeouts = []

    class FakeResp:
        status_code = 200

        def json(self):
            return {"embeddings": [[0.1, 0.2]], "processing_time": 0.01}

    def fake_post(url, **kwargs):
        post_timeouts.append(kwargs.get("timeout"))
        return FakeResp()

    monkeypatch.setattr(embedding_mod.requests, "get", forbidden_get)
    monkeypatch.setattr(embedding_mod.requests, "post", fake_post)

    vector = embedding_mod.get_custom_embedding(
        "BMI là gì?",
        timeout=0.35,
        deadline_monotonic=time.monotonic() + 0.25,
    )
    assert vector == [0.1, 0.2]
    assert len(post_timeouts) == 1
    assert 0 < post_timeouts[0] <= 0.25

    # Expired deadline must not call requests.post at all.
    post_timeouts.clear()
    with pytest.raises(BudgetExhaustedError):
        embedding_mod.get_custom_embedding(
            "BMI là gì?",
            deadline_monotonic=time.monotonic() - 0.1,
        )
    assert post_timeouts == []


def test_qdrant_search_never_rounds_small_budget_up_above_remaining(monkeypatch):
    qdrant_calls = []

    class FakeSearchClient:
        def search(self, **kwargs):
            qdrant_calls.append(kwargs.get("timeout"))
            return []

    monkeypatch.setattr(qdrant_mod, "search_client", FakeSearchClient())

    # 0.4s remaining < 1.0s integer floor -> must skip, NOT round up to 1s!
    with pytest.raises(BudgetExhaustedError):
        qdrant_mod.search_vector(
            "test_col",
            [0.1, 0.2],
            deadline_monotonic=time.monotonic() + 0.4,
            raise_on_timeout=True,
        )
    assert qdrant_calls == []

    # 2.8s remaining -> floor to 2s (never 3s!)
    qdrant_mod.search_vector(
        "test_col",
        [0.1, 0.2],
        deadline_monotonic=time.monotonic() + 2.8,
    )
    assert qdrant_calls == [2]


def test_rerank_and_tavily_skip_external_calls_when_budget_exhausted(monkeypatch):
    cohere_called = []
    monkeypatch.setattr(rerank_mod, "COHERE_API_KEY", "fake-key")
    monkeypatch.setattr(
        rerank_mod,
        "_get_cohere_client",
        lambda timeout=None: cohere_called.append(timeout) or SimpleNamespace(
            rerank=lambda **kw: SimpleNamespace(results=[])
        ),
    )
    docs = [{"doc_id": "1", "content": "BMI và PBF", "content_type": "inbody_metric"}]

    # Exhausted deadline -> Cohere not called, local heuristic returns result immediately.
    ranked = rerank_mod.rerank_documents(docs, "BMI", top_n=1, deadline_monotonic=time.monotonic() + 0.05)
    assert len(ranked) == 1
    assert cohere_called == []

    # Tavily exhausted deadline -> client not even requested.
    tavily_called = []
    monkeypatch.setattr(tavily_mod, "_get_tavily_client", lambda: tavily_called.append(1) or None)
    res = tavily_mod.tavily_search("BMI", deadline_monotonic=time.monotonic() + 0.05)
    assert "timeout:" in res["error"]
    assert tavily_called == []


def test_celery_task_aborts_immediately_when_queue_deadline_expired(monkeypatch):
    monkeypatch.setattr(
        chat_mod,
        "multi_agent_handle",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("graph must not run after queue expiry")),
    )
    monkeypatch.setattr(
        profiles,
        "safe_build_confirmed_context",
        lambda subject: {"available": False, "reason": "no_profile", "provenance": []},
    )
    execute = getattr(tasks_mod.llm_handle_message, "run", tasks_mod.llm_handle_message)
    result = execute(
        "health-inbody-agent",
        "alice",
        "Giải thích BMI giúp tôi",
        None,
        None,
        deadline_epoch=time.time() - 5.0,
    )
    assert result["status"] == "degraded"
    assert any("deadline" in err.lower() for err in result["errors"])


# ---------------------------------------------------------------------------
# B. Event Loop, Concurrency, Queue, Rate Limit & Abandonment (R03)
# ---------------------------------------------------------------------------


def test_slow_search_and_summarize_do_not_block_event_loop(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")

    def slow_search(*args, **kwargs):
        time.sleep(0.22)
        return [{"doc_id": "d1", "content": "BMI"}]

    def slow_summary(*args, **kwargs):
        time.sleep(0.22)
        return "Tóm tắt ngắn."

    monkeypatch.setattr(api_app, "hybrid_search", slow_search)
    monkeypatch.setattr(api_app, "summarize_text", slow_summary)

    async def measure(coro_fn):
        timer_ms = None
        t0 = time.perf_counter()

        async def timer():
            nonlocal timer_ms
            await asyncio.sleep(0.015)
            timer_ms = (time.perf_counter() - t0) * 1000.0

        t_timer = asyncio.create_task(timer())
        await asyncio.sleep(0)
        res = await coro_fn()
        await t_timer
        return res, timer_ms

    fake_req = SimpleNamespace(
        headers={},
        state=SimpleNamespace(),
        client=SimpleNamespace(host="127.0.0.1"),
    )

    search_res, search_timer_ms = asyncio.run(
        measure(lambda: api_app.search_endpoint(api_app.SearchRequest(query="bmi", limit=3, use_rerank=False), fake_req))
    )
    assert len(search_res["results"]) == 1
    assert search_timer_ms < 100.0

    sum_res, sum_timer_ms = asyncio.run(
        measure(lambda: api_app.summarize_endpoint(api_app.SummaryRequest(text="Nội dung InBody mẫu."), fake_req))
    )
    assert sum_res["summary"] == "Tóm tắt ngắn."
    assert sum_timer_ms < 100.0


def test_bounded_lane_concurrency_queue_and_abandoned_worker_accounting():
    lane = exec_mod.BoundedWorkLane(
        "test-abandon",
        max_concurrency=1,
        max_queue=0,
        queue_timeout_seconds=0.5,
    )
    started = threading.Event()
    release_worker = threading.Event()
    active_observed = 0
    max_active_observed = 0
    lock = threading.Lock()

    def blocking_work():
        nonlocal active_observed, max_active_observed
        with lock:
            active_observed += 1
            max_active_observed = max(max_active_observed, active_observed)
        started.set()
        release_worker.wait(timeout=2.0)
        with lock:
            active_observed -= 1
        return "done"

    async def scenario():
        # 1. Request 1 times out at HTTP budget while thread is STILL blocked.
        with pytest.raises(BudgetExhaustedError):
            await lane.run(blocking_work, budget=RequestBudget.start(0.06))

        assert started.is_set()
        stats_during = lane.stats()
        assert stats_during["active"] == 1
        assert stats_during["abandoned"] == 1

        # 2. Request 2 arrives while thread 1 is still running -> MUST be rejected (not spawn thread 2!).
        with pytest.raises(exec_mod.CapacityExceededError):
            await lane.run(blocking_work, budget=RequestBudget.start(0.5))
        assert max_active_observed == 1

        # 3. Release thread 1 -> permit is released exactly once; Request 3 succeeds cleanly.
        release_worker.set()
        for _ in range(40):
            if lane.stats()["active"] == 0:
                break
            await asyncio.sleep(0.01)

        stats_after = lane.stats()
        assert stats_after["active"] == 0
        assert stats_after["abandoned"] == 0

        res = await lane.run(lambda: "recovered", budget=RequestBudget.start(1.0))
        assert res == "recovered"
        assert lane.stats()["active"] == 0

    try:
        asyncio.run(scenario())
    finally:
        release_worker.set()
        lane.shutdown(wait=True)


def test_bounded_lane_client_cancellation_does_not_leak_permits():
    lane = exec_mod.BoundedWorkLane(
        "test-cancel",
        max_concurrency=1,
        max_queue=1,
        queue_timeout_seconds=1.0,
    )
    started = threading.Event()
    finish = threading.Event()

    def slow_job():
        started.set()
        finish.wait(timeout=2.0)
        return "ok"

    async def scenario():
        task = asyncio.create_task(lane.run(slow_job, budget=RequestBudget.start(5.0)))
        for _ in range(50):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Still holding permit while thread is running
        assert lane.stats()["active"] == 1
        assert lane.stats()["abandoned"] == 1

        finish.set()
        for _ in range(50):
            if lane.stats()["active"] == 0:
                break
            await asyncio.sleep(0.01)

        assert lane.stats()["active"] == 0
        assert lane.stats()["abandoned"] == 0
        assert await lane.run(lambda: "after-cancel", budget=RequestBudget.start(1.0)) == "after-cancel"

    try:
        asyncio.run(scenario())
    finally:
        finish.set()
        lane.shutdown(wait=True)


def test_input_bounds_and_production_auth_reject_before_provider(monkeypatch):
    provider_calls = []
    monkeypatch.setattr(api_app, "hybrid_search", lambda *a, **k: provider_calls.append("search") or [])
    monkeypatch.setattr(api_app, "summarize_text", lambda *a, **k: provider_calls.append("sum") or "ok")
    client = TestClient(api_app.app)

    # Production mode: unauthenticated /search and /summarize must return 401 before provider.
    monkeypatch.setenv("AUTH_MODE", "production")
    monkeypatch.setenv("ALLOW_PUBLIC_EXPENSIVE_ENDPOINTS", "false")
    assert client.post("/search", json={"query": "BMI là gì?"}).status_code == 401
    assert client.post("/summarize", json={"text": "Báo cáo InBody mẫu."}).status_code == 401
    assert provider_calls == []

    # Development mode: input length & whitespace caps reject with 422 before provider.
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("SEARCH_MAX_QUERY_CHARS", "50")
    monkeypatch.setenv("SUMMARIZE_MAX_TEXT_CHARS", "100")
    assert client.post("/search", json={"query": "   "}).status_code == 422
    assert client.post("/search", json={"query": "a" * 51}).status_code == 422
    assert client.post("/summarize", json={"text": "   "}).status_code == 422
    assert client.post("/summarize", json={"text": "x" * 101}).status_code == 422
    assert provider_calls == []


def test_rate_limit_atomic_lua_deployment_scope_and_production_fail_closed(monkeypatch):
    # 1. Atomic Redis Lua path (deployment scope)
    eval_calls = []

    class FakeRedis:
        def __init__(self):
            self.counts = {}

        def eval(self, script, numkeys, key, window):
            eval_calls.append((numkeys, key, window))
            self.counts[key] = self.counts.get(key, 0) + 1
            return [self.counts[key], window]

    fake_redis = FakeRedis()
    monkeypatch.setenv("AUTH_MODE", "production")
    d1 = rl_mod.enforce_rate_limit(bucket="search", identifier="user:alice", limit=2, window_seconds=60, redis_client=fake_redis)
    d2 = rl_mod.enforce_rate_limit(bucket="search", identifier="user:alice", limit=2, window_seconds=60, redis_client=fake_redis)
    assert d1.scope == "deployment" and d2.count == 2
    assert len(eval_calls) == 2
    with pytest.raises(rl_mod.RateLimitExceededError) as exc_info:
        rl_mod.enforce_rate_limit(bucket="search", identifier="user:alice", limit=2, window_seconds=60, redis_client=fake_redis)
    assert exc_info.value.scope == "deployment"

    # 2. Production fail-closed when Valkey is offline
    monkeypatch.setenv("AUTH_MODE", "production")
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED_IN_PRODUCTION", "true")
    with pytest.raises(rl_mod.RateLimiterUnavailableError):
        rl_mod.enforce_rate_limit(bucket="search", identifier="user:alice", limit=5, window_seconds=60)

    # 3. Development per-process fallback still enforces rate limit
    monkeypatch.setenv("AUTH_MODE", "development")
    d_dev = rl_mod.enforce_rate_limit(bucket="search", identifier="user:bob", limit=1, window_seconds=60)
    assert d_dev.scope == "per_process"
    with pytest.raises(rl_mod.RateLimitExceededError):
        rl_mod.enforce_rate_limit(bucket="search", identifier="user:bob", limit=1, window_seconds=60)


# ---------------------------------------------------------------------------
# C. Safety & Urgent Invariants under Saturation
# ---------------------------------------------------------------------------


def test_urgent_fast_path_succeeds_under_saturated_lanes_with_zero_dependencies(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")

    def forbidden(name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"{name} must NEVER be called on urgent fast path")
        return _fail

    monkeypatch.setattr(profiles, "safe_build_confirmed_context", forbidden("db_context"))
    monkeypatch.setattr(memory_store, "load_history", forbidden("load_history"))
    monkeypatch.setattr(memory_store, "create_task", forbidden("create_task"))
    monkeypatch.setattr(graph, "openai_chat_complete", forbidden("openai_chat_complete"))
    monkeypatch.setattr(graph, "vietnamese_llm_chat_complete", forbidden("vietnamese_llm"))
    monkeypatch.setattr(graph, "hybrid_search", forbidden("hybrid_search"))
    monkeypatch.setattr(graph, "rerank_documents", forbidden("rerank_documents"))
    monkeypatch.setattr(graph, "tavily_search_health", forbidden("tavily_search_health"))

    # Saturate search and chat lanes completely
    exec_mod.configure_lane("search", max_concurrency=1, max_queue=0, queue_timeout_seconds=0.5)
    exec_mod.configure_lane("chat", max_concurrency=1, max_queue=0, queue_timeout_seconds=0.5)

    hold = threading.Event()
    search_started = threading.Event()
    chat_started = threading.Event()

    def slow_search(*args, **kwargs):
        search_started.set()
        hold.wait(timeout=2.0)
        return []

    monkeypatch.setattr(api_app, "hybrid_search", slow_search)

    async def run_under_saturation():
        fake_req = SimpleNamespace(headers={}, state=SimpleNamespace(), client=SimpleNamespace(host="127.0.0.1"))
        # Occupy chat lane directly
        chat_blocker = asyncio.create_task(
            exec_mod.get_lane("chat").run(
                lambda: (chat_started.set(), hold.wait(timeout=2.0)),
                budget=RequestBudget.start(5.0),
            )
        )
        # Occupy search lane via endpoint
        search_blocker = asyncio.create_task(
            api_app.search_endpoint(api_app.SearchRequest(query="bmi", limit=3, use_rerank=False), fake_req)
        )
        for _ in range(50):
            if search_started.is_set() and chat_started.is_set():
                break
            await asyncio.sleep(0.01)

        assert exec_mod.get_lane("search").stats()["active"] == 1
        assert exec_mod.get_lane("chat").stats()["active"] == 1

        # Now forbid rate_limit & Valkey too — urgent MUST NOT touch them!
        monkeypatch.setattr(api_app, "enforce_rate_limit", forbidden("rate_limit"))

        # Fire urgent on both /agent/answer and /chat/complete while lanes are 100% saturated
        from auth.context import CurrentUser
        user = CurrentUser(subject="alice", auth_source="development_header")

        t0 = time.perf_counter()
        ans = await api_app.agent_answer(
            api_app.AgentRequest(question="Tôi đau ngực và khó thở khi tập."),
            current_user=user,
        )
        comp = await api_app.complete(
            api_app.CompleteRequest(user_message="Tôi bị đau ngực và khó thở.", sync_request=False),
            current_user=user,
        )
        urgent_ms = (time.perf_counter() - t0) * 1000.0

        assert ans["fast_path"] == "urgent_safety"
        assert ans["safety_result"]["risk_level"] == "urgent"
        assert comp["response"]["fast_path"] == "urgent_safety"
        assert urgent_ms < 100.0

        hold.set()
        await asyncio.gather(chat_blocker, search_blocker, return_exceptions=True)

    try:
        asyncio.run(run_under_saturation())
    finally:
        hold.set()


def test_greeting_and_bmi_low_risk_fast_paths_preserve_contract(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setattr(
        profiles,
        "safe_build_confirmed_context",
        lambda subject: {"available": False, "reason": "no_profile", "provenance": []},
    )
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not run on low-risk fast path")),
    )
    monkeypatch.setattr(
        graph,
        "hybrid_search",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("RAG must not run on low-risk fast path")),
    )
    client = TestClient(api_app.app)
    headers = {"X-Dev-User-Id": "phase3-fast-user"}

    greeting = client.post("/agent/answer", headers=headers, json={"question": "Xin chào"})
    assert greeting.status_code == 200
    assert greeting.json()["fast_path"] == "general_chat"

    bmi = client.post(
        "/agent/answer",
        headers=headers,
        json={"question": "Tôi nặng 72kg, cao 170cm. Tính BMI giúp tôi."},
    )
    assert bmi.status_code == 200
    assert bmi.json()["fast_path"] == "inbody_tools"
    assert bmi.json()["tool_results"][0]["result"]["bmi"] == 24.91


def test_medical_caution_preserves_recommended_action_when_budget_exhausted(monkeypatch):
    action = "Nên hỏi bác sĩ điều trị trước khi thay đổi thuốc hoặc kế hoạch tập luyện."
    state = {
        "question": "Tôi bị tiểu đường type 2, nên ăn thế nào?",
        "selected_agents": [graph.RAG_AGENT],
        "selected_capabilities": [graph.RAG_AGENT],
        "deadline_monotonic": time.monotonic() - 1.0,
        "retrieved_docs": [],
        "evidence": [],
        "tool_results": [],
        "safety_result": {
            "risk_level": "medical_caution",
            "disclaimer": "Thông tin chỉ mang tính tham khảo.",
            "recommended_action": action,
        },
        "agent_trace": [],
        "errors": [],
        "limitations": [],
    }
    monkeypatch.setattr(
        graph,
        "openai_chat_complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not run when deadline exhausted")),
    )
    out = graph.response_composer_agent(state)
    assert action in out["final_answer"]
    assert any("deadline" in err.lower() for err in out["errors"])

    # Also verify run_chat timeout before graph preserves medical_caution recommended_action.
    monkeypatch.setattr(
        profiles,
        "safe_build_confirmed_context",
        lambda subject: {
            "available": True,
            "profile": {"medical_conditions": ["tiểu đường"]},
            "provenance": [],
        },
    )
    monkeypatch.setattr(memory_store, "open_conversation", lambda *a, **k: {"conversation_id": "c-1"})
    monkeypatch.setattr(
        chat_mod,
        "multi_agent_handle",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("graph must not run when budget expired")),
    )
    chat_res = chat_mod.run_chat(
        "Tôi bị tiểu đường, nên điều chỉnh liều thuốc không?",
        "alice",
        deadline_monotonic=time.monotonic() - 1.0,
    )
    assert chat_res["status"] == "degraded"
    assert chat_res["safety_result"]["risk_level"] == "medical_caution"
    assert chat_res["safety_result"]["recommended_action"] in chat_res["content"]
