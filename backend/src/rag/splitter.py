"""Tach tai lieu suc khoe/InBody thanh cac chunk cho pipeline RAG."""
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, TypedDict

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50

HEALTH_DOMAIN_KEYWORDS = {
    "inbody_metric": [
        "inbody",
        "bmi",
        "smm",
        "bfm",
        "pbf",
        "visceral fat",
        "mo noi tang",
        "mỡ nội tạng",
        "khoi luong co",
        "khối lượng cơ",
        "khoi luong mo",
        "khối lượng mỡ",
        "phan tram mo",
        "phần trăm mỡ",
    ],
    "nutrition": [
        "dinh duong",
        "dinh dưỡng",
        "calo",
        "calorie",
        "protein",
        "carb",
        "chat beo",
        "chất béo",
        "khau phan",
        "khẩu phần",
        "an uong",
        "ăn uống",
    ],
    "exercise": [
        "tap luyen",
        "tập luyện",
        "lich tap",
        "lịch tập",
        "cardio",
        "khang luc",
        "kháng lực",
        "tang co",
        "tăng cơ",
        "giam mo",
        "giảm mỡ",
        "phuc hoi",
        "phục hồi",
    ],
    "medical_safety": [
        "bac si",
        "bác sĩ",
        "trieu chung",
        "triệu chứng",
        "benh nen",
        "bệnh nền",
        "thuoc",
        "thuốc",
        "chan doan",
        "chẩn đoán",
        "cap cuu",
        "cấp cứu",
        "an toan",
        "an toàn",
    ],
}


class SplitterState(TypedDict, total=False):
    """Trang thai duoc truyen qua cac node trong LangGraph splitter."""

    text: str
    metadata: Dict[str, Any]
    chunk_size: int
    chunk_overlap: int
    normalized_text: str
    domain: str
    source_document: Document
    chunks: List[Document]


def normalize_text(text: str) -> str:
    """Chuan hoa khoang trang va xuong dong truoc khi chunking."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_health_domain(text: str) -> str:
    """Nhan dien nhom noi dung suc khoe/InBody de gan metadata cho chunk."""
    normalized = text.lower()
    for domain, keywords in HEALTH_DOMAIN_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return domain
    return "general_health"


def _normalize_node(state: SplitterState) -> SplitterState:
    return {
        **state,
        "normalized_text": normalize_text(state.get("text", "")),
    }


def _detect_domain_node(state: SplitterState) -> SplitterState:
    metadata = dict(state.get("metadata") or {})
    domain = metadata.get("content_type") or detect_health_domain(
        state.get("normalized_text", "")
    )
    metadata.update({"content_type": domain, "domain": "health_inbody"})
    return {**state, "metadata": metadata, "domain": domain}


def _build_document_node(state: SplitterState) -> SplitterState:
    metadata = dict(state.get("metadata") or {})
    source_document = Document(
        page_content=state.get("normalized_text", ""),
        metadata=metadata,
    )
    return {**state, "source_document": source_document}


def _split_node(state: SplitterState) -> SplitterState:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=state.get("chunk_size", DEFAULT_CHUNK_SIZE),
        chunk_overlap=state.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP),
        separators=[
            "\n## ",
            "\n### ",
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )
    chunks = splitter.split_documents([state["source_document"]])
    return {**state, "chunks": chunks}


def _enrich_chunks_node(state: SplitterState) -> SplitterState:
    chunks = []
    for index, chunk in enumerate(state.get("chunks", []), start=1):
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "chunk_index": index,
                "chunk_count": len(state.get("chunks", [])),
                "chunk_length": len(chunk.page_content),
                "content_type": state.get("domain", "general_health"),
                "domain": "health_inbody",
            }
        )
        chunks.append(Document(page_content=chunk.page_content, metadata=metadata))
    return {**state, "chunks": chunks}


@lru_cache(maxsize=1)
def build_splitter_graph():
    """
    Tao LangGraph dieu phoi cac buoc tach chunk.

    Graph giup pipeline ro rang hon: chuan hoa text, nhan dien domain, tao
    LangChain Document, tach chunk va gan metadata phuc vu retrieval.
    """
    graph = StateGraph(SplitterState)
    graph.add_node("normalize_text", _normalize_node)
    graph.add_node("detect_domain", _detect_domain_node)
    graph.add_node("build_document", _build_document_node)
    graph.add_node("split_document", _split_node)
    graph.add_node("enrich_chunks", _enrich_chunks_node)

    graph.set_entry_point("normalize_text")
    graph.add_edge("normalize_text", "detect_domain")
    graph.add_edge("detect_domain", "build_document")
    graph.add_edge("build_document", "split_document")
    graph.add_edge("split_document", "enrich_chunks")
    graph.add_edge("enrich_chunks", END)

    return graph.compile()


def split_document(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    Tach tai lieu suc khoe/InBody thanh cac LangChain Document chunks.

    Args:
        text: Noi dung tai lieu can tach.
        metadata: Metadata nguon, vi du source_file, user_id, document_type.
        chunk_size: Kich thuoc toi da moi chunk.
        chunk_overlap: So ky tu overlap giua cac chunk lien tiep.

    Returns:
        Danh sach LangChain Document, moi chunk da co metadata ve domain,
        content_type, chunk_index va chunk_length.
    """
    if not text or not text.strip():
        logger.info("No text provided for chunking")
        return []

    splitter_graph = build_splitter_graph()
    result = splitter_graph.invoke(
        {
            "text": text,
            "metadata": dict(metadata or {}),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
    )

    chunks = result.get("chunks", [])
    logger.info(
        "Split health/InBody document into %s chunks with content_type=%s",
        len(chunks),
        result.get("domain", "general_health"),
    )
    return chunks
