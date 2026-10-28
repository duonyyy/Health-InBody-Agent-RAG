"""Module Phân đoạn Tài liệu Markdown Đa Cấp độ (Structure-Aware Markdown Chunker).

Vai trò:
    Hiện thực hóa chiến lược phân đoạn nâng cao (Advanced Chunking) chuẩn doanh nghiệp
    theo Chương 4 của Giáo trình RAG:
    1. Structure-Aware Splitting: Tôn trọng tuyệt đối phân cấp tiêu đề Markdown (#, ##, ###, ####).
    2. Contextual Breadcrumbs: Đính kèm cây gia phả nguồn (Tiêu đề > Chương > Mục) vào đầu mỗi chunk.
    3. Table-Aware Preservation: Bảo toàn cấu trúc bảng Markdown, tự động nhân bản Header và Delimiter row
       vào mọi sub-chunk khi bảng bị tràn kích thước.
    4. Parent-Child Tracking: Lưu vết khối cha (Parent Section ~1500-2500 ký tự) song song với chunk con
       (Child Chunk ~300-600 ký tự) phục vụ truy vấn Small-to-Big kèm Deduplication.
    5. Sentence Integrity: Cắt đoạn đệ quy theo ranh giới câu tự nhiên, tránh đứt gãy giữa câu.
    6. Idempotent Provenance: Sinh mã băm nội dung SHA-256 và chunk_id tất định.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .breadcrumbs import format_breadcrumb, inject_breadcrumb


def normalize_chunk_text(text: str) -> str:
    """Chuẩn hóa văn bản về Unicode NFC và làm sạch ký tự rác.

    Vai trò:
        Loại bỏ các ký tự tàng hình (Zero-Width Characters như \u200B-\u200D, \uFEFF)
        có nguy cơ làm vỡ Tokenizer của mô hình Embedding BGE-M3 (Chương 3.1 Giáo trình),
        đồng thời đồng nhất ngắt dòng (\r\n -> \n) và khoảng trắng thừa.

    Args:
        text: Chuỗi văn bản thô cần làm sạch.

    Returns:
        Văn bản đã chuẩn hóa Unicode NFC và được gọt sạch ký tự rác.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_text_by_separators(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """Chia nhỏ văn bản đệ quy dựa trên danh sách ký tự phân tách có thứ tự ưu tiên.

    Vai trò:
        Bảo toàn ranh giới ngữ nghĩa tự nhiên của câu (ưu tiên cắt ở đoạn văn `\n\n`,
        sau đó đến dòng `\n`, rồi đến dấu chấm câu `. `, dấu phẩy `, `).
        Hỗ trợ cửa sổ trượt (overlap) để giữ sự liên tục của ngữ mạch.

    Args:
        text: Đoạn văn bản cần chia nhỏ.
        chunk_size: Độ dài tối đa của một chunk (tính theo số ký tự).
        chunk_overlap: Độ dài đoạn gối đầu giữa 2 chunk kế tiếp.
        separators: Danh sách ký tự phân tách theo thứ tự ưu tiên giảm dần.

    Returns:
        Danh sách các mẩu văn bản sau khi chia nhỏ.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", "; ", ", ", " "]

    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chosen_separator = ""
    for separator in separators:
        if separator in text:
            chosen_separator = separator
            break

    if not chosen_separator:
        # Fallback về cắt cứng theo cửa sổ ký tự nếu không tìm thấy phân tách
        chunks = []
        step = max(1, chunk_size - chunk_overlap)
        for i in range(0, len(text), step):
            sub = text[i : i + chunk_size].strip()
            if sub:
                chunks.append(sub)
        return chunks

    splits = text.split(chosen_separator)
    remaining_separators = [s for s in separators if s != chosen_separator]

    merged_chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for split in splits:
        split_len = len(split)
        join_len = len(chosen_separator) if current_chunk else 0

        if current_length + join_len + split_len <= chunk_size:
            current_chunk.append(split)
            current_length += join_len + split_len
        else:
            if current_chunk:
                merged = chosen_separator.join(current_chunk).strip()
                if merged:
                    merged_chunks.append(merged)
                # Tính toán cửa sổ gối đầu (overlap window)
                overlap_chunk: List[str] = []
                overlap_length = 0
                for item in reversed(current_chunk):
                    if overlap_length + len(item) + len(chosen_separator) <= chunk_overlap:
                        overlap_chunk.insert(0, item)
                        overlap_length += len(item) + len(chosen_separator)
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = overlap_length

            # Nếu một phần tử đơn lẻ vượt quá chunk_size, tiếp tục đệ quy với separator mịn hơn
            if split_len > chunk_size and remaining_separators:
                sub_chunks = split_text_by_separators(
                    split, chunk_size, chunk_overlap, remaining_separators
                )
                merged_chunks.extend(sub_chunks)
                current_chunk = []
                current_length = 0
            else:
                current_chunk.append(split)
                current_length += (len(chosen_separator) if len(current_chunk) > 1 else 0) + split_len

    if current_chunk:
        merged = chosen_separator.join(current_chunk).strip()
        if merged:
            merged_chunks.append(merged)

    return merged_chunks


def is_table_separator(line: str) -> bool:
    """Kiểm tra một dòng có phải là dòng phân cách cột của bảng Markdown (|---|---|).

    Vai trò:
        Nhận diện chính xác cú pháp phân cách tiêu đề bảng chuẩn GFM (GitHub Flavored Markdown),
        bao gồm cả các định dạng căn lề trái/phải/giữa (:---, ---:, :---:).

    Args:
        line: Dòng văn bản cần kiểm tra.

    Returns:
        True nếu dòng là phân cách bảng hợp lệ, ngược lại False.
    """
    stripped = line.strip()
    if "|" not in stripped or "-" not in stripped:
        return False
    parts = [p.strip() for p in stripped.split("|")]
    if parts and not parts[0]:
        parts = parts[1:]
    if parts and not parts[-1]:
        parts = parts[:-1]
    if not parts:
        return False
    return all(bool(re.fullmatch(r":?-+:?", p)) for p in parts)


def extract_content_blocks(text: str) -> List[Tuple[str, str]]:
    """Tách văn bản section thành các khối xen kẽ gồm văn xuôi ('prose') và bảng biểu ('table').

    Vai trò:
        Cô lập các bảng Markdown ra khỏi các đoạn văn bình thường, ngăn ngừa thuật toán
        cắt xé vô tội vạ làm vỡ các hàng bảng dữ liệu dinh dưỡng/chỉ số.

    Args:
        text: Văn bản của một section cần phân lập.

    Returns:
        Danh sách các bộ tuple `(loại_khối, nội_dung_khối)` theo đúng thứ tự xuất hiện.
    """
    lines = text.splitlines()
    blocks: List[Tuple[str, str]] = []
    current_lines: List[str] = []
    current_type = "prose"

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Kiểm tra xem có bắt đầu một bảng Markdown tại vị trí i không
        if (
            i + 1 < len(lines)
            and stripped.startswith("|")
            and is_table_separator(lines[i + 1])
        ):
            # Lưu lại đoạn văn xuôi phía trước bảng nếu có
            if current_lines:
                prose_text = "\n".join(current_lines).strip()
                if prose_text:
                    blocks.append(("prose", prose_text))
                current_lines = []

            # Thu thập toàn bộ khối bảng Markdown
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1

            table_text = "\n".join(table_lines).strip()
            if table_text:
                blocks.append(("table", table_text))
            current_type = "prose"
            continue
        else:
            current_lines.append(line)
            i += 1

    if current_lines:
        prose_text = "\n".join(current_lines).strip()
        if prose_text:
            blocks.append(("prose", prose_text))

    return blocks


def split_markdown_table_with_header(
    table_text: str,
    chunk_size: int = 600,
    table_caption: Optional[str] = None,
) -> List[str]:
    """Chia nhỏ một bảng Markdown dài theo hàng, bảo toàn Header và Delimiter row ở mọi sub-chunk.

    Vai trò:
        Giải quyết triệt để lỗi "Mất tiêu đề cột" (Mục 3.3.2 Giáo trình RAG). Khi một bảng dinh dưỡng
        hoặc bảng khoảng BMI có nhiều hàng vượt quá `chunk_size`, hàm sẽ gom các hàng dữ liệu thành
        từng cụm vừa vặn và tự động gắn lại dòng Header cột và Delimiter row vào đầu mỗi sub-chunk.

    Args:
        table_text: Toàn bộ chuỗi văn bản của bảng Markdown.
        chunk_size: Kích thước tối đa cho mỗi sub-chunk bảng.
        table_caption: Tiêu đề hoặc chú giải của bảng xuất hiện ngay trước bảng (tùy chọn).

    Returns:
        Danh sách các sub-chunk bảng, mỗi sub-chunk đều là một bảng Markdown độc lập hoàn chỉnh.
    """
    lines = [line.strip() for line in table_text.strip().splitlines() if line.strip()]
    if len(lines) < 3:
        return [table_text]

    header_line = lines[0]
    separator_line = lines[1]
    if not is_table_separator(separator_line):
        return [table_text]

    prefix_parts = []
    if table_caption and table_caption.strip():
        prefix_parts.append(table_caption.strip())
    prefix_parts.append(header_line)
    prefix_parts.append(separator_line)
    table_header_prefix = "\n".join(prefix_parts)

    header_len = len(table_header_prefix) + 1  # tính cả newline

    data_rows = lines[2:]
    table_chunks: List[str] = []
    current_rows: List[str] = []
    current_len = header_len

    for row in data_rows:
        row_len = len(row) + 1
        if current_rows and (current_len + row_len > chunk_size):
            chunk_content = f"{table_header_prefix}\n" + "\n".join(current_rows)
            table_chunks.append(chunk_content)
            current_rows = [row]
            current_len = header_len + row_len
        else:
            current_rows.append(row)
            current_len += row_len

    if current_rows:
        chunk_content = f"{table_header_prefix}\n" + "\n".join(current_rows)
        table_chunks.append(chunk_content)

    return table_chunks


def split_section_content_table_aware(
    content: str,
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_length: int = 50,
) -> List[str]:
    """Phân đoạn nội dung một section có nhận biết cấu trúc bảng biểu Markdown.

    Vai trò:
        Điều phối quá trình băm: Đối với văn xuôi thì chia theo ranh giới câu đệ quy;
        đối với bảng biểu thì chia theo từng hàng bảo tồn header; tự động ghép các caption
        ngắn vào đầu bảng biểu để không bị rơi rụng thông tin.

    Args:
        content: Nội dung của section cần băm.
        chunk_size: Độ dài tối đa của chunk (ký tự).
        chunk_overlap: Độ dài gối đầu giữa các đoạn văn xuôi (ký tự).
        min_chunk_length: Ngưỡng độ dài tối thiểu để xem xét một đoạn là caption hay khối riêng.

    Returns:
        Danh sách các đoạn văn bản/bảng biểu đã được tối ưu hóa.
    """
    blocks = extract_content_blocks(content)
    if not blocks:
        return []

    # Nếu toàn bộ nội dung chỉ là văn xuôi thông thường
    if len(blocks) == 1 and blocks[0][0] == "prose":
        return split_text_by_separators(content, chunk_size, chunk_overlap)

    final_chunks: List[str] = []
    pending_caption: Optional[str] = None

    for idx, (b_type, b_content) in enumerate(blocks):
        if b_type == "prose":
            # Kiểm tra xem đoạn văn xuôi này có phải là caption đứng ngay trước bảng không
            next_is_table = (idx + 1 < len(blocks)) and (blocks[idx + 1][0] == "table")
            if next_is_table and len(b_content) < min_chunk_length * 2:
                pending_caption = b_content
                continue

            if len(b_content) <= chunk_size:
                final_chunks.append(b_content)
            else:
                sub_splits = split_text_by_separators(b_content, chunk_size, chunk_overlap)
                final_chunks.extend(sub_splits)
        elif b_type == "table":
            if len(b_content) <= chunk_size and not pending_caption:
                final_chunks.append(b_content)
            else:
                table_chunks = split_markdown_table_with_header(
                    b_content,
                    chunk_size=chunk_size,
                    table_caption=pending_caption,
                )
                final_chunks.extend(table_chunks)
            pending_caption = None

    return final_chunks


def parse_markdown_sections(text: str) -> List[Tuple[List[str], str]]:
    """Phân tích cú pháp văn bản Markdown thành danh sách các section kèm cây phân cấp tiêu đề.

    Vai trò:
        Duyệt qua các dòng văn bản, nhận diện các tiêu đề H1-H4 (`#`, `##`, `###`, `####`),
        và duy trì ngăn xếp (stack) phân cấp cha-con chính xác:
        H1 resets stack -> [H1]
        H2 -> [H1, H2]
        H3 -> [H1, H2, H3]

    Args:
        text: Toàn bộ nội dung văn bản Markdown gốc.

    Returns:
        Danh sách các bộ tuple `(ngăn_xếp_tiêu_đề_cha_con, nội_dung_mục)`.
    """
    lines = text.splitlines()
    sections: List[Tuple[List[str], str]] = []
    current_hierarchy: List[str] = []
    current_lines: List[str] = []

    header_pattern = re.compile(r"^(#{1,4})\s+(.+)$")

    for line in lines:
        match = header_pattern.match(line.strip())
        if match:
            # Lưu lại nội dung đã tích lũy trước tiêu đề mới
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((list(current_hierarchy), content))
                current_lines = []

            level = len(match.group(1))
            header_title = match.group(2).strip()

            current_hierarchy = current_hierarchy[: level - 1]
            current_hierarchy.append(header_title)
            current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((list(current_hierarchy), content))

    return sections


def chunk_document(
    doc: Dict[str, Any],
    chunk_size: int = 600,
    chunk_overlap: int = 80,
    min_chunk_length: int = 50,
) -> List[Dict[str, Any]]:
    """Phân đoạn toàn diện một tài liệu thành các chunks kèm Contextual Breadcrumbs và Parent-Child Metadata.

    Vai trò:
        Hàm trung tâm của Ingestion Pipeline. Nhận đầu vào là một bản ghi tài liệu chuẩn hóa
        (thuộc 5 domain types: inbody_metric, nutrition, exercise, medical_safety, general_health),
        thực hiện bóc tách tiêu đề, bảo toàn bảng, gắn vụn bánh mì ngữ cảnh, liên kết khối cha (Parent),
        và sinh định danh tất định (idempotent chunk_id & SHA-256 content_hash) sẵn sàng nạp vào Qdrant và BM25.

    Args:
        doc: Dictionary chứa thông tin tài liệu gốc (`doc_id`, `title`, `content`, `source`, `content_type`...).
        chunk_size: Kích thước mục tiêu tối đa cho mỗi chunk (mặc định 600 ký tự).
        chunk_overlap: Độ dài gối đầu giữa các chunk (mặc định 80 ký tự).
        min_chunk_length: Độ dài tối thiểu để giữ lại một chunk (loại bỏ các chunk rác).

    Returns:
        Danh sách các dictionary chunk đã được làm giàu siêu dữ liệu hoàn chỉnh.
    """
    doc_id = str(doc.get("doc_id") or doc.get("id") or "doc")
    title = str(doc.get("title") or doc.get("question") or "Untitled Document")
    content = normalize_chunk_text(str(doc.get("content") or ""))
    source = str(doc.get("source") or "internal")
    content_type = str(doc.get("content_type") or "general_health")
    domain = str(doc.get("domain") or "health_inbody")
    language = str(doc.get("language") or "vi")
    parent_metadata = dict(doc.get("metadata") or {})

    if not content or len(content) < min_chunk_length:
        return []

    has_markdown_headers = bool(re.search(r"^#{1,3}\s+", content, re.MULTILINE))

    # (raw_text, breadcrumb, section_title, parent_id, parent_title, parent_content)
    raw_chunks: List[Tuple[str, str, Optional[str], str, str, str]] = []

    if has_markdown_headers:
        sections = parse_markdown_sections(content)
        for p_idx, (hierarchy, section_content) in enumerate(sections, start=1):
            breadcrumb = format_breadcrumb(title, hierarchy)
            section_title = hierarchy[-1] if hierarchy else title
            parent_id = f"{doc_id}-parent-{p_idx:03d}"
            parent_title = section_title
            parent_content = inject_breadcrumb(section_content, breadcrumb)

            clean_check = re.sub(r"\[PAGE\s+\d+\]", "", section_content).strip()
            if len(clean_check) < min_chunk_length:
                continue

            # Kiểm tra nếu toàn bộ section nằm trọn trong 1 chunk
            if len(section_content) <= chunk_size:
                raw_chunks.append(
                    (section_content, breadcrumb, section_title, parent_id, parent_title, parent_content)
                )
            else:
                # Tách khối có nhận diện bảng biểu cho section dài
                sub_splits = split_section_content_table_aware(
                    section_content, chunk_size, chunk_overlap, min_chunk_length
                )
                for sub in sub_splits:
                    clean_sub = re.sub(r"\[PAGE\s+\d+\]", "", sub).strip()
                    if len(clean_sub) >= min_chunk_length:
                        raw_chunks.append(
                            (sub, breadcrumb, section_title, parent_id, parent_title, parent_content)
                        )
    else:
        # Tài liệu không có tiêu đề phân cấp (Seed câu hỏi, ghi chú lâm sàng ngắn)
        clean_check = re.sub(r"\[PAGE\s+\d+\]", "", content).strip()
        if len(clean_check) < min_chunk_length:
            return []

        breadcrumb = format_breadcrumb(title)
        parent_id = f"{doc_id}-parent-001"
        parent_title = title
        parent_content = inject_breadcrumb(content, breadcrumb)

        if len(content) <= chunk_size:
            raw_chunks.append((content, breadcrumb, title, parent_id, parent_title, parent_content))
        else:
            sub_splits = split_section_content_table_aware(
                content, chunk_size, chunk_overlap, min_chunk_length
            )
            for sub in sub_splits:
                clean_sub = re.sub(r"\[PAGE\s+\d+\]", "", sub).strip()
                if len(clean_sub) >= min_chunk_length:
                    raw_chunks.append((sub, breadcrumb, title, parent_id, parent_title, parent_content))

    # Đóng gói danh sách chunks chuẩn hóa
    total_chunks = len(raw_chunks)
    final_chunks: List[Dict[str, Any]] = []

    for index, (raw_text, breadcrumb, section_title, parent_id, parent_title, parent_content) in enumerate(
        raw_chunks, start=1
    ):
        chunk_id = f"{doc_id}-chunk-{index:03d}"
        injected_content = inject_breadcrumb(raw_text, breadcrumb)
        content_hash = hashlib.sha256(injected_content.encode("utf-8")).hexdigest()

        final_chunks.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "parent_id": parent_id,
                "parent_title": parent_title,
                "parent_content": parent_content,
                "has_parent": True,
                "title": section_title or title,
                "breadcrumb": breadcrumb,
                "content": injected_content,
                "raw_content": raw_text,
                "source": source,
                "content_type": content_type,
                "domain": domain,
                "language": language,
                "chunk_index": index,
                "chunk_count": total_chunks,
                "chunk_length": len(injected_content),
                "content_hash": content_hash,
                "metadata": {
                    **parent_metadata,
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "parent_id": parent_id,
                    "parent_title": parent_title,
                    "parent_content": parent_content,
                    "has_parent": True,
                    "breadcrumb": breadcrumb,
                    "section_title": section_title,
                    "chunk_index": index,
                    "chunk_count": total_chunks,
                    "chunk_length": len(injected_content),
                    "content_hash": content_hash,
                    "content_type": content_type,
                    "domain": domain,
                },
            }
        )

    return final_chunks
