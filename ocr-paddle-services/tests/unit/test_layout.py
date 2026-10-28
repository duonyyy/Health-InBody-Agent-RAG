from inbody_ocr.clients.paddle import OcrLine
from inbody_ocr.imaging.layout import to_plain_text


def test_empty_lines_returns_empty_string():
    assert to_plain_text([]) == ""


def test_sorts_rows_top_to_bottom_and_columns_left_to_right():
    lines = [
        # Row 2 (y=100)
        OcrLine(text="72.5 kg", confidence=0.98, bbox=[[150, 100], [200, 100], [200, 120], [150, 120]]),
        OcrLine(text="Cân nặng", confidence=0.95, bbox=[[20, 102], [80, 102], [80, 122], [20, 122]]),
        # Row 1 (y=50)
        OcrLine(text="175.0 cm", confidence=0.99, bbox=[[150, 50], [210, 50], [210, 70], [150, 70]]),
        OcrLine(text="Chiều cao", confidence=0.96, bbox=[[20, 52], [90, 52], [90, 72], [20, 72]]),
    ]

    result = to_plain_text(lines, row_gap_px=10)
    lines_out = result.splitlines()

    assert len(lines_out) == 2
    assert lines_out[0] == "Chiều cao  |  175.0 cm"
    assert lines_out[1] == "Cân nặng  |  72.5 kg"


def test_max_chars_limits_output():
    lines = [
        OcrLine(text="Dòng chữ rất dài cần được giới hạn độ dài", confidence=0.9, bbox=[[0, 0], [10, 0], [10, 10], [0, 10]]),
    ]
    result = to_plain_text(lines, max_chars=10)
    assert len(result) == 10
