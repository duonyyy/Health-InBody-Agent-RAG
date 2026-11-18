import pytest

from rag import corpus_lifecycle as lifecycle


@pytest.mark.parametrize("field", ["content_hash", "corpus_version", "embedding_fingerprint", "document_id", "chunk_id"])
@pytest.mark.parametrize("side", ["expected", "existing"])
@pytest.mark.parametrize("missing", [None, "", " "])
def test_resume_rejects_missing_point_evidence(field, side, missing):
    point = {"qdrant_point_id": "id-1", "document_id": "doc-1", "chunk_id": "chunk-1",
             "content_hash": "a" * 64, "corpus_version": "v1", "embedding_fingerprint": "b" * 64}
    expected, existing = dict(point), dict(point)
    (expected if side == "expected" else existing)[field] = missing
    assert lifecycle.check_existing_point_conflict("id-1", expected, {"id-1": existing})[0] == "conflict"


def test_resume_rejects_incomplete_signature():
    signature = lifecycle.build_resume_signature(collection_name="staging", corpus_version="v1",
        data_file_sha256="a" * 64, chunk_size=512, chunk_overlap=50, vector_size=4,
        embedding_fingerprint="b" * 64)
    for field in signature:
        incomplete = dict(signature)
        del incomplete[field]
        with pytest.raises(lifecycle.CorpusConflictError):
            lifecycle.verify_resume_compatibility({"resume_signature": incomplete}, signature)
    with pytest.raises(lifecycle.CorpusConflictError):
        lifecycle.verify_resume_compatibility(signature, signature)


@pytest.mark.parametrize("field,value", [("content_hash", "broken"), ("embedding_fingerprint", "broken"), ("corpus_version", "not valid")])
def test_resume_does_not_accept_identical_malformed_evidence(field, value):
    point = {"qdrant_point_id": "id-1", "document_id": "d1", "chunk_id": "c1",
             "content_hash": "a" * 64, "embedding_fingerprint": "b" * 64, "corpus_version": "v1"}
    point[field] = value
    assert lifecycle.check_existing_point_conflict("id-1", point, {"id-1": dict(point)})[0] == "conflict"
