"""Module Xây dựng Ngữ cảnh Nguồn Phân cấp (Contextual Breadcrumbs) cho RAG Chunks.

Vai trò:
    Đảm bảo mỗi chunk dữ liệu khi được trích xuất độc lập trong quá trình truy vấn
    vẫn bảo lưu đầy đủ ngữ cảnh nguồn gốc phân cấp (Tiêu đề tài liệu > Chương > Mục > Tiểu mục).
    Ngăn chặn triệt để hiện tượng đứt gãy ngữ nghĩa (Context Fragmentation) và mất gốc
    tham chiếu theo chuẩn Mục 3.2 và Mục 4.1.3 trong Giáo trình RAG.
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional


def format_breadcrumb(document_title: str, section_hierarchy: Optional[List[str]] = None) -> str:
    """Định dạng chuỗi vụn bánh mì ngữ cảnh (breadcrumb) chuẩn hóa phân cấp.

    Vai trò:
        Tạo chuỗi nhãn phân cấp bối cảnh từ tiêu đề tài liệu gốc và danh sách
        các cấp tiêu đề cha-con (H1 > H2 > H3), chuẩn hóa toàn bộ về Unicode NFC.

    Args:
        document_title: Tên hoặc tiêu đề chính của tài liệu gốc.
        section_hierarchy: Danh sách các cấp tiêu đề mục (tùy chọn).

    Returns:
        Chuỗi breadcrumb hoàn chỉnh bọc trong dấu ngoặc vuông.
        Ví dụ: `[Hướng dẫn chẩn đoán béo phì > Tiêu chuẩn BMI Châu Á]`
    """
    parts = [document_title.strip()]
    if section_hierarchy:
        for section in section_hierarchy:
            cleaned = section.strip().lstrip("#").strip()
            if cleaned and cleaned not in parts:
                parts.append(cleaned)

    breadcrumb_text = " > ".join(parts)
    breadcrumb_text = unicodedata.normalize("NFC", breadcrumb_text)
    return f"[{breadcrumb_text}]"


def inject_breadcrumb(content: str, breadcrumb: str) -> str:
    """Gắn vụn bánh mì ngữ cảnh vào đầu nội dung của chunk văn bản.

    Vai trò:
        Nối chuỗi breadcrumb vào dòng đầu tiên của chunk văn bản một cách sạch sẽ,
        đảm bảo mô hình Embedding (Bi-Encoder) và BM25 luôn nhận biết được bối cảnh
        nguồn của đoạn trích ngay cả khi đứng đơn lẻ.

    Args:
        content: Nội dung văn bản thô của chunk.
        breadcrumb: Chuỗi breadcrumb đã được format từ `format_breadcrumb`.

    Returns:
        Văn bản chunk đã được chèn breadcrumb ở dòng đầu tiên.
    """
    if not breadcrumb:
        return content.strip()
    return f"{breadcrumb}\n{content.strip()}"
