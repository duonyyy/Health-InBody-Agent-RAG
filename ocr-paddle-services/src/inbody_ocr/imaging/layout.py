"""Convert PaddleOCR detected lines to structured text for LLM parsing."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inbody_ocr.clients.paddle import OcrLine


def to_plain_text(lines: list[OcrLine], row_gap_px: int = 12, max_chars: int = 4000) -> str:
    """Group OcrLine objects into rows based on vertical proximity and sort left-to-right.

    Lines on the same horizontal line (|y2 - y1| <= row_gap_px) are joined with ' | '.
    Rows are joined with newlines, preserving table and column relationships.
    """
    if not lines:
        return ""

    # Sort initially by top-y, then left-x
    sorted_lines = sorted(lines, key=lambda l: (l.top_y, l.left_x))

    rows: list[list[OcrLine]] = []
    current_row: list[OcrLine] = [sorted_lines[0]]
    current_row_y = sorted_lines[0].top_y

    for line in sorted_lines[1:]:
        if abs(line.top_y - current_row_y) <= row_gap_px:
            current_row.append(line)
        else:
            rows.append(sorted(current_row, key=lambda l: l.left_x))
            current_row = [line]
            current_row_y = line.top_y

    if current_row:
        rows.append(sorted(current_row, key=lambda l: l.left_x))

    formatted_rows = ["  |  ".join(item.text for item in row) for row in rows]
    result = "\n".join(formatted_rows)
    return result[:max_chars]
