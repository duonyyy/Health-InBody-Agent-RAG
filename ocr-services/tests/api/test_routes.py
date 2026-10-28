import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from inbody_ocr.api import routes
from inbody_ocr.config import Settings
from inbody_ocr.inbody.schemas import InBodyResponse
from inbody_ocr.main import app


def test_http_only_inbody_and_validates_upload(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(ollama_model="test-model"))
    monkeypatch.setattr(routes, "get_inbody_service", lambda: SimpleNamespace(extract=lambda _: InBodyResponse()))
    client = TestClient(app)
    assert {item.path for item in app.routes if item.path.startswith("/ocr/")} == {"/ocr/inbody"}
    assert client.post("/ocr/inbody", files={"file": ("bad.png", b"not image", "image/png")}).status_code == 400
    image = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    response = client.post("/ocr/inbody", files={"file": ("report.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 200
    assert response.json()["status"] == "needs_confirmation"
