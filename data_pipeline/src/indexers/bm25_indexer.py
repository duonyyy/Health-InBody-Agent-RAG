"""Module Xuất và Đóng gói Snapshot BM25 (BM25 Snapshot Indexer).

Vai trò:
    Tạo ra file artifact nén gzip (`bm25_snapshot.json.gz`) chứa toàn bộ kho tri thức
    đã được tiền xử lý và làm giàu bối cảnh (bao gồm cả Breadcrumbs và Parent-Child metadata).
    Giúp Backend khởi động tức thì (Zero-Startup Latency), nạp trực tiếp chỉ mục BM25 vào RAM
    mà không cần tốn tài nguyên và thời gian cuộn dữ liệu (scroll overhead) từ Qdrant Vector DB.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..processors.provenance_bridge import PROVENANCE_METADATA_FIELDS

logger = logging.getLogger(__name__)

BM25_SNAPSHOT_SCHEMA_VERSION = 1


def build_bm25_documents_from_chunks(
    chunks: List[Dict[str, Any]],
    *,
    corpus_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Chuyển đổi danh sách chunks sang định dạng tài liệu chuẩn của backend BM25 engine.

    Vai trò:
        Ánh xạ các trường dữ liệu từ chunk (chunk_id, document_id, content, metadata,
        provenance, parent_id, parent_content) sang schema document mà hàm
        `initialize_search_index()` tại backend/src/rag/search.py yêu cầu.
        Bảo toàn toàn bộ thông tin khối cha (Parent) và provenance xuyên suốt tới evidence.

    Args:
        chunks: Danh sách các dictionary chunk được sinh ra từ module chunking.
        corpus_version: Phiên bản corpus (nếu có) để gắn vào từng document.

    Returns:
        Danh sách tài liệu đã được chuẩn hóa theo schema BM25.
    """
    bm25_docs: List[Dict[str, Any]] = []

    for chunk in chunks:
        chunk_meta = dict(chunk.get("metadata") or {})
        document_id = str(
            chunk.get("document_id")
            or chunk_meta.get("document_id")
            or chunk.get("doc_id")
            or chunk_meta.get("doc_id")
            or chunk.get("chunk_id")
            or ""
        )
        chunk_id = str(chunk.get("chunk_id") or chunk_meta.get("chunk_id") or document_id)
        provenance = {
            field: chunk.get(field) if field in chunk else chunk_meta.get(field)
            for field in PROVENANCE_METADATA_FIELDS
            if field in chunk or field in chunk_meta
        }
        if corpus_version and not provenance.get("corpus_version"):
            provenance["corpus_version"] = corpus_version
        provenance["document_id"] = document_id
        provenance["chunk_id"] = chunk_id
        if chunk.get("content_hash"):
            provenance["content_hash"] = chunk["content_hash"]

        merged_meta = {**chunk_meta, **provenance}
        bm25_docs.append(
            {
                **provenance,
                "doc_id": chunk_id or document_id,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "question": chunk.get("title") or "",
                "title": chunk.get("title") or "",
                "content": chunk.get("content") or "",
                "source": chunk.get("source") or "health_inbody_corpus",
                "content_type": chunk.get("content_type") or "general_health",
                "domain": chunk.get("domain") or "health_inbody",
                "parent_id": chunk.get("parent_id"),
                "parent_title": chunk.get("parent_title"),
                "parent_content": chunk.get("parent_content"),
                "has_parent": chunk.get("has_parent", False),
                "metadata": merged_meta,
            }
        )

    return bm25_docs


def export_bm25_snapshot(
    chunks: List[Dict[str, Any]],
    output_path: Path,
    collection_name: str = "nmk_chatbot_active",
    corpus_version: str = "2026.1",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    """Xây dựng và lưu trữ file snapshot BM25 nén gzip nguyên tử (atomic write).

    Vai trò:
        Gói toàn bộ tài liệu BM25 cùng metadata phiên bản vào một file nén JSON Gzip.
        Quá trình ghi sử dụng file tạm `.tmp` rồi đổi tên nguyên tử (atomic rename),
        ngăn ngừa việc backend đọc phải file lỗi khi pipeline đang ghi đè.

    Args:
        chunks: Danh sách các chunk dữ liệu hoàn chỉnh.
        output_path: Đường dẫn file đích (ví dụ: `backend/data/generated/bm25_snapshot.json.gz`).
        collection_name: Tên collection tương ứng trong Qdrant.
        corpus_version: Mã phiên bản của kho tri thức (phục vụ tracking và audit).
        extra_metadata: Siêu dữ liệu bổ sung đính kèm vào snapshot header.

    Returns:
        Dictionary báo cáo trạng thái xuất file (status, document_count, file_size_kb...).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bm25_docs = build_bm25_documents_from_chunks(chunks, corpus_version=corpus_version)
    created_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "corpus_version": corpus_version,
        "built_by": "data_pipeline",
        "chunk_count": len(chunks),
        **(extra_metadata or {}),
    }

    payload = {
        "schema_version": BM25_SNAPSHOT_SCHEMA_VERSION,
        "collection_name": collection_name,
        "created_at": created_at,
        "document_count": len(bm25_docs),
        "metadata": metadata,
        "documents": bm25_docs,
    }

    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with gzip.open(temporary_path, "wt", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
    temporary_path.replace(output_path)

    file_size_kb = output_path.stat().st_size / 1024.0
    logger.info(
        "Exported BM25 snapshot to %s: %s documents (%.1f KB)",
        output_path,
        len(bm25_docs),
        file_size_kb,
    )

    return {
        "status": "ok",
        "output_path": str(output_path),
        "document_count": len(bm25_docs),
        "collection_name": collection_name,
        "created_at": created_at,
        "file_size_kb": round(file_size_kb, 1),
    }
