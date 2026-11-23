"""Dependency injection protocols and container for Agent RAG orchestrator.

Design principles (python-design-patterns):
- Pattern 7 (Dependency Injection): Pass dependencies explicitly for testability.
- Interfaces over implementation: Use typing.Protocol for external callable boundaries.
- Single Responsibility: Decouple agent nodes from global module imports and monkey-patching.
"""
from dataclasses import dataclass
import sys
from typing import Any, Callable, Dict, List, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class ChatCompleteCallable(Protocol):
    """Protocol for LLM chat completion functions."""
    def __call__(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 1000,
        timeout: Optional[float] = None,
        deadline_monotonic: Optional[float] = None,
        raise_on_timeout: bool = False,
        **kwargs: Any,
    ) -> Optional[str]: ...


@runtime_checkable
class SearchCallable(Protocol):
    """Protocol for vector / BM25 / hybrid retrieval functions."""
    def __call__(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_rerank: bool = True,
        embedding_timeout: Optional[float] = None,
        expand_parents: Optional[bool] = None,
        timeout: Optional[float] = None,
        deadline_monotonic: Optional[float] = None,
        raise_on_timeout: bool = False,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]: ...


@runtime_checkable
class RewriteQueryCallable(Protocol):
    """Protocol for query rewrite multi-query generation."""
    def __call__(
        self,
        query: str,
        max_queries: int = 3,
        timeout: Optional[float] = None,
        deadline_monotonic: Optional[float] = None,
        raise_on_timeout: bool = False,
        **kwargs: Any,
    ) -> List[str]: ...


@runtime_checkable
class RerankDocumentsCallable(Protocol):
    """Protocol for document cross-encoder reranking."""
    def __call__(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        top_n: Optional[int] = None,
        timeout: Optional[float] = None,
        deadline_monotonic: Optional[float] = None,
        raise_on_timeout: bool = False,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]: ...


@runtime_checkable
class WebSearchCallable(Protocol):
    """Protocol for health web search."""
    def __call__(
        self,
        query: str,
        max_results: int = 5,
        timeout: Optional[float] = None,
        deadline_monotonic: Optional[float] = None,
        **kwargs: Any,
    ) -> Optional[str]: ...


@runtime_checkable
class MedicalSafetyCallable(Protocol):
    """Protocol for medical safety pre-check."""
    def __call__(
        self,
        question: str,
        medical_conditions: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]: ...


@runtime_checkable
class AnswerMemoryCallable(Protocol):
    """Protocol for memory profile lookups."""
    def __call__(
        self,
        question: str,
        personalization_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[str]: ...


@dataclass
class AgentDependencies:
    """Explicit container for all external service dependencies of the Agent graph."""
    openai_chat_fn: Optional[Callable[..., Optional[str]]] = None
    vietnamese_llm_fn: Optional[Callable[..., Optional[str]]] = None
    search_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None
    rewrite_fn: Optional[Callable[..., List[str]]] = None
    rerank_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None
    tavily_fn: Optional[Callable[..., Optional[str]]] = None
    medical_safety_fn: Optional[Callable[..., Dict[str, Any]]] = None
    answer_memory_fn: Optional[Callable[..., Optional[str]]] = None

    def clone_with(self, **overrides: Any) -> "AgentDependencies":
        """Return a copy with specific dependency overrides."""
        data = {
            "openai_chat_fn": self.openai_chat_fn,
            "vietnamese_llm_fn": self.vietnamese_llm_fn,
            "search_fn": self.search_fn,
            "rewrite_fn": self.rewrite_fn,
            "rerank_fn": self.rerank_fn,
            "tavily_fn": self.tavily_fn,
            "medical_safety_fn": self.medical_safety_fn,
            "answer_memory_fn": self.answer_memory_fn,
        }
        data.update(overrides)
        return AgentDependencies(**data)


def resolve_agent_dependencies(state: Optional[Dict[str, Any]] = None) -> AgentDependencies:
    """Resolve active dependencies with cascading priority:

    1. Explicit dependencies container from state['dependencies'] (Highest priority).
    2. Test monkeypatch on 'agents.graph' module (for 100% backward compatibility).
    3. Production default implementations (Lowest priority).
    """
    injected = (state or {}).get("dependencies")
    if isinstance(injected, AgentDependencies):
        base = injected
    elif isinstance(injected, dict):
        base = AgentDependencies(**injected)
    else:
        base = AgentDependencies()

    graph_mod = sys.modules.get("agents.graph")

    def _resolve(field_name: str, graph_attr_name: str, default_loader: Callable[[], Any]) -> Any:
        injected_val = getattr(base, field_name, None)
        if injected_val is not None:
            return injected_val
        if graph_mod is not None:
            patched_val = getattr(graph_mod, graph_attr_name, None)
            if patched_val is not None:
                return patched_val
        return default_loader()

    def _get_default_openai_chat():
        from llm.client import openai_chat_complete
        return openai_chat_complete

    def _get_default_vietnamese_llm():
        from llm.client import vietnamese_llm_chat_complete
        return vietnamese_llm_chat_complete

    def _get_default_search():
        from rag.search import hybrid_search
        return hybrid_search

    def _get_default_rewrite():
        from rag.query_rewriter import rewrite_query_to_multi_queries
        return rewrite_query_to_multi_queries

    def _get_default_rerank():
        from rag.rerank import rerank_documents
        return rerank_documents

    def _get_default_tavily():
        from integrations.tavily import tavily_search_health
        return tavily_search_health

    def _get_default_safety():
        from health.tools import check_medical_safety
        return check_medical_safety

    def _get_default_memory():
        from memory.context import answer_memory_question
        return answer_memory_question

    return AgentDependencies(
        openai_chat_fn=_resolve("openai_chat_fn", "openai_chat_complete", _get_default_openai_chat),
        vietnamese_llm_fn=_resolve("vietnamese_llm_fn", "vietnamese_llm_chat_complete", _get_default_vietnamese_llm),
        search_fn=_resolve("search_fn", "hybrid_search", _get_default_search),
        rewrite_fn=_resolve("rewrite_fn", "rewrite_query_to_multi_queries", _get_default_rewrite),
        rerank_fn=_resolve("rerank_fn", "rerank_documents", _get_default_rerank),
        tavily_fn=_resolve("tavily_fn", "tavily_search_health", _get_default_tavily),
        medical_safety_fn=_resolve("medical_safety_fn", "check_medical_safety", _get_default_safety),
        answer_memory_fn=_resolve("answer_memory_fn", "answer_memory_question", _get_default_memory),
    )
