"""Corpus management and document indexing endpoints."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.common import (
    DEFAULT_INDEX_MAX_BATCH_CHARS,
    DEFAULT_INDEX_MAX_BATCH_DOCS,
    _check_rate_limit_async,
    _env_int,
    _indexing_timeout_seconds,
    _raise_lane_http_error,
    get_app_dep,
)
from api.schemas import CollectionCreateRequest, DocumentCreateRequest, DocumentsIndexRequest
from auth.context import CurrentUser, require_corpus_admin
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from harness.budget import BudgetExhaustedError, RequestBudget, call_with_supported_kwargs
from jobs.tasks import index_document_v2, index_health_documents
from rag.corpus_policy import require_staging_collection, validate_shared_document

logger = logging.getLogger(__name__)
router = APIRouter(tags=["corpus"])


def _receipt_indicates_failure(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return True
    if int(result.get("failed_points") or 0) > 0:
        return True
    if int(result.get("failed_documents") or 0) > 0:
        return True
    if int(result.get("unconfirmed_points") or 0) > 0:
        return True
    if result.get("errors"):
        return True
    return False


def _validate_index_batch_limits(documents: list) -> None:
    max_docs = _env_int("INDEX_MAX_BATCH_DOCS", DEFAULT_INDEX_MAX_BATCH_DOCS, minimum=1, maximum=100)
    if len(documents) > max_docs:
        raise HTTPException(
            status_code=422,
            detail=f"Số tài liệu trong một lô vượt quá giới hạn ({max_docs}).",
        )
    max_chars = _env_int("INDEX_MAX_BATCH_CHARS", DEFAULT_INDEX_MAX_BATCH_CHARS, minimum=1000, maximum=2000000)
    total_chars = sum(
        len(str(doc.get("content") or doc.get("page_content") or ""))
        + len(str(doc.get("question") or doc.get("title") or ""))
        for doc in documents
        if isinstance(doc, dict)
    )
    if total_chars > max_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Tổng dung lượng văn bản trong lô vượt quá giới hạn ({max_chars} ký tự).",
        )


def _validate_corpus_admission(
    collection_name: str,
    documents: list,
    *,
    corpus_version: Optional[str] = None,
) -> None:
    from rag.corpus_lifecycle import (
        CorpusAdmissionError,
        CorpusTopologyUnavailableError,
        verify_staging_write_target,
    )
    from rag.qdrant.client import client as qdrant_client

    try:
        # 1. Check document privacy/public scope first (pure offline).
        for document in documents:
            validate_shared_document(document, require_review=True)
        # 2. Check static allowlist + serving aliases + live Qdrant alias target (fail-closed).
        require_staging_collection(collection_name)
        verify_staging_write_target(
            collection_name,
            qdrant_client=qdrant_client,
            corpus_version=corpus_version,
            require_corpus_version=False,
            require_allowlist=True,
            dry_run=False,
        )
    except (CorpusAdmissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CorpusTopologyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _validate_corpus_admission_async(
    collection_name: str,
    documents: list,
    *,
    corpus_version: Optional[str] = None,
    budget: Optional[RequestBudget] = None,
) -> None:
    """Offload live Qdrant topology verification onto the probe lane so event loop stays free."""
    try:
        await get_lane("probe").run(
            _validate_corpus_admission,
            collection_name,
            documents,
            corpus_version=corpus_version,
            budget=budget,
            pass_cancel_event=False,
        )
    except HTTPException:
        raise
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)


@router.post("/collection/create")
async def create_vector_collection(data: CollectionCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("indexing", f"admin:{admin.subject}", index_limit, budget)
    await _validate_corpus_admission_async(data.collection_name, [], budget=budget)
    try:
        from rag.corpus_lifecycle import CorpusAdmissionError, CorpusLockError, CorpusTopologyUnavailableError
        from rag.qdrant.client import create_collection

        create_status = await get_lane("indexing").run(
            create_collection,
            data.collection_name,
            data.vector_size,
            require_allowlist=True,
            budget=budget,
            pass_cancel_event=False,
        )
        if not create_status:
            return JSONResponse(
                status_code=502,
                content={"status": False, "detail": "Qdrant không xác nhận tạo collection."},
            )
        return {"status": True, "collection_name": data.collection_name, "result": str(create_status)}
    except HTTPException:
        raise
    except CorpusAdmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CorpusLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CorpusTopologyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create collection failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể tạo collection lúc này.")


@router.post("/document/create")
async def create_document(data: DocumentCreateRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("indexing", f"admin:{admin.subject}", index_limit, budget)
    await _validate_corpus_admission_async(
        data.collection_name,
        [data.model_dump()],
        corpus_version=data.corpus_version,
        budget=budget,
    )
    try:
        from rag.corpus_lifecycle import (
            CorpusAdmissionError,
            CorpusLockError,
            CorpusTopologyUnavailableError,
            CorpusWriteValidationError,
            QdrantWriteError,
        )

        index_fn = get_app_dep("index_document_v2", index_document_v2)
        index_status = await get_lane("indexing").run(
            index_fn,
            data.id,
            data.question,
            data.content,
            collection_name=data.collection_name,
            metadata=data.metadata,
            corpus_version=data.corpus_version,
            require_allowlist=True,
            budget=budget,
            pass_cancel_event=False,
        )
        if _receipt_indicates_failure(index_status):
            return JSONResponse(
                status_code=502,
                content={
                    "status": False,
                    "detail": "Ghi tài liệu vào Qdrant thất bại hoặc chưa được xác nhận hoàn tất.",
                    "index_status": index_status,
                },
            )
        return {"status": True, "index_status": index_status}
    except HTTPException:
        raise
    except (CorpusAdmissionError, CorpusWriteValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CorpusLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CorpusTopologyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QdrantWriteError as exc:
        return JSONResponse(
            status_code=502,
            content={"status": False, "detail": str(exc), "index_status": exc.receipt},
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create/index document failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể lập chỉ mục tài liệu lúc này.")


@router.post("/documents/index")
async def index_documents(data: DocumentsIndexRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_index_batch_limits(data.documents)
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("indexing", f"admin:{admin.subject}", index_limit, budget)
    await _validate_corpus_admission_async(
        data.collection_name,
        data.documents,
        corpus_version=data.corpus_version,
        budget=budget,
    )
    try:
        from rag.corpus_lifecycle import (
            CorpusAdmissionError,
            CorpusLockError,
            CorpusTopologyUnavailableError,
            CorpusWriteValidationError,
            QdrantWriteError,
        )

        index_fn = get_app_dep("index_health_documents", index_health_documents)
        result = await get_lane("indexing").run(
            call_with_supported_kwargs,
            index_fn,
            data.documents,
            collection_name=data.collection_name,
            corpus_version=data.corpus_version,
            require_allowlist=True,
            budget=budget,
            pass_cancel_event=False,
        )
        if _receipt_indicates_failure(result):
            return JSONResponse(
                status_code=502,
                content={
                    "status": False,
                    "detail": "Lập chỉ mục lô tài liệu gặp lỗi hoặc mới ghi được một phần.",
                    "result": result,
                },
            )
        return {"status": True, "result": result}
    except HTTPException:
        raise
    except (CorpusAdmissionError, CorpusWriteValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CorpusLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CorpusTopologyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QdrantWriteError as exc:
        return JSONResponse(
            status_code=502,
            content={"status": False, "detail": str(exc), "result": exc.receipt},
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Batch index failed (%s)", type(e).__name__)
        raise HTTPException(status_code=503, detail="Không thể lập chỉ mục lô tài liệu lúc này.")


@router.post("/data/import")
async def import_data_endpoint(data: DocumentsIndexRequest, admin: CurrentUser = Depends(require_corpus_admin)):
    _validate_index_batch_limits(data.documents)
    budget = RequestBudget.start(_indexing_timeout_seconds(), max_timeout_seconds=55.0)
    index_limit = _env_int("INDEXING_RATE_LIMIT_PER_MINUTE", 10, minimum=0, maximum=200)
    check_rate_limit = get_app_dep("_check_rate_limit_async", _check_rate_limit_async)
    await check_rate_limit("indexing", f"admin:{admin.subject}", index_limit, budget)
    await _validate_corpus_admission_async(
        data.collection_name,
        data.documents,
        corpus_version=data.corpus_version,
        budget=budget,
    )
    try:
        from rag.corpus_lifecycle import (
            CorpusAdmissionError,
            CorpusLockError,
            CorpusTopologyUnavailableError,
            CorpusWriteValidationError,
            QdrantWriteError,
        )

        index_fn = get_app_dep("index_health_documents", index_health_documents)
        result = await get_lane("indexing").run(
            call_with_supported_kwargs,
            index_fn,
            data.documents,
            collection_name=data.collection_name,
            corpus_version=data.corpus_version,
            require_allowlist=True,
            budget=budget,
            pass_cancel_event=False,
        )
        if _receipt_indicates_failure(result):
            return JSONResponse(
                status_code=502,
                content={
                    "success": False,
                    "status": False,
                    "detail": "Nhập dữ liệu vào Qdrant thất bại hoặc mới ghi được một phần.",
                    "result": result,
                },
            )
        return {"success": True, "status": True, "result": result}
    except HTTPException:
        raise
    except (CorpusAdmissionError, CorpusWriteValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CorpusLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CorpusTopologyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QdrantWriteError as exc:
        return JSONResponse(
            status_code=502,
            content={"success": False, "status": False, "detail": str(exc), "result": exc.receipt},
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as exc:
        logger.error("Data import failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể nhập dữ liệu lúc này.") from exc
