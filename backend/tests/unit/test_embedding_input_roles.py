"""Embedding inputs and fingerprint use configured retrieval roles."""

def test_query_and_passage_prefixes_reach_embedding_service(monkeypatch):
    from llm import client
    from rag import search

    monkeypatch.setenv("EMBEDDING_QUERY_PREFIX", "query: ")
    monkeypatch.setenv("EMBEDDING_PASSAGE_PREFIX", "passage: ")
    seen = []
    monkeypatch.setattr(client, "get_custom_embedding", lambda text, **kwargs: seen.append(text) or [0.1])

    assert client.get_embedding(["first", "second"]) == [0.1]
    assert search._get_embedding("question") == [0.1]
    assert seen == [["passage: first", "passage: second"], "query: question"]


def test_embedding_prefixes_affect_release_fingerprint(monkeypatch):
    from rag.corpus_lifecycle import current_embedding_config

    monkeypatch.delenv("EMBEDDING_QUERY_PREFIX", raising=False)
    monkeypatch.delenv("EMBEDDING_PASSAGE_PREFIX", raising=False)
    old = current_embedding_config(vector_size=384, model_identifier="test")
    monkeypatch.setenv("EMBEDDING_QUERY_PREFIX", "query: ")
    monkeypatch.setenv("EMBEDDING_PASSAGE_PREFIX", "passage: ")
    new = current_embedding_config(vector_size=384, model_identifier="test")
    assert old["fingerprint"] != new["fingerprint"]


def test_pipeline_embedding_uses_passage_prefix(monkeypatch):
    from data_pipeline.src.embedder import client

    monkeypatch.setenv("EMBEDDING_PASSAGE_PREFIX", "passage: ")
    sent = []
    class Response:
        status_code = 200
        def json(self):
            return {"embeddings": [[0.1]]}
    monkeypatch.setattr(client.requests, "post", lambda url, json, timeout: sent.append(json) or Response())
    assert client.EmbeddingClient().embed_batch(["document"]) == [[0.1]]
    assert sent[0]["texts"] == ["passage: document"]
