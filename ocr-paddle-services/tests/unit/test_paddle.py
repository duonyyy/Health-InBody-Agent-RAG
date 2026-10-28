import io
from PIL import Image

from inbody_ocr.clients.paddle import OcrLine, PaddleOcrReader


def test_ocr_line_spatial_properties():
    line = OcrLine(
        text="Sample",
        confidence=0.9,
        bbox=[[15.0, 30.0], [45.0, 30.0], [45.0, 50.0], [15.0, 50.0]],
    )
    assert line.left_x == 15.0
    assert line.top_y == 30.0


def test_ocr_line_empty_bbox_safe():
    line = OcrLine(text="", confidence=0.0, bbox=[])
    assert line.left_x == 0.0
    assert line.top_y == 0.0


def test_paddle_reader_with_mock_engine():
    class MockEngine:
        def ocr(self, _img_np, cls=True):
            return [
                [
                    [[[10, 20], [50, 20], [50, 40], [10, 40]], ("Weight", 0.95)],
                    [[[60, 20], [100, 20], [100, 40], [60, 40]], ("72.0 kg", 0.92)],
                    [[[0, 0], [10, 0], [10, 10], [0, 10]], ("noise", 0.20)],  # Low confidence
                ]
            ]

    reader = PaddleOcrReader(min_confidence=0.5, engine=MockEngine())
    assert reader.is_available() is True

    img = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    lines = reader.read(buffer.getvalue())
    assert len(lines) == 2
    assert lines[0].text == "Weight"
    assert lines[1].text == "72.0 kg"


def test_paddle_reader_empty_bytes_returns_empty():
    reader = PaddleOcrReader(min_confidence=0.5, engine=object())
    assert reader.read(b"") == []
