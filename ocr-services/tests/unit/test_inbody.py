import json
from types import SimpleNamespace

from inbody_ocr.config import Settings
from inbody_ocr.config import get_settings
from inbody_ocr.inbody.extractor import InBodyOcrService
from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.imaging.preprocess import PreparedImage


class FakeClient:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.settings = SimpleNamespace(ocr_num_predict=800)

    def generate(self, **_kwargs):
        return next(self.outputs)


def test_partial_json_keeps_null_unresolved():
    client = FakeClient([json.dumps({"weight_kg": {"value": 72.5, "raw_text": "72.5"},
                                     "pbf_percent": {"value": None, "raw_text": ""}})])
    result = InBodyOcrService(client).extract([PreparedImage(1, "image")])
    assert result.status == "needs_confirmation"
    assert result.extracted_fields["weight_kg"].value == 72.5
    assert result.extracted_fields["weight_kg"].confidence is None
    assert "pbf_percent" in result.unresolved_fields


def test_invalid_and_conflicting_values_need_review():
    outputs = [
        json.dumps({"weight_kg": {"value": 72, "raw_text": "72"},
                    "pbf_percent": {"value": 500, "raw_text": "500"}}),
        json.dumps({"weight_kg": {"value": 82, "raw_text": "82"}}),
    ]
    result = InBodyOcrService(FakeClient(outputs)).extract(
        [PreparedImage(1, "a"), PreparedImage(2, "b")]
    )
    assert "weight_kg" not in result.extracted_fields
    assert "pbf_percent" not in result.extracted_fields
    assert result.warnings


def test_non_json_degrades_to_manual_entry():
    result = InBodyOcrService(FakeClient(["not JSON"])).extract([PreparedImage(1, "a")])
    assert not result.extracted_fields
    assert result.warnings


def test_value_must_match_visible_text():
    result = InBodyOcrService(FakeClient([json.dumps({
        "weight_kg": {"value": 82.5, "raw_text": "72.5 kg"}
    })])).extract([PreparedImage(1, "a")])
    assert "weight_kg" in result.unresolved_fields


def test_local_ocr_environment_names_are_loaded(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("OCR_OLLAMA_MODEL", "test-vision")
    monkeypatch.setenv("OCR_OLLAMA_URL", "http://127.0.0.1:11434")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.ollama_model == "test-vision"
        assert settings.ollama_base_url == "http://127.0.0.1:11434"
    finally:
        get_settings.cache_clear()


def test_ollama_client_ignores_environment_proxy():
    client = OllamaClient(Settings(ollama_model="test-vision"))
    try:
        assert client.session.trust_env is False
    finally:
        client.session.close()

