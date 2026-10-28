import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from inbody_ocr.api import routes
from inbody_ocr.config import Settings
from inbody_ocr.inbody.schemas import InBodyResponse
from inbody_ocr.main import app


def test_http_health_check(monkeypatch):
    monkeypatch.setattr(routes, "get_ollama_client", lambda: SimpleNamespace(health=lambda: (True, True, "ok")))
    monkeypatch.setattr(routes, "get_paddle_reader", lambda: SimpleNamespace(is_available=lambda: True))
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["model_available"] is True
    assert data["paddle_ready"] is True


def test_http_inbody_upload_validation_and_success(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(ollama_model="qwen2.5:7b"))
    monkeypatch.setattr(
        routes,
        "get_inbody_service",
        lambda: SimpleNamespace(extract=lambda _: InBodyResponse(parser_version="inbody-paddle-v1")),
    )
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
