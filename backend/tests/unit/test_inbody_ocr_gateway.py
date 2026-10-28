"""The upload gateway must fail closed before forwarding health files."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.inbody_ocr import router
from auth.context import CurrentUser, get_current_user


def _client(authenticated: bool) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("test-owner")
    return TestClient(app)


def test_unauthenticated_upload_is_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "production")
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "true")
    response = _client(False).post("/me/inbody-ocr", files={"file": ("report.png", b"sample")})
    assert response.status_code == 401


def test_disabled_feature_never_forwards_file(monkeypatch):
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "false")
    monkeypatch.setattr("api.inbody_ocr.requests.Session", lambda: (_ for _ in ()).throw(AssertionError("forwarded")))
    response = _client(True).post("/me/inbody-ocr", files={"file": ("report.png", b"sample")})
    assert response.status_code == 404


def test_missing_health_consent_never_forwards_file(monkeypatch):
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "true")
    monkeypatch.setattr("api.inbody_ocr._has_health_consent", lambda _subject: False)
    monkeypatch.setattr("api.inbody_ocr.requests.Session", lambda: (_ for _ in ()).throw(AssertionError("forwarded")))
    response = _client(True).post("/me/inbody-ocr", files={"file": ("report.png", b"sample")})
    assert response.status_code == 409


def test_authenticated_upload_returns_unconfirmed_extraction(monkeypatch):
    monkeypatch.setenv("FEATURE_OCR_UPLOAD", "true")
    monkeypatch.setattr("api.inbody_ocr._has_health_consent", lambda _subject: True)
    seen = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "document_type": "inbody_result", "parser_version": "inbody-v1",
                "status": "needs_confirmation", "extracted_fields": {},
                "unresolved_fields": ["weight_kg"], "warnings": [],
            }

    class Session:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, files, timeout):
            seen["url"] = url
            seen["bytes"] = files["file"][1]
            seen["trust_env"] = self.trust_env
            return Response()

    monkeypatch.setattr("api.inbody_ocr.requests.Session", Session)
    response = _client(True).post("/me/inbody-ocr", files={"file": ("report.png", b"sample")})
    assert response.status_code == 200
    assert response.json()["status"] == "needs_confirmation"
    assert seen["url"].endswith("/ocr/inbody")
    assert seen["bytes"] == b"sample"
    assert seen["trust_env"] is False
