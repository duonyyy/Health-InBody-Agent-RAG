from pathlib import Path

import import_data


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


def test_qdrant_write_failure_stops_import_and_writes_manifest(
    monkeypatch,
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
    monkeypatch.setattr(import_data, "ensure_payload_indexes_safe", lambda *_: None)
    monkeypatch.setattr(
        import_data,
        "build_chunk_vectors",
        lambda *args, **kwargs: (
            {
                "point-1": {
                    "vector": [0.1],
                    "payload": {"content": "test"},
                }
            },
            {"doc_id": "doc-001"},
        ),
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
        corpus_version="2026-07-30-v2",
        skip_collection_create=True,
        manifest_file="manifest.json",
    )

    assert result["status"] is False
    assert result["fatal_error"] == "Qdrant unavailable"
    assert result["upserted_chunks"] == 0
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


def test_skip_existing_points_does_not_call_embedding_or_upsert(monkeypatch):
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
    existing_id = next(iter(payloads))

    monkeypatch.setattr(import_data, "ensure_payload_indexes_safe", lambda *_: None)
    monkeypatch.setattr(
        import_data,
        "get_collection_point_ids_safe",
        lambda *_: {existing_id},
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
    )

    assert result["status"] is True
    assert result["processed_docs"] == 1
    assert result["total_chunks"] == 1
    assert result["initial_existing_points"] == 1
    assert result["skipped_existing_chunks"] == 1
    assert result["newly_embedded_chunks"] == 0
    assert result["upserted_chunks"] == 0
