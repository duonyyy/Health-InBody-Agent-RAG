import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from inbody_ocr.api import dependencies, routes
from inbody_ocr.config import Settings
from inbody_ocr.inbody.schemas import InBodyResponse
from inbody_ocr.main import app


def test_http_health_check():
    app.dependency_overrides[routes.get_ollama_client] = lambda: SimpleNamespace(health=lambda: (True, True, "ok"))
    app.dependency_overrides[routes.get_paddle_reader] = lambda: SimpleNamespace(is_available=lambda: True)
    try:
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["model_available"] is True
        assert data["paddle_ready"] is True
    finally:
        app.dependency_overrides.clear()


def test_http_inbody_upload_validation_and_success():
    app.dependency_overrides[routes.get_settings] = lambda: Settings(ollama_model="qwen2.5:7b")
    app.dependency_overrides[routes.get_inbody_service] = lambda: SimpleNamespace(
        extract=lambda _: InBodyResponse(parser_version="inbody-paddle-v1")
    )
    try:
        client = TestClient(app)

        # Rejects bad file content
        assert client.post("/ocr/inbody", files={"file": ("bad.png", b"not image", "image/png")}).status_code == 400

        # Accepts valid image
        image = Image.new("RGB", (100, 100), "white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        response = client.post("/ocr/inbody", files={"file": ("report.png", buffer.getvalue(), "image/png")})

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "needs_confirmation"
        assert payload["parser_version"] == "inbody-paddle-v1"
    finally:
        app.dependency_overrides.clear()


def test_internal_service_key_authentication():
    secret_key = "test-internal-secret-token"
    mock_settings = lambda: Settings(
        ollama_model="qwen2.5:7b",
        internal_service_key=secret_key,
    )
    app.dependency_overrides[routes.get_settings] = mock_settings
    app.dependency_overrides[dependencies.get_settings] = mock_settings
    app.dependency_overrides[routes.get_inbody_service] = lambda: SimpleNamespace(
        extract=lambda _: InBodyResponse(parser_version="inbody-paddle-v1")
    )
    try:
        client = TestClient(app)
        image = Image.new("RGB", (100, 100), "white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        file_payload = {"file": ("report.png", buffer.getvalue(), "image/png")}

        # 1. Missing key -> 401
        res_no_key = client.post("/ocr/inbody", files=file_payload)
        assert res_no_key.status_code == 401

        # 2. Invalid key -> 401
        file_payload["file"] = ("report.png", buffer.getvalue(), "image/png")
        res_wrong_key = client.post(
            "/ocr/inbody",
            files=file_payload,
            headers={"X-Internal-Service-Key": "wrong-secret"},
        )
        assert res_wrong_key.status_code == 401

        # 3. Valid key via X-Internal-Service-Key -> 200
        file_payload["file"] = ("report.png", buffer.getvalue(), "image/png")
        res_valid_header = client.post(
            "/ocr/inbody",
            files=file_payload,
            headers={"X-Internal-Service-Key": secret_key},
        )
        assert res_valid_header.status_code == 200

        # 4. Valid key via Authorization Bearer -> 200
        file_payload["file"] = ("report.png", buffer.getvalue(), "image/png")
        res_valid_bearer = client.post(
            "/ocr/inbody",
            files=file_payload,
            headers={"Authorization": f"Bearer {secret_key}"},
        )
        assert res_valid_bearer.status_code == 200
    finally:
        app.dependency_overrides.clear()

