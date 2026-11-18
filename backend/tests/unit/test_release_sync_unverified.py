import pytest

from rag import search
from rag.corpus_lifecycle import CorpusReleaseMismatchError


@pytest.mark.parametrize("live,physical", [("new_collection", None), (None, "old_collection")])
def test_unverified_release_cannot_mix_dense_and_bm25(monkeypatch, live, physical):
    monkeypatch.setattr(search, "_resolve_alias_target", lambda *args, **kwargs: live)
    monkeypatch.setattr(search, "_search_engine_initialized", True)
    monkeypatch.setattr(search, "_search_index_metadata", {"physical_collection": physical})
    monkeypatch.delenv("CORPUS_RELEASE_MANIFEST_PATH", raising=False)
    info = search.verify_runtime_release_sync()
    assert info["status"] == "unverified"
    assert info["synced"] is False
    assert info["reasons"]
    with pytest.raises(CorpusReleaseMismatchError):
        search.hybrid_search("BMI", qdrant_client=object(), mismatch_policy="refuse")


def test_snapshot_digest_must_match_release_manifest(monkeypatch):
    monkeypatch.setattr(search, "_resolve_alias_target", lambda *args, **kwargs: "collection")
    monkeypatch.setattr(search, "_search_engine_initialized", True)
    monkeypatch.setattr(search, "_search_index_metadata", {
        "physical_collection": "collection", "release_id": "release-1",
        "corpus_version": "v1", "chunk_set_fingerprint": "fingerprint",
        "snapshot_sha256": "different-digest",
    })
    monkeypatch.setattr(search, "load_release_manifest", lambda _: {
        "physical_collection": "collection", "release_id": "release-1",
        "corpus_version": "v1", "chunk_manifest": {"chunk_set_fingerprint": "fingerprint"},
        "bm25_artifact": {"sha256": "expected-digest"},
    })
    info = search.verify_runtime_release_sync(release_manifest_path="release.json")
    assert not info["synced"]
    assert any("sha256" in reason for reason in info["reasons"])
