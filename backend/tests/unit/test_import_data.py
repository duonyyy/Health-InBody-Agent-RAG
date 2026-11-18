from pathlib import Path

from pipelines import import_data
from rag.provenance import compute_document_content_hash


def _record(doc_id: str) -> dict:
    return {
        "doc_id": doc_id,
        "title": "Hướng dẫn sức khỏe",
        "content": "Nội dung kiểm thử đủ dài để vượt qua bước kiểm tra schema tài liệu.",
        "source": "unit-test",
        "content_type": "general_health",
        "domain": "health_inbody",
        "language": "vi",
        "metadata": {"source_url": "https://example.test/source"},
    }


def _trusted_record(doc_id: str) -> dict:
    record = _record(doc_id)
    record["metadata"].update(
        {
            "publisher": "Cơ quan y tế kiểm thử",
            "source_tier": "guideline",
            "published_at": "2025-01-15",
            "reviewed_at": "2026-08-14",
            "medical_review_status": "approved",
        }
    )
    return record


def _synthetic_registry_for(record: dict) -> dict:
    return {
        "schema_version": 1,
        "registry_version": "synthetic-test-only",
        "is_synthetic_fixture": True,
        "reviewers": {
            "clinician-syn-1": {
                "name": "Synthetic Test Reviewer",
                "role": "clinical_reviewer",
                "active": True,
            }
        },
        "reviews": [
            {
                "review_id": "rev-syn-import-001",
                "document_id": record["doc_id"],
                "reviewer_id": "clinician-syn-1",
                "review_role": "clinical_reviewer",
                "review_scope": "general_health",
                "reviewed_at": "2026-08-14T00:00:00Z",
                "content_hash": compute_document_content_hash(record["content"]),
                "document_version": "1.0",
                "decision": "approved",
                "notes": "Synthetic test review for strict importer validation.",
                "verified_source_tier": "guideline",
                "verified_publisher": "Cơ quan y tế kiểm thử",
                "verified_source_url": "https://example.test/source",
                "verified_published_at": "2025-01-15",
                "is_synthetic_fixture": True,
            }
        ],
    }


def test_strict_source_validation_rejects_legacy_and_self_claimed_and_accepts_registry_verified():
    legacy_errors = import_data.validate_document(
        _record("legacy"),
        line_number=1,
        require_trusted_source_metadata=True,
    )
    self_claimed_errors = import_data.validate_document(
        _trusted_record("self-claimed"),
        line_number=2,
        require_trusted_source_metadata=True,
    )
    curated = _trusted_record("trusted")
    curated["document_version"] = "1.0"
    trusted_errors = import_data.validate_document(
        curated,
        line_number=3,
        require_trusted_source_metadata=True,
        review_registry=_synthetic_registry_for(curated),
        allow_synthetic_registry=True,
    )

    assert any("missing trusted source metadata" in error for error in legacy_errors)
    assert any("not backed by a managed review registry record" in error for error in self_claimed_errors)
    assert trusted_errors == []


def test_chunk_payload_has_version_hash_and_stable_id(monkeypatch):
    monkeypatch.setattr(
        import_data,
        "split_document_safe",
        lambda text, metadata, chunk_size, chunk_overlap: [
            import_data.SimpleDocument(text, metadata)
        ],
    )
    monkeypatch.setattr(
        import_data,
        "get_embedding_safe",
        lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
    )

    first, _ = import_data.build_chunk_vectors(
        _record("doc-001"),
        line_number=1,
        chunk_size=512,
        chunk_overlap=50,
        embedding_batch_size=32,
        corpus_version="2026-07-30-v2",
    )
    second, _ = import_data.build_chunk_vectors(
        _record("doc-001"),
        line_number=1,
        chunk_size=512,
        chunk_overlap=50,
        embedding_batch_size=32,
        corpus_version="2026-07-30-v2",
    )

    assert first.keys() == second.keys()
    payload = next(iter(first.values()))["payload"]
    assert payload["document_id"] == "doc-001"
    assert payload["corpus_version"] == "2026-07-30-v2"
    assert len(payload["content_hash"]) == 64
    assert payload["text"] == payload["content"]


def _fake_qdrant_client(active_target: str = "prod_collection_v1"):
    class _Alias:
        def __init__(self, alias_name: str, collection_name: str):
            self.alias_name = alias_name
            self.collection_name = collection_name

    class _AliasesResp:
        def __init__(self, items):
            self.aliases = items

    class _FakeQdrant:
        def get_aliases(self):
            return _AliasesResp([_Alias("nmk_chatbot_active", active_target)])

    return _FakeQdrant()


def test_qdrant_write_failure_stops_import_and_writes_manifest(
    monkeypatch, tmp_path
):
    persisted = []

    monkeypatch.setattr(
        import_data,
        "load_jsonl",
        lambda *_: iter([(1, _record("doc-001"))]),
    )
    monkeypatch.setattr(import_data, "sha256_file", lambda *_: "test-sha256")
    monkeypatch.setattr(
        import_data,
        "write_import_manifest",
        lambda path, payload: persisted.append(payload),
    )
    monkeypatch.setattr(import_data, "ensure_payload_indexes_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        import_data,
        "embed_chunk_payloads",
        lambda payloads, *args, **kwargs: {
            pid: {"vector": [0.1, 0.2, 0.3], "payload": pl}
            for pid, pl in payloads.items()
        },
    )
    monkeypatch.setattr(
        import_data,
        "add_vector_safe",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            import_data.ImportWriteError("Qdrant unavailable")
        ),
    )
    monkeypatch.setattr(
        import_data,
        "initialize_search_index_safe",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("BM25 must not initialize after a fatal write")
        ),
    )

    result = import_data.import_embedding_dataset(
        data_file_path=Path(import_data.__file__),
        collection_name="collection_v2",
        batch_size=1,
        vector_size=3,
        corpus_version="2026-07-30-v2",
        skip_collection_create=True,
        manifest_file=tmp_path / "manifest.json",
        qdrant_client=_fake_qdrant_client(),
        lock_dir=tmp_path / "locks",
    )

    assert result["status"] is False
    assert result["fatal_error"] == "Qdrant unavailable"
    assert result["upserted_chunks"] == 0
    assert result["write_receipt"]["ok"] is False
    assert persisted[-1]["status"] is False
    assert persisted[-1]["last_successful_upsert_line"] == 0


def test_dry_run_can_resume_from_jsonl_line(monkeypatch):
    monkeypatch.setattr(
        import_data,
        "load_jsonl",
        lambda *_: iter(
            [
                (1, _record("doc-001")),
                (2, _record("doc-002")),
            ]
        ),
    )
    monkeypatch.setattr(import_data, "sha256_file", lambda *_: "test-sha256")
    monkeypatch.setattr(
        import_data,
        "split_document_safe",
        lambda text, metadata, chunk_size, chunk_overlap: [
            import_data.SimpleDocument(text, metadata)
        ],
    )

    result = import_data.import_embedding_dataset(
        data_file_path=Path(import_data.__file__),
        dry_run=True,
        start_line=2,
        limit=1,
    )

    assert result["processed_docs"] == 1
    assert result["last_processed_line"] == 2
    assert result["total_chunks"] == 1
    assert result["topology_verified"] is False


def test_skip_existing_points_does_not_call_embedding_or_upsert(monkeypatch, tmp_path):
    monkeypatch.setattr(
        import_data,
        "load_jsonl",
        lambda *_: iter([(1, _record("doc-001"))]),
    )
    monkeypatch.setattr(import_data, "sha256_file", lambda *_: "test-sha256")
    monkeypatch.setattr(
        import_data,
        "split_document_safe",
        lambda text, metadata, chunk_size, chunk_overlap: [
            import_data.SimpleDocument(text, metadata)
        ],
    )
    payloads, _ = import_data.build_chunk_payloads(
        _record("doc-001"),
        line_number=1,
        chunk_size=512,
        chunk_overlap=50,
        corpus_version="2026-07-30-v2",
    )
    existing_id, existing_payload = next(iter(payloads.items()))

    monkeypatch.setattr(import_data, "ensure_payload_indexes_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        import_data,
        "get_collection_point_fingerprints_safe",
        lambda *a, **k: {
            existing_id: {
                "qdrant_point_id": existing_id,
                "document_id": existing_payload["document_id"],
                "chunk_id": existing_payload["chunk_id"],
                "content_hash": existing_payload["content_hash"],
                "corpus_version": "2026-07-30-v2",
            }
        },
    )
    monkeypatch.setattr(
        import_data,
        "get_embedding_safe",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Existing chunks must not be embedded")
        ),
    )
    monkeypatch.setattr(
        import_data,
        "add_vector_safe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Existing chunks must not be upserted")
        ),
    )

    result = import_data.import_embedding_dataset(
        data_file_path=Path(import_data.__file__),
        collection_name="collection_v2",
        corpus_version="2026-07-30-v2",
        skip_collection_create=True,
        skip_existing_points=True,
        qdrant_client=_fake_qdrant_client(),
        lock_dir=tmp_path / "locks",
    )

    assert result["status"] is True
    assert result["processed_docs"] == 1
    assert result["total_chunks"] == 1
    assert result["initial_existing_points"] == 1
    assert result["skipped_existing_chunks"] == 1
    assert result["newly_embedded_chunks"] == 0
    assert result["upserted_chunks"] == 0
