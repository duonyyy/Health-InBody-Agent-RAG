"""Isolated integration test on real local in-memory Qdrant (`QdrantClient(':memory:')`).

NOTE ON ENVIRONMENT SCOPE:
- Uses real `qdrant-client` 1.19.1 local in-memory engine (real create_collection,
  upsert, scroll, query_points, update_collection_aliases, get_aliases).
- Does NOT touch any live Docker/HTTP Qdrant server, serving volumes, or real corpus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data_pipeline.src.indexers.bm25_indexer import export_bm25_snapshot
from pipelines import import_data
from rag import corpus_lifecycle as lc
from rag import search
from rag.qdrant import client as qdrant_mod


def _vec(seed: float) -> list[float]:
    return [seed, 1.0 - seed, 0.5, 0.25]


def test_full_blue_green_corpus_lifecycle_on_isolated_local_qdrant(monkeypatch, tmp_path):
    qdrant = QdrantClient(":memory:")
    lock_dir = tmp_path / "locks"
    manager = lc.CorpusLeaseManager(lock_dir=lock_dir)

    # 1. Seed initial v1 collection & activate alias nmk_chatbot_active -> col_v1.
    docs_v1 = [
        {
            "doc_id": "inbody-bmi-01",
            "document_id": "inbody-bmi-01",
            "title": "Chỉ số BMI",
            "content": "BMI là chỉ số khối cơ thể tính bằng cân nặng chia bình phương chiều cao, chỉ dùng sàng lọc ban đầu.",
            "source": "synthetic_v1",
            "content_type": "inbody_metric",
            "domain": "health_inbody",
            "language": "vi",
            "metadata": {"source_url": "https://example.test/bmi-v1"},
        }
    ]
    file_v1 = tmp_path / "corpus_v1.jsonl"
    file_v1.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs_v1) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        import_data,
        "get_embedding_safe",
        lambda texts: [_vec(0.8) for _ in texts],
    )
    monkeypatch.setattr(search, "_get_embedding", lambda query, **kwargs: _vec(0.8))

    res_v1 = import_data.import_embedding_dataset(
        data_file_path=file_v1,
        collection_name="col_v1",
        corpus_version="2026-11-18-v1",
        vector_size=4,
        batch_size=10,
        manifest_file=tmp_path / "manifest_v1.json",
        release_manifest_file=tmp_path / "release_v1.json",
        qdrant_client=qdrant,
        lock_dir=lock_dir,
        embedding_model_id="synthetic-embed-v1",
    )
    assert res_v1["status"] is True
    assert res_v1["write_receipt"]["committed_points"] == 1
    assert res_v1["write_receipt"]["ok"] is True

    act_v1 = qdrant_mod.activate_collection_alias(
        "col_v1",
        "nmk_chatbot_active",
        release_manifest_path=tmp_path / "release_v1.json",
        lease_manager=manager,
        qdrant_client=qdrant,
    )
    assert act_v1["status"] is True
    assert qdrant_mod.get_alias_target("nmk_chatbot_active", qdrant_client=qdrant) == "col_v1"

    # 2. Serving alias AND physical target col_v1 MUST now both be blocked from writes!
    for forbidden in ("nmk_chatbot_active", "col_v1"):
        with pytest.raises(lc.CorpusAdmissionError):
            import_data.import_embedding_dataset(
                data_file_path=file_v1,
                collection_name=forbidden,
                corpus_version="2026-11-18-v2",
                vector_size=4,
                qdrant_client=qdrant,
                lock_dir=lock_dir,
            )

    # 3. Build staging release v2 into col_v2 (new physical staging collection).
    docs_v2 = [
        docs_v1[0],
        {
            "doc_id": "safety-redflag-01",
            "document_id": "safety-redflag-01",
            "title": "Cảnh báo an toàn tập luyện",
            "content": "Đau ngực và khó thở khi tập là dấu hiệu cảnh báo cần dừng tập ngay và tìm hỗ trợ y tế khẩn cấp.",
            "source": "synthetic_v2",
            "content_type": "medical_safety",
            "domain": "health_inbody",
            "language": "vi",
            "metadata": {"source_url": "https://example.test/safety-v2"},
        },
    ]
    file_v2 = tmp_path / "corpus_v2.jsonl"
    file_v2.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs_v2) + "\n", encoding="utf-8")

    release_v2_path = tmp_path / "release_v2.json"
    res_v2 = import_data.import_embedding_dataset(
        data_file_path=file_v2,
        collection_name="col_v2",
        corpus_version="2026-11-18-v2",
        vector_size=4,
        batch_size=10,
        manifest_file=tmp_path / "manifest_v2.json",
        release_manifest_file=release_v2_path,
        qdrant_client=qdrant,
        lock_dir=lock_dir,
        embedding_model_id="synthetic-embed-v1",
    )
    assert res_v2["status"] is True
    assert res_v2["upserted_chunks"] == 2

    # 4. Idempotent resume on identical input/config skips all chunks with 0 new embeds/upserts!
    embed_calls_on_resume = []
    monkeypatch.setattr(
        import_data,
        "get_embedding_safe",
        lambda texts: embed_calls_on_resume.append(texts) or [_vec(0.8) for _ in texts],
    )
    res_v2_resume = import_data.import_embedding_dataset(
        data_file_path=file_v2,
        collection_name="col_v2",
        corpus_version="2026-11-18-v2",
        vector_size=4,
        skip_collection_create=True,
        skip_existing_points=True,
        manifest_file=tmp_path / "manifest_v2.json",
        qdrant_client=qdrant,
        lock_dir=lock_dir,
        embedding_model_id="synthetic-embed-v1",
    )
    assert res_v2_resume["status"] is True
    assert res_v2_resume["skipped_existing_chunks"] == 2
    assert res_v2_resume["upserted_chunks"] == 0
    assert embed_calls_on_resume == []

    # 5. Export synchronized BM25 snapshot for col_v2 & attach to release_v2 manifest.
    q_fingerprints = qdrant_mod.get_collection_point_fingerprints("col_v2", qdrant_client=qdrant)
    # Build matching chunk records from Qdrant col_v2 payloads.
    scrolled_pts, _ = qdrant.scroll("col_v2", limit=100, with_payload=True, with_vectors=False)
    chunks_v2 = [dict(p.payload) for p in scrolled_pts]
    bm25_v2_path = tmp_path / "bm25_v2.json.gz"
    bm25_meta = export_bm25_snapshot(
        chunks=chunks_v2,
        output_path=bm25_v2_path,
        collection_name="nmk_chatbot_active",
        corpus_version="2026-11-18-v2",
        physical_collection="col_v2",
        release_id=res_v2["release_id"],
    )
    assert bm25_meta["chunk_set_fingerprint"] == res_v2["chunk_set_fingerprint"]
    assert len(q_fingerprints) == 2

    manifest_v2 = lc.load_release_manifest(release_v2_path)
    manifest_v2["bm25_artifact"] = {
        "path": str(bm25_v2_path),
        "sha256": bm25_meta["sha256"],
        "schema_version": 1,
        "tokenizer_version": bm25_meta["tokenizer_version"],
        "document_count": bm25_meta["document_count"],
        "chunk_set_fingerprint": bm25_meta["chunk_set_fingerprint"],
        "physical_collection": "col_v2",
        "release_id": res_v2["release_id"],
        "corpus_version": "2026-11-18-v2",
    }
    lc.save_release_manifest(release_v2_path, manifest_v2)

    # 6. Verify Qdrant collection integrity (count + vector size + chunk_set_fingerprint + version).
    integrity = qdrant_mod.verify_collection_integrity(
        "col_v2",
        expected_points=2,
        expected_vector_size=4,
        expected_chunk_set_fingerprint=res_v2["chunk_set_fingerprint"],
        expected_corpus_version="2026-11-18-v2",
        qdrant_client=qdrant,
    )
    assert integrity["verified"] is True

    # 7. Activate alias nmk_chatbot_active -> col_v2 (preserving col_v1 for rollback!).
    act_v2 = qdrant_mod.activate_collection_alias(
        "col_v2",
        "nmk_chatbot_active",
        release_manifest_path=release_v2_path,
        lease_manager=manager,
        qdrant_client=qdrant,
    )
    assert act_v2["previous_collection"] == "col_v1"
    assert act_v2["active_collection"] == "col_v2"
    assert act_v2["previous_collection_preserved"] is True
    assert qdrant_mod.get_collection_stats("col_v1", qdrant_client=qdrant)["points_count"] == 1

    # 8. Runtime hybrid search on real local Qdrant + synchronized BM25 v2 -> true hybrid!
    assert search.load_search_snapshot(
        bm25_v2_path,
        expected_physical_collection="col_v2",
        expected_corpus_version="2026-11-18-v2",
        expected_chunk_set_fingerprint=res_v2["chunk_set_fingerprint"],
        qdrant_client=qdrant,
        verify_against_qdrant=True,
    )
    hits = search.hybrid_search(
        "chỉ số BMI là gì",
        limit=3,
        use_rerank=False,
        expand_parents=False,
        qdrant_client=qdrant,
        release_manifest_path=release_v2_path,
    )
    assert len(hits) >= 1
    assert hits[0]["retrieval_mode"] == "hybrid"
    assert hits[0]["active_physical_collection"] == "col_v2"

    # 9. Controlled rollback alias back to col_v1 -> BM25 v2 now mismatches and hybrid refuses!
    rb = qdrant_mod.activate_collection_alias(
        "col_v1",
        "nmk_chatbot_active",
        expected_points=1,
        lease_manager=manager,
        qdrant_client=qdrant,
    )
    assert rb["active_collection"] == "col_v1"
    assert rb["previous_collection"] == "col_v2"
    assert qdrant_mod.get_collection_stats("col_v2", qdrant_client=qdrant)["points_count"] == 2

    with pytest.raises(lc.CorpusReleaseMismatchError):
        search.hybrid_search(
            "chỉ số BMI là gì",
            limit=3,
            use_rerank=False,
            expand_parents=False,
            qdrant_client=qdrant,
        )

