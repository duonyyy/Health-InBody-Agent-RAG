"""Actual importer and Qdrant local; synthetic files and stub embeddings only."""
import json

import pytest
from qdrant_client import QdrantClient
from pipelines import import_data
from rag import corpus_lifecycle as lc


@pytest.fixture
def staging(monkeypatch, tmp_path):
    client = QdrantClient(":memory:")
    source = tmp_path / "input.jsonl"
    docs = [{"doc_id": f"d{i}", "document_id": f"d{i}", "title": "Synthetic",
             "content": f"Nội dung tổng hợp số {i} để kiểm chứng importer độc lập.",
             "source": "synthetic", "content_type": "inbody_metric", "language": "vi", "domain": "health_inbody"}
            for i in range(2)]
    source.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs), encoding="utf-8")
    counts = {"embed": 0, "upsert": 0}
    def embed(texts):
        counts["embed"] += len(texts)
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]
    original_upsert = client.upsert
    def upsert(*args, **kwargs):
        counts["upsert"] += len(kwargs.get("points", []))
        return original_upsert(*args, **kwargs)
    monkeypatch.setattr(import_data, "get_embedding_safe", embed)
    monkeypatch.setattr(client, "upsert", upsert)
    args = dict(data_file_path=source, collection_name="staging_matrix", corpus_version="v1",
                vector_size=4, batch_size=1, manifest_file=tmp_path / "manifest.json",
                embedding_model_id="synthetic", qdrant_client=client, lock_dir=tmp_path / "locks")
    yield client, args, counts
    client.close()


def test_resume_only_missing_point(staging):
    client, args, counts = staging
    assert import_data.import_embedding_dataset(**args)["status"] is True
    point = client.scroll("staging_matrix")[0][0]
    client.delete("staging_matrix", points_selector=[point.id])
    counts.update(embed=0, upsert=0)
    result = import_data.import_embedding_dataset(**args, skip_existing_points=True, skip_collection_create=True)
    assert result["status"] is True
    assert counts == {"embed": 1, "upsert": 1}
    assert result["skipped_existing_chunks"] == 1


@pytest.mark.parametrize("field", ["collection_name", "corpus_version", "data_file_sha256", "chunk_size", "chunk_overlap", "vector_size", "embedding_fingerprint", "splitter_version"])
@pytest.mark.parametrize("mode", ["missing", "changed"])
def test_missing_signature_field_fails_before_mutation(staging, field, mode):
    client, args, counts = staging
    assert import_data.import_embedding_dataset(**args)["status"] is True
    manifest = args["manifest_file"]
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if mode == "missing":
        del value["resume_signature"][field]
    else:
        value["resume_signature"][field] = "different"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    counts.update(embed=0, upsert=0)
    with pytest.raises(lc.CorpusConflictError):
        import_data.import_embedding_dataset(**args, skip_existing_points=True)
    assert counts == {"embed": 0, "upsert": 0}


def test_second_batch_failure_receipt_and_lease(staging, monkeypatch):
    client, args, counts = staging
    original = client.upsert
    calls = []
    def fail_second(*a, **kw):
        calls.append(True)
        if len(calls) == 2:
            raise OSError("synthetic write failure")
        return original(*a, **kw)
    monkeypatch.setattr(client, "upsert", fail_second)
    result = import_data.import_embedding_dataset(**args)
    assert result["status"] is False
    assert result["last_successful_upsert_line"] == 1
    assert result["write_receipt"]["committed_points"] == 1
    assert result["write_receipt"]["failed_points"] == 1
    assert result["write_receipt"]["partial_write"] is True
    # A new importer can acquire the same lease after the failed job.
    monkeypatch.setattr(client, "upsert", original)
    result = import_data.import_embedding_dataset(**args, skip_existing_points=True, skip_collection_create=True)
    assert result["status"] is True
    assert result["upserted_chunks"] == 1


def test_conflict_after_prior_committed_batch_is_reported_as_partial(staging):
    client, args, counts = staging
    assert import_data.import_embedding_dataset(**args)["status"] is True
    points = {p.payload["document_id"]: p.id for p in client.scroll("staging_matrix", with_payload=True)[0]}
    client.delete("staging_matrix", points_selector=[points["d0"]])
    client.set_payload("staging_matrix", {"embedding_fingerprint": "f" * 64}, points=[points["d1"]])
    counts.update(embed=0, upsert=0)
    result = import_data.import_embedding_dataset(**args, skip_existing_points=True, skip_collection_create=True)
    assert result["status"] is False
    assert result["conflict_count"] == 1
    assert result["write_receipt"]["committed_points"] == 1
    assert result["write_receipt"]["partial_write"] is True
    assert result["last_successful_upsert_line"] == 1
    assert counts == {"embed": 1, "upsert": 1}
