"""Phase 4 regression tests for R06 (staging admission & locks), R12 (honest write receipts),
and R13 (release manifest, BM25/Qdrant sync, request pinning, cache binding, worker guard).

Tests in this module use deterministic fakes/mocks to inject errors, partial writes,
Qdrant UpdateStatus edge cases, and race conditions without touching any real Qdrant server.
"""

from __future__ import annotations

import gzip
import json
import math
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from qdrant_client.models import UpdateResult, UpdateStatus

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents import composer, graph
from core.response_cache import build_llm_response_cache_key
from jobs import tasks
from pipelines import import_data
from rag import corpus_lifecycle as lc
from rag import search
from rag.qdrant import client as qdrant_mod
from rag.qdrant import collection_admin


class _FakeAliasesQdrant:
    """Fake Qdrant client with configurable aliases, points, and batch failure injection."""

    def __init__(
        self,
        *,
        aliases: dict[str, str] | None = None,
        fail_aliases: bool = False,
        upsert_outcomes: list | None = None,
        points_by_collection: dict[str, list] | None = None,
        vector_size: int = 4,
    ):
        self.aliases = dict(aliases or {"nmk_chatbot_active": "prod_col_v1"})
        self.fail_aliases = fail_aliases
        self.upsert_outcomes = list(upsert_outcomes or [])
        self.points_by_collection = {
            k: list(v) for k, v in (points_by_collection or {}).items()
        }
        self.vector_size = vector_size
        self.upsert_calls: list[dict] = []
        self.create_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.alias_updates: list = []

    def get_aliases(self):
        if self.fail_aliases:
            raise ConnectionError("Qdrant unreachable")
        items = [
            SimpleNamespace(alias_name=alias, collection_name=target)
            for alias, target in self.aliases.items()
        ]
        return SimpleNamespace(aliases=items)

    def get_collections(self):
        names = set(self.points_by_collection.keys()) | set(self.aliases.values())
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in sorted(names)])

    def get_collection(self, collection_name: str):
        pts = self.points_by_collection.get(collection_name, [])
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self.vector_size))
            ),
            points_count=len(pts),
            vectors_count=len(pts),
            indexed_vectors_count=len(pts),
            status="green",
            optimizer_status="ok",
            payload_schema={"content_type": {}, "document_id": {}, "corpus_version": {}, "content_hash": {}},
        )

    def create_collection(self, collection_name: str, **kwargs):
        self.create_calls.append(collection_name)
        self.points_by_collection.setdefault(collection_name, [])
        return True

    def create_payload_index(self, **kwargs):
        return UpdateResult(operation_id=1, status=UpdateStatus.COMPLETED)

    def upsert(self, collection_name: str, points, wait: bool = True):
        self.upsert_calls.append(
            {"collection_name": collection_name, "count": len(points), "wait": wait}
        )
        if self.upsert_outcomes:
            outcome = self.upsert_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, UpdateResult) and outcome.status == UpdateStatus.COMPLETED:
                self.points_by_collection.setdefault(collection_name, []).extend(points)
            return outcome
        self.points_by_collection.setdefault(collection_name, []).extend(points)
        return UpdateResult(operation_id=len(self.upsert_calls), status=UpdateStatus.COMPLETED)

    def scroll(self, collection_name: str, limit: int = 100, offset=None, **kwargs):
        pts = self.points_by_collection.get(collection_name, [])
        return pts, None

    def delete(self, collection_name: str, points_selector, wait: bool = True):
        self.delete_calls.append(collection_name)
        return UpdateResult(operation_id=1, status=UpdateStatus.COMPLETED)

    def update_collection_aliases(self, change_aliases_operations):
        self.alias_updates.append(change_aliases_operations)
        return True


def _sample_jsonl(tmp_path: Path, docs: list[dict]) -> Path:
    path = tmp_path / "corpus.jsonl"
    path.write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n",
        encoding="utf-8",
    )
    return path


def _doc(doc_id: str, content: str | None = None, content_type: str = "inbody_metric") -> dict:
    return {
        "doc_id": doc_id,
        "document_id": doc_id,
        "title": f"Tài liệu {doc_id}",
        "content": content
        or f"Nội dung chuẩn hóa về chỉ số InBody và sức khỏe cho tài liệu {doc_id} đủ độ dài tối thiểu.",
        "source": "synthetic_test",
        "content_type": content_type,
        "domain": "health_inbody",
        "language": "vi",
        "metadata": {"source_url": "https://example.test/health"},
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. R06 — STAGING ADMISSION, TOPOLOGY FAIL-CLOSED, ALLOWLIST & LOCKING
# ─────────────────────────────────────────────────────────────────────────────


def test_r06_serving_alias_and_physical_target_blocked_even_if_allowlisted(monkeypatch):
    fake_qdrant = _FakeAliasesQdrant(aliases={"nmk_chatbot_active": "prod_col_v1"})
    monkeypatch.setenv("CORPUS_STAGING_COLLECTIONS", "nmk_chatbot_active,prod_col_v1,staging_v2")
    monkeypatch.setenv("QDRANT_COLLECTION_ALIAS", "nmk_chatbot_active")

    # 1. Serving alias blocked even though it is in CORPUS_STAGING_COLLECTIONS.
    with pytest.raises(lc.CorpusAdmissionError):
        lc.verify_staging_write_target(
            "nmk_chatbot_active",
            qdrant_client=fake_qdrant,
            corpus_version="2026-11-18-v2",
            require_allowlist=True,
        )

    # 2. Actual physical target of serving alias blocked EVEN THOUGH it is in allowlist!
    with pytest.raises(lc.CorpusAdmissionError, match="actual alias target"):
        lc.verify_staging_write_target(
            "prod_col_v1",
            qdrant_client=fake_qdrant,
            corpus_version="2026-11-18-v2",
            require_allowlist=True,
        )

    # 3. Real staging physical collection is admitted.
    ok = lc.verify_staging_write_target(
        "staging_v2",
        qdrant_client=fake_qdrant,
        corpus_version="2026-11-18-v2",
        require_allowlist=True,
    )
    assert ok["admitted"] is True
    assert ok["topology_verified"] is True


def test_r06_topology_unverifiable_fails_closed_before_embed_or_write(monkeypatch, tmp_path):
    broken_qdrant = _FakeAliasesQdrant(fail_aliases=True)
    embed_called = []
    monkeypatch.setattr(import_data, "get_embedding_safe", lambda texts: embed_called.append(texts) or [[0.1] * 4])

    data_file = _sample_jsonl(tmp_path, [_doc("d1")])
    with pytest.raises(lc.CorpusTopologyUnavailableError):
        import_data.import_embedding_dataset(
            data_file_path=data_file,
            collection_name="staging_v2",
            corpus_version="2026-11-18-v2",
            vector_size=4,
            qdrant_client=broken_qdrant,
            lock_dir=tmp_path / "locks",
        )

    assert embed_called == []
    assert broken_qdrant.create_calls == []
    assert broken_qdrant.upsert_calls == []


def test_r06_all_writers_reject_serving_alias_and_physical_target_before_embed(monkeypatch, tmp_path):
    from data_pipeline.src.indexers.qdrant_indexer import QdrantIndexer

    fake_qdrant = _FakeAliasesQdrant(aliases={"nmk_chatbot_active": "prod_col_v1"})
    data_file = _sample_jsonl(tmp_path, [_doc("d1")])
    embed_calls = []

    monkeypatch.setattr(import_data, "get_embedding_safe", lambda texts: embed_calls.append("import") or [[0.1] * 4])
    monkeypatch.setattr(tasks, "get_embedding", lambda text: embed_calls.append("tasks") or [0.1] * 4)

    for forbidden_target in ("nmk_chatbot_active", "prod_col_v1"):
        # CLI import_data
        with pytest.raises(lc.CorpusAdmissionError):
            import_data.import_embedding_dataset(
                data_file_path=data_file,
                collection_name=forbidden_target,
                corpus_version="2026-11-18-v2",
                vector_size=4,
                qdrant_client=fake_qdrant,
                lock_dir=tmp_path / "locks",
            )
        # Celery / API task index_health_documents
        with pytest.raises(lc.CorpusAdmissionError):
            tasks.index_health_documents(
                [_doc("d1")],
                collection_name=forbidden_target,
                corpus_version="2026-11-18-v2",
                qdrant_client=fake_qdrant,
                lock_dir=str(tmp_path / "locks"),
            )
        # data_pipeline QdrantIndexer
        indexer = QdrantIndexer(vector_size=4, lock_dir=tmp_path / "locks")
        indexer._client = fake_qdrant
        fake_embedder = SimpleNamespace(embed_texts=lambda texts, dry_run=False: embed_calls.append("dp") or [[0.1] * 4])
        with pytest.raises(lc.CorpusAdmissionError):
            indexer.index_chunks(
                chunks=[{"chunk_id": "d1-1", "doc_id": "d1", "content": "Nội dung kiểm thử dài hơn 40 ký tự cho pipeline.", "content_hash": "a" * 64}],
                embedder=fake_embedder,
                collection_name=forbidden_target,
                corpus_version="2026-11-18-v2",
                dry_run=False,
            )
        # Low-level qdrant create_collection & delete_vectors
        with pytest.raises(lc.CorpusAdmissionError):
            qdrant_mod.create_collection(forbidden_target, vector_size=4, qdrant_client=fake_qdrant)
        with pytest.raises(lc.CorpusAdmissionError):
            qdrant_mod.delete_vectors(forbidden_target, ["00000000-0000-0000-0000-000000000001"], qdrant_client=fake_qdrant)

    assert embed_calls == []
    assert fake_qdrant.upsert_calls == []
    assert fake_qdrant.create_calls == []
    assert fake_qdrant.delete_calls == []


def test_r06_write_lease_blocks_activation_and_mid_import_activation_halts_next_batch(tmp_path):
    fake_qdrant = _FakeAliasesQdrant(aliases={"nmk_chatbot_active": "prod_col_v1"})
    manager = lc.CorpusLeaseManager(lock_dir=tmp_path / "locks")

    lease = manager.acquire_write_lease(
        "staging_v2",
        qdrant_client=fake_qdrant,
        corpus_version="2026-11-18-v2",
        release_id="rel-v2",
    )
    try:
        # 1. Activation MUST be refused while import holds write lease.
        with pytest.raises(lc.CorpusLockError, match="write lease"):
            qdrant_mod.activate_collection_alias(
                "staging_v2",
                "nmk_chatbot_active",
                expected_points=0,
                lease_manager=manager,
                qdrant_client=fake_qdrant,
            )

        # 2. Second concurrent writer is also refused.
        with pytest.raises(lc.CorpusLockError):
            manager.acquire_write_lease(
                "staging_v2",
                qdrant_client=fake_qdrant,
                corpus_version="2026-11-18-v2",
            )

        # 3. If an external actor activates staging_v2 mid-import, per-batch renewal MUST abort!
        fake_qdrant.aliases["nmk_chatbot_active"] = "staging_v2"
        with pytest.raises(lc.CorpusAdmissionError, match="đang được phục vụ"):
            manager.verify_and_renew_write_lease(lease, qdrant_client=fake_qdrant)
    finally:
        manager.release_lease(lease)


# ─────────────────────────────────────────────────────────────────────────────
# 2. R12 — HONEST WRITE RECEIPTS, PARTIAL FAILURE, VECTOR VALIDATION & HTTP 502
# ─────────────────────────────────────────────────────────────────────────────


def test_r12_partial_batch_failure_preserves_batch1_receipt_and_never_claims_success(tmp_path):
    fake_qdrant = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        upsert_outcomes=[
            UpdateResult(operation_id=1, status=UpdateStatus.COMPLETED),
            RuntimeError("disk full on batch 2"),
        ],
    )
    vectors = {
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"c-{i}")): {
            "vector": [0.1, 0.2, 0.3, 0.4],
            "payload": {
                "doc_id": f"d-{i}",
                "document_id": f"d-{i}",
                "chunk_id": f"c-{i}",
                "content": "Nội dung sức khỏe hợp lệ để ghi vào Qdrant.",
                "content_hash": f"{i:064x}",
                "corpus_version": "2026-11-18-v2",
            },
        }
        for i in range(4)
    }

    receipt = qdrant_mod.add_vector(
        "staging_v2",
        vectors=vectors,
        batch_size=2,
        raise_on_error=False,
        expected_vector_size=4,
        corpus_version="2026-11-18-v2",
        qdrant_client=fake_qdrant,
    )

    assert receipt["ok"] is False
    assert receipt["status"] == "partial"
    assert receipt["attempted_points"] == 4
    assert receipt["committed_points"] == 2
    assert receipt["failed_points"] == 2
    assert receipt["partial_write"] is True
    assert receipt["rollback_performed"] is False
    assert len(receipt["errors"]) == 1


@pytest.mark.parametrize(
    "status_enum,expected_state",
    [
        (UpdateStatus.WAIT_TIMEOUT, "failed"),
        (UpdateStatus.ACKNOWLEDGED, "incomplete"),
    ],
)
def test_r12_qdrant_wait_timeout_and_acknowledged_not_counted_as_committed(status_enum, expected_state):
    fake_qdrant = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        upsert_outcomes=[UpdateResult(operation_id=9, status=status_enum)],
    )
    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, "c-status"))
    vectors = {
        pid: {
            "vector": [0.1, 0.2, 0.3, 0.4],
            "payload": {"content": "Nội dung hợp lệ", "corpus_version": "2026-11-18-v2"},
        }
    }

    receipt = qdrant_mod.add_vector(
        "staging_v2",
        vectors=vectors,
        batch_size=1,
        raise_on_error=False,
        expected_vector_size=4,
        corpus_version="2026-11-18-v2",
        qdrant_client=fake_qdrant,
    )

    assert receipt["ok"] is False
    assert receipt["committed_points"] == 0
    assert receipt["status"] == expected_state


def test_r12_pre_upsert_blocks_missing_embeddings_wrong_dim_and_nan_inf():
    # 1. Missing embedding (zip must NEVER silently drop tail chunk).
    with pytest.raises(lc.CorpusWriteValidationError, match="không khớp"):
        lc.validate_embeddings_alignment(["a", "b", "c"], [[0.1, 0.2], [0.3, 0.4]], expected_vector_size=2)

    # 2. Wrong dimension.
    with pytest.raises(lc.CorpusWriteValidationError, match="kích thước vector"):
        lc.validate_embeddings_alignment(["a"], [[0.1, 0.2, 0.3]], expected_vector_size=4)

    # 3. NaN / Inf / -Inf.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(lc.CorpusWriteValidationError, match="không hữu hạn"):
            lc.validate_vector_values([0.1, bad, 0.2, 0.3], expected_vector_size=4, point_id="p1")


def test_r12_api_indexing_returns_http_502_on_writer_failure_and_never_200_true(monkeypatch, tmp_path):
    import importlib
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    from fastapi.testclient import TestClient
    from auth.context import CurrentUser, get_current_user

    api = importlib.import_module("api.app")
    fake_qdrant = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        upsert_outcomes=[
            RuntimeError("Qdrant write exploded on /documents/index"),
            RuntimeError("Qdrant write exploded on /data/import"),
        ],
    )
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ENABLE_CORPUS_ADMIN_API", "true")
    monkeypatch.setenv("CORPUS_STAGING_COLLECTIONS", "staging_v2")
    monkeypatch.setenv("CORPUS_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(qdrant_mod, "client", fake_qdrant)
    monkeypatch.setattr(tasks, "get_embedding", lambda text: [0.1, 0.2, 0.3, 0.4])

    doc = {
        "doc_id": "d-fail-1",
        "title": "Test",
        "content": "Nội dung kiến thức chung về BMI đủ dài để tách chunk và kiểm tra lỗi ghi.",
        "data_scope": "shared_knowledge",
        "privacy_review_status": "approved",
        "source_url": "https://example.org/bmi",
    }
    client = TestClient(api.app)
    api.app.dependency_overrides[get_current_user] = lambda: CurrentUser("admin", scopes=("corpus:write",))
    try:
        resp_index = client.post(
            "/documents/index",
            json={"collection_name": "staging_v2", "documents": [doc]},
        )
        assert resp_index.status_code == 502
        assert len(fake_qdrant.upsert_calls) == 1
        body = resp_index.json()
        assert body["status"] is False
        assert body["result"]["ok"] is False
        assert body["result"]["indexed"] == 0
        assert body["result"]["failed_documents"] == 1

        resp_import = client.post(
            "/data/import",
            json={"collection_name": "staging_v2", "documents": [doc]},
        )
        assert resp_import.status_code == 502
        assert resp_import.json()["success"] is False

        # Verify CLI import_data exits non-zero when writer fails.
        data_file = _sample_jsonl(tmp_path, [_doc("d1")])
        monkeypatch.setattr(import_data, "get_embedding_safe", lambda texts: [[0.1, 0.2, 0.3, 0.4] for _ in texts])
        exit_code = import_data.main(
            [
                "--data-file", str(data_file),
                "--collection", "nmk_chatbot_active",
                "--corpus-version", "2026-11-18-v2",
                "--vector-size", "4",
                "--lock-dir", str(tmp_path / "locks"),
            ]
        )
        assert exit_code != 0
    finally:
        api.app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# 3. RESUME CONFLICTS, CHECKPOINT COMPATIBILITY & VECTOR REUSE FINGERPRINT
# ─────────────────────────────────────────────────────────────────────────────


def test_resume_rejects_same_id_with_different_content_hash_and_version(monkeypatch, tmp_path):
    doc = _doc("doc-conflict-1", "Nội dung phiên bản mới đã thay đổi so với lần ghi trước đây.")
    data_file = _sample_jsonl(tmp_path, [doc])
    payloads, _ = import_data.build_chunk_payloads(
        doc, line_number=1, chunk_size=512, chunk_overlap=50, corpus_version="2026-11-18-v2"
    )
    point_id, payload = next(iter(payloads.items()))

    fake_qdrant = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        points_by_collection={
            "staging_v2": [
                SimpleNamespace(
                    id=point_id,
                    payload={
                        "doc_id": "doc-conflict-1",
                        "document_id": "doc-conflict-1",
                        "chunk_id": payload["chunk_id"],
                        "content_hash": "0" * 64,  # DIFFERENT content hash!
                        "corpus_version": "2026-11-18-v2",
                    },
                )
            ]
        },
    )
    monkeypatch.setattr(import_data, "get_embedding_safe", lambda texts: [[0.1] * 4 for _ in texts])

    res = import_data.import_embedding_dataset(
        data_file_path=data_file,
        collection_name="staging_v2",
        corpus_version="2026-11-18-v2",
        vector_size=4,
        skip_collection_create=True,
        skip_existing_points=True,
        qdrant_client=fake_qdrant,
        lock_dir=tmp_path / "locks",
    )

    assert res["status"] is False
    assert res["conflict_count"] == 1
    assert res["skipped_existing_chunks"] == 0
    assert res["write_receipt"]["ok"] is False


def test_resume_rejects_changed_source_file_or_chunk_config_checkpoint(tmp_path):
    sig1 = lc.build_resume_signature(
        collection_name="staging_v2",
        corpus_version="2026-11-18-v2",
        data_file_sha256="a" * 64,
        chunk_size=512,
        chunk_overlap=50,
        vector_size=4,
        embedding_fingerprint="e" * 64,
    )
    checkpoint = {"resume_signature": sig1}

    # Source file changed -> rejected.
    with pytest.raises(lc.CorpusConflictError, match="data_file_sha256"):
        lc.verify_resume_compatibility(checkpoint, {**sig1, "data_file_sha256": "b" * 64})

    # Chunking changed -> rejected.
    with pytest.raises(lc.CorpusConflictError, match="chunk_size"):
        lc.verify_resume_compatibility(checkpoint, {**sig1, "chunk_size": 600})

    # Embedding fingerprint changed -> rejected.
    with pytest.raises(lc.CorpusConflictError, match="embedding_fingerprint"):
        lc.verify_resume_compatibility(checkpoint, {**sig1, "embedding_fingerprint": "f" * 64})


# ─────────────────────────────────────────────────────────────────────────────
# 4. R13 — FINGERPRINT, BM25/QDRANT SYNC, PINNING, CACHE, WORKER GUARD
# ─────────────────────────────────────────────────────────────────────────────


def test_r13_same_count_different_hash_detected_in_qdrant_and_bm25(tmp_path):
    from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot

    chunks_a = [
        {
            "doc_id": "d1",
            "document_id": "d1",
            "chunk_id": "d1-chunk-001",
            "title": "BMI",
            "content": "BMI là chỉ số khối cơ thể giúp sàng lọc ban đầu.",
            "source": "guide",
            "content_type": "inbody_metric",
            "domain": "health_inbody",
            "content_hash": "a" * 64,
        }
    ]
    chunks_b = [
        {
            **chunks_a[0],
            "content": "BMI là chỉ số đã thay đổi nội dung nhưng cùng số lượng chunk.",
            "content_hash": "b" * 64,
        }
    ]
    fp_a = lc.compute_chunk_set_fingerprint(chunks_a)["chunk_set_fingerprint"]
    fp_b = lc.compute_chunk_set_fingerprint(chunks_b)["chunk_set_fingerprint"]
    assert fp_a != fp_b

    # Export snapshot for chunks_a, verify loading with expected fp_b fails!
    snap_path = tmp_path / "bm25.json.gz"
    export_bm25_snapshot(
        chunks=chunks_a,
        output_path=snap_path,
        collection_name=search.DEFAULT_COLLECTION_NAME,
        corpus_version="2026-11-18-v2",
        physical_collection="staging_v2",
    )
    assert search.load_search_snapshot(snap_path, expected_chunk_set_fingerprint=fp_b) is False

    # Corrupt/truncated gzip file must NEVER be marked ready!
    corrupt_path = tmp_path / "corrupt.json.gz"
    corrupt_path.write_bytes(b"\x1f\x8b\x08\x00corrupt_partial_write")
    assert search.load_search_snapshot(corrupt_path) is False
    assert search.get_search_stats()["initialized"] is False
    assert search.get_search_stats()["snapshot_error"] is not None


def test_r13_bm25_same_alias_wrong_physical_release_refused_and_explicit_degrade(monkeypatch, tmp_path):
    from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot

    chunks = [
        {
            "doc_id": "d1",
            "document_id": "d1",
            "chunk_id": "d1-chunk-001",
            "title": "BMI",
            "content": "BMI là chỉ số khối cơ thể tham khảo trong đánh giá InBody.",
            "source": "guide",
            "content_type": "inbody_metric",
            "domain": "health_inbody",
        }
    ]
    snap_path = tmp_path / "bm25_v1.json.gz"
    export_bm25_snapshot(
        chunks=chunks,
        output_path=snap_path,
        collection_name=search.DEFAULT_COLLECTION_NAME,
        corpus_version="2026-11-18-v1",
        physical_collection="col_v1",
        release_id="rel-v1",
    )
    assert search.load_search_snapshot(snap_path) is True

    # Alias has moved to col_v2 while BM25 still belongs to col_v1!
    live_qdrant = _FakeAliasesQdrant(aliases={search.DEFAULT_COLLECTION_NAME: "col_v2"})

    # Default policy = refuse -> raises CorpusReleaseMismatchError (never silently mixes!)
    monkeypatch.setenv("RETRIEVAL_MISMATCH_POLICY", "refuse")
    with pytest.raises(lc.CorpusReleaseMismatchError):
        search.hybrid_search(
            "BMI là gì",
            limit=3,
            use_rerank=False,
            expand_parents=False,
            qdrant_client=live_qdrant,
        )

    # Explicit dense_only policy -> skips BM25 and labels dense_only (never "hybrid"!)
    captured_collections = []

    def fake_vector_fallback(query, **kwargs):
        captured_collections.append(kwargs.get("collection_name"))
        return [
            {
                "doc_id": "d2",
                "document_id": "d2",
                "chunk_id": "d2-1",
                "content": "BMI mới từ col_v2.",
                "similarity_score": 0.9,
                "content_type": "inbody_metric",
            }
        ]

    monkeypatch.setattr(search, "vector_search_fallback", fake_vector_fallback)
    res_dense = search.hybrid_search(
        "BMI là gì",
        limit=3,
        use_rerank=False,
        expand_parents=False,
        qdrant_client=live_qdrant,
        mismatch_policy="dense_only",
    )
    assert captured_collections == ["col_v2"]
    assert len(res_dense) == 1
    assert res_dense[0]["retrieval_mode"] == "dense_only"
    assert res_dense[0]["release_mismatch_degraded"] is True


def test_r13_alias_switch_mid_request_does_not_mix_corpora(monkeypatch, tmp_path):
    from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot

    chunks = [
        {
            "doc_id": "d1",
            "document_id": "d1",
            "chunk_id": "d1-chunk-001",
            "title": "BMI",
            "content": "BMI là chỉ số khối cơ thể tham khảo trong đánh giá InBody.",
            "source": "guide",
            "content_type": "inbody_metric",
            "domain": "health_inbody",
        }
    ]
    snap_path = tmp_path / "bm25_v1.json.gz"
    export_bm25_snapshot(
        chunks=chunks,
        output_path=snap_path,
        collection_name=search.DEFAULT_COLLECTION_NAME,
        corpus_version="2026-11-18-v1",
        physical_collection="col_v1",
        release_id="rel-v1",
    )
    assert search.load_search_snapshot(snap_path) is True

    # Alias points to col_v1 at request start, then switches to col_v2 right before vector search!
    live_qdrant = _FakeAliasesQdrant(aliases={search.DEFAULT_COLLECTION_NAME: "col_v1"})
    queried_collections = []

    def fake_vector_fallback(query, **kwargs):
        # Simulate external alias switch happening AFTER request pinned col_v1!
        live_qdrant.aliases[search.DEFAULT_COLLECTION_NAME] = "col_v2"
        queried_collections.append(kwargs.get("collection_name"))
        return [
            {
                "doc_id": "d1",
                "document_id": "d1",
                "chunk_id": "d1-chunk-001",
                "content": "BMI là chỉ số khối cơ thể tham khảo trong đánh giá InBody.",
                "similarity_score": 0.95,
                "content_type": "inbody_metric",
            }
        ]

    monkeypatch.setattr(search, "vector_search_fallback", fake_vector_fallback)
    results = search.hybrid_search(
        "BMI là gì",
        limit=3,
        use_rerank=False,
        expand_parents=False,
        qdrant_client=live_qdrant,
    )
    assert queried_collections == ["col_v1"]
    assert results[0]["active_physical_collection"] == "col_v1"
    assert results[0]["retrieval_mode"] == "hybrid"


def test_r13_new_release_invalidates_response_cache_even_with_same_alias_and_count(monkeypatch):
    messages = [{"role": "user", "content": "BMI là gì?"}]
    model_cfg = {"provider": "openai", "model": "test-model"}
    key_v1 = build_llm_response_cache_key(
        messages=messages,
        model_config=model_cfg,
        corpus_fingerprint={
            "corpus_version": "2026-11-18-v1",
            "release_id": "rel-v1",
            "physical_collection": "col_v1",
            "chunk_set_fingerprint": "a" * 64,
            "collection_name": "nmk_chatbot_active",
            "snapshot_point_count": 100,
        },
    )
    key_v2 = build_llm_response_cache_key(
        messages=messages,
        model_config=model_cfg,
        corpus_fingerprint={
            "corpus_version": "2026-11-18-v1",  # Even if same version & alias & count!
            "release_id": "rel-v2",
            "physical_collection": "col_v2",
            "chunk_set_fingerprint": "b" * 64,
            "collection_name": "nmk_chatbot_active",
            "snapshot_point_count": 100,
        },
    )
    assert key_v1 != key_v2


def test_r13_multi_worker_bm25_config_is_blocked(monkeypatch):
    monkeypatch.setenv("API_WORKERS", "2")
    monkeypatch.setenv("BM25_AUTOLOAD", "true")
    monkeypatch.delenv("ALLOW_UNSUPPORTED_MULTI_WORKER_BM25", raising=False)
    with pytest.raises(RuntimeError, match="API_WORKERS=2"):
        search.validate_lexical_worker_config()

    monkeypatch.setenv("API_WORKERS", "1")
    info = search.validate_lexical_worker_config()
    assert info["multi_worker_supported"] is False
    assert info["lexical_index_owner"] == "single_api_process_in_memory"


def test_r12_celery_and_import_checkpoint_preserve_partial_failure(
    monkeypatch, tmp_path
):
    fake_qdrant = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        upsert_outcomes=[
            UpdateResult(operation_id=1, status=UpdateStatus.COMPLETED),
            RuntimeError("second batch network drop"),
        ],
    )
    monkeypatch.setattr(tasks, "get_embedding", lambda text: [0.1, 0.2, 0.3, 0.4])

    with pytest.raises(lc.QdrantWriteError) as exc_info:
        tasks.index_health_documents(
            [_doc("d1"), _doc("d2")],
            collection_name="staging_v2",
            corpus_version="2026-11-18-v2",
            qdrant_client=fake_qdrant,
            raise_on_error=True,
            lock_dir=str(tmp_path / "locks"),
        )
    assert exc_info.value.receipt["committed_documents"] == 1
    assert exc_info.value.receipt["failed_documents"] == 1
    assert exc_info.value.receipt["partial_write"] is True

    # The supported importer must not advance its checkpoint past a failed batch.
    fake_qdrant2 = _FakeAliasesQdrant(
        aliases={"nmk_chatbot_active": "prod_col_v1"},
        upsert_outcomes=[
            UpdateResult(operation_id=1, status=UpdateStatus.COMPLETED),
            RuntimeError("batch 2 failed"),
        ],
        points_by_collection={"staging_v2": []},
    )
    data_file = _sample_jsonl(tmp_path, [_doc("m1"), _doc("m2")])
    manifest_file = tmp_path / "missing_manifest.json"
    monkeypatch.setattr(import_data, "get_embedding_safe", lambda texts: [[0.1, 0.2, 0.3, 0.4] for _ in texts])

    res = import_data.import_embedding_dataset(
        data_file_path=data_file,
        collection_name="staging_v2",
        corpus_version="2026-11-18-v2",
        batch_size=1,
        vector_size=4,
        manifest_file=manifest_file,
        qdrant_client=fake_qdrant2,
        lock_dir=tmp_path / "locks",
    )
    assert res["status"] is False
    assert res["last_successful_upsert_line"] == 1
    assert res["last_processed_line"] == 2
    assert res["write_receipt"]["committed_points"] == 1
    assert res["write_receipt"]["failed_points"] == 1
    assert res["write_receipt"]["partial_write"] is True


def test_r13_readiness_and_search_refuse_corrupt_or_mismatched_bm25_snapshot(monkeypatch, tmp_path):
    import importlib
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    from fastapi.testclient import TestClient

    api = importlib.import_module("api.app")
    monkeypatch.setenv("AUTH_MODE", "development")

    # 1. Corrupt snapshot makes /health/ready return 503 with corpus_release_sync=False!
    corrupt = tmp_path / "corrupt_bm25.json.gz"
    corrupt.write_bytes(b"not-a-valid-gzip")
    assert search.load_search_snapshot(corrupt) is False

    report = api._readiness_report()
    assert report["dependencies"]["corpus_release_sync"] is False
    assert report["status"] == "degraded"

    # 2. Mismatched release causes /search to return 503 (never silently mix corpora).
    from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot

    snap_path = tmp_path / "bm25_v1.json.gz"
    export_bm25_snapshot(
        chunks=[
            {
                "doc_id": "d1",
                "document_id": "d1",
                "chunk_id": "d1-1",
                "title": "BMI",
                "content": "BMI là chỉ số khối cơ thể tham khảo trong đánh giá InBody.",
                "source": "guide",
                "content_type": "inbody_metric",
                "domain": "health_inbody",
            }
        ],
        output_path=snap_path,
        collection_name=search.DEFAULT_COLLECTION_NAME,
        corpus_version="2026-11-18-v1",
        physical_collection="col_v1",
        release_id="rel-v1",
    )
    assert search.load_search_snapshot(snap_path) is True
    monkeypatch.setenv("RETRIEVAL_MISMATCH_POLICY", "refuse")
    monkeypatch.setattr(search, "_resolve_alias_target", lambda alias, qdrant_client=None: "col_v2")

    client = TestClient(api.app)
    resp = client.post("/search", json={"query": "BMI là gì", "limit": 3, "use_rerank": False})
    assert resp.status_code == 503


def test_data_pipeline_refuses_hardcoded_version_and_offline_non_dry_run(tmp_path):
    from data_pipeline import run_pipeline

    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps(
            {
                "doc_id": "d1",
                "document_id": "d1",
                "chunk_id": "d1-chunk-001",
                "title": "BMI",
                "breadcrumb": "[BMI]",
                "content": "[BMI]\nBMI là chỉ số khối cơ thể tham khảo trong đánh giá InBody.",
                "source": "guide",
                "content_type": "inbody_metric",
                "domain": "health_inbody",
                "content_hash": "a" * 64,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # BM25 stage MUST reject empty corpus_version (no silent "2026.1").
    with pytest.raises(lc.CorpusAdmissionError):
        run_pipeline.run_bm25_stage(
            corpus_version="",
            staging_collection="staging_v2",
            chunks_path=chunks_file,
            output_path=tmp_path / "bm25.json.gz",
        )

    # Qdrant stage without --dry-run MUST fail closed when Qdrant/Embedder are offline.
    offline_indexer = SimpleNamespace(is_available=lambda: False)
    offline_embedder = SimpleNamespace(is_available=lambda: False)
    with pytest.raises(RuntimeError, match="Từ chối ghi Qdrant thật"):
        run_pipeline.run_qdrant_stage(
            dry_run=False,
            corpus_version="2026-11-18-v2",
            staging_collection="staging_v2",
            chunks_path=chunks_file,
            indexer=offline_indexer,
            embedder=offline_embedder,
        )

