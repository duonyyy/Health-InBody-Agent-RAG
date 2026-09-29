import pytest
from rag.corpus_policy import validate_shared_document, require_staging_collection


def test_private_metadata_and_pii_are_rejected_even_if_declared_public():
    approved = {"data_scope": "shared_knowledge", "privacy_review_status": "approved", "source_url": "https://example.org/article"}
    validate_shared_document({"content": "Tài liệu kiến thức chung về cơ thể.", "metadata": approved}, require_review=True)
    for document in (
        {"content": "Tài liệu", "metadata": {**approved, "user_id": "alice"}},
        {"content": "Liên hệ alice@example.com", "metadata": approved},
        {"content": "Bệnh nhân: Nguyễn A, cân nặng 72 kg", "metadata": approved},
        {"content": "Tài liệu", "metadata": {"data_scope": "personal"}},
        {**approved, "metadata": {"data_scope": "personal"}, "content": "Tài liệu"},
        {**approved, "title": "Bệnh nhân: Nguyễn A", "content": "Tài liệu"},
        {**approved, "page_content": "alice@example.com"},
        {**approved, "source": "chat_history", "content": "Tài liệu"},
    ):
        with pytest.raises(ValueError):
            validate_shared_document(document, require_review=True)


def test_serving_collection_cannot_be_written_by_admin_api(monkeypatch):
    monkeypatch.setenv("CORPUS_STAGING_COLLECTIONS", "staging-v1,nmk_chatbot_active")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_active")
    assert require_staging_collection("staging-v1") == "staging-v1"
    for name in ("nmk_chatbot_active", "unapproved"):
        with pytest.raises(ValueError):
            require_staging_collection(name)


def test_http_corpus_requires_trusted_admin_and_rejects_batch_before_write(monkeypatch):
    import os
    import importlib
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    from fastapi.testclient import TestClient
    from auth.context import get_current_user, CurrentUser
    api = importlib.import_module("api.app")
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ENABLE_CORPUS_ADMIN_API", "true")
    monkeypatch.setenv("CORPUS_STAGING_COLLECTIONS", "staging-v1")
    writes = []
    monkeypatch.setattr(api, "index_health_documents", lambda *a, **k: writes.append(a) or {})
    document = {"content": "Kiến thức chung.", "data_scope": "shared_knowledge",
                "privacy_review_status": "approved", "source_url": "https://example.org/article"}
    payload = {"collection_name": "staging-v1", "documents": [document]}
    client = TestClient(api.app)
    assert client.post("/documents/index", json=payload).status_code == 401
    assert client.post("/documents/index", headers={"X-Dev-User-Id": "admin"}, json=payload).status_code == 403
    api.app.dependency_overrides[get_current_user] = lambda: CurrentUser("admin", scopes=("corpus:write",))
    try:
        private = {**document, "metadata": {"user_id": "alice"}}
        assert client.post("/documents/index", json={**payload, "documents": [document, private]}).status_code == 422
        assert writes == []
        assert client.post("/documents/index", json=payload).status_code == 200
        assert len(writes) == 1
    finally:
        api.app.dependency_overrides.pop(get_current_user, None)
