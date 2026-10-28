import json
from types import SimpleNamespace

from inbody_ocr.clients.ollama import OllamaClient
from inbody_ocr.clients.paddle import OcrLine
from inbody_ocr.config import Settings, get_settings
from inbody_ocr.imaging.preprocess import PreparedImage
from inbody_ocr.inbody.extractor import InBodyOcrService


class FakePaddle:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def read(self, _bytes):
        return next(self.outputs)


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.settings = SimpleNamespace(ocr_num_predict=800)

    def generate(self, **_kwargs):
        return next(self.outputs)


def test_two_stage_extraction_success():
    paddle = FakePaddle([
        [
            OcrLine("Cân nặng", 0.95, [[10, 10], [50, 10], [50, 30], [10, 30]]),
            OcrLine("72.5 kg", 0.98, [[60, 10], [110, 10], [110, 30], [60, 30]]),
        ]
    ])
    llm = FakeLLM([
        json.dumps({
            "weight_kg": {"value": 72.5, "raw_text": "72.5 kg"},
            "height_cm": {"value": None, "raw_text": ""},
        })
    ])

    service = InBodyOcrService(paddle=paddle, llm=llm)
    result = service.extract([PreparedImage(page_number=1, image_base64="a", image_bytes=b"dummy")])

    assert result.status == "needs_confirmation"
    assert result.parser_version == "inbody-paddle-v1"
    assert result.extracted_fields["weight_kg"].value == 72.5
    assert "height_cm" in result.unresolved_fields


def test_value_must_match_visible_text():
    paddle = FakePaddle([
        [OcrLine("72.5 kg", 0.98, [[0, 0], [10, 0], [10, 10], [0, 10]])]
    ])
    # LLM hallucinated 82.5 while text was 72.5 kg
    llm = FakeLLM([
        json.dumps({"weight_kg": {"value": 82.5, "raw_text": "72.5 kg"}})
    ])

    service = InBodyOcrService(paddle=paddle, llm=llm)
    result = service.extract([PreparedImage(1, "a", b"bytes")])

    assert "weight_kg" in result.unresolved_fields


def test_invalid_and_conflicting_values_need_review():
    paddle = FakePaddle([
        [OcrLine("72", 0.9, [[0, 0], [10, 0], [10, 10], [0, 10]])],
        [OcrLine("82", 0.9, [[0, 0], [10, 0], [10, 10], [0, 10]])],
    ])
    llm = FakeLLM([
        json.dumps({
            "weight_kg": {"value": 72, "raw_text": "72"},
            "pbf_percent": {"value": 500, "raw_text": "500"},  # Over limit (max 80)
        }),
        json.dumps({"weight_kg": {"value": 82, "raw_text": "82"}}),  # Conflicting weight on page 2
    ])

    service = InBodyOcrService(paddle=paddle, llm=llm)
    result = service.extract([PreparedImage(1, "a", b"1"), PreparedImage(2, "b", b"2")])

    assert "weight_kg" not in result.extracted_fields
    assert "pbf_percent" not in result.extracted_fields
    assert result.warnings


def test_non_json_degrades_to_manual_entry():
    paddle = FakePaddle([[OcrLine("Text", 0.9, [[0, 0], [10, 0], [10, 10], [0, 10]])]])
    llm = FakeLLM(["not JSON"])

    service = InBodyOcrService(paddle=paddle, llm=llm)
    result = service.extract([PreparedImage(1, "a", b"1")])

    assert not result.extracted_fields
    assert result.warnings


def test_paddle_finds_no_text_adds_warning():
    paddle = FakePaddle([[]])  # No text detected
    llm = FakeLLM([])

    service = InBodyOcrService(paddle=paddle, llm=llm)
    result = service.extract([PreparedImage(1, "a", b"1")])

    assert not result.extracted_fields
    assert any("không phát hiện chữ" in w for w in result.warnings)


def test_local_ocr_environment_names_are_loaded(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("OCR_OLLAMA_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("OCR_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("PADDLE_LANG", "ch")
    monkeypatch.setenv("PADDLE_USE_GPU", "false")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.ollama_model == "qwen2.5:7b"
        assert settings.ollama_base_url == "http://127.0.0.1:11434"
        assert settings.paddle_lang == "ch"
        assert settings.paddle_use_gpu is False
    finally:
        get_settings.cache_clear()


def test_ollama_client_ignores_environment_proxy():
    client = OllamaClient(Settings(ollama_model="test-model"))
    try:
        assert client.session.trust_env is False
    finally:
        client.session.close()
