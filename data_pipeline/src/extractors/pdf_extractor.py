"""Module Bóc tách và Chuyển đổi PDF sang Markdown Cấu trúc Cao (PDF to Markdown Extractor).

Vai trò:
    Sử dụng PyMuPDF (`fitz`) để trích xuất văn bản từ các tài liệu PDF nguồn (sách giáo trình thể hình,
    bảng thành phần thực phẩm Bộ Y tế 2007).
    Tích hợp các giải thuật xử lý tiếng Việt chuyên sâu theo Chương 3 Giáo trình RAG:
    1. Hàn gắn khoảng trắng kerning (Smart Kerning Spacing) tránh dính chữ tiếng Việt.
    2. Chuyển đổi bảng mã TCVN3 (.VnArial) sang Unicode chuẩn NFC.
    3. Nhận diện kích thước font và cờ đậm để tự động gán cấu trúc tiêu đề Markdown (#, ##, ###).
    4. Trích xuất bảng dinh dưỡng phức tạp thành cấu trúc bảng Markdown (`|---|---|`).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

logger = logging.getLogger(__name__)

# Bảng tra cứu chuyển đổi ký tự TCVN3 sang Unicode chuẩn NFC
TCVN3_MAP: Dict[str, str] = {
    '©': 'â', 'ª': 'ê', '«': 'ô', '¬': 'ơ', '®': 'đ', '§': 'Đ',
    'µ': 'à', '¸': 'á', '¶': 'ả', '·': 'ã', '¹': 'ạ',
    '¨': 'ă', '»': 'ằ', '¾': 'ắ', '¼': 'ẳ', '½': 'ẵ', 'Æ': 'ặ',
    'Ç': 'ầ', 'Ê': 'ấ', 'È': 'ẩ', 'É': 'ẫ', 'Ë': 'ậ',
    'Ì': 'è', 'Ð': 'é', 'Î': 'ẻ', 'Ï': 'ẽ', 'Ñ': 'ẹ',
    'Ò': 'ề', 'Õ': 'ế', 'Ó': 'ể', 'Ô': 'ễ', 'Ö': 'ệ',
    '×': 'ì', 'Ø': 'í', 'Ù': 'ỉ', 'Ú': 'ĩ', 'Û': 'ị', 'Þ': 'ị',
    'Ü': 'ò', 'Ý': 'ó', 'ß': 'õ', 'à': 'ọ',
    'á': 'ỏ', 'â': 'ổ', 'ã': 'ỗ', 'ä': 'ố', 'å': 'ộ',
    'æ': 'ờ', 'ç': 'ở', 'è': 'ố', 'é': 'ộ', 'ê': 'ờ',
    'ë': 'ở', 'ì': 'ỡ', 'î': 'ợ', 'ï': 'ụ', 'ñ': 'ủ',
    'ó': 'ú', 'ô': 'ự', 'õ': 'ỳ', 'ö': 'ỷ', '÷': 'ỹ',
    'ø': 'ứ', 'ù': 'ự', 'ú': 'ì', 'ü': 'ò', 'ý': 'ó',
    'μ': 'à', '−': 'ư',
}

FOOD_GROUPS: Dict[str, str] = {
    '1': 'Ngũ cốc và sản phẩm chế biến',
    '2': 'Khoai củ và sản phẩm chế biến',
    '3': 'Hạt, quả giàu đạm, béo và sản phẩm chế biến',
    '4': 'Rau, củ, quả dùng làm rau',
    '5': 'Quả chín',
    '6': 'Dầu, mỡ, bơ',
    '7': 'Thịt và sản phẩm chế biến',
    '8': 'Thủy sản và sản phẩm chế biến',
    '9': 'Trứng và sản phẩm chế biến',
    '10': 'Sữa và sản phẩm chế biến',
    '11': 'Đồ hộp',
    '12': 'Đồ ngọt (đường, bánh kẹo...)',
    '13': 'Gia vị, nước chấm',
    '14': 'Nước giải khát, bia rượu',
}


def decode_tcvn3(text: str) -> str:
    """Chuyển chuỗi ký tự TCVN3 (ABC) sang Unicode dựng sẵn chuẩn NFC.

    Vai trò:
        Giải mã các văn bản tiếng Việt cũ được gõ bằng font .VnTime, .VnArial
        (thường gặp trong các tài liệu y tế, dinh dưỡng xuất bản trước năm 2010),
        đảm bảo mô hình Embedding và BM25 đọc hiểu chính xác 100%.

    Args:
        text: Chuỗi văn bản mã hóa TCVN3.

    Returns:
        Chuỗi văn bản Unicode chuẩn NFC.
    """
    if not text:
        return ''
    decoded = ''.join(TCVN3_MAP.get(c, c) for c in text)
    return unicodedata.normalize('NFC', decoded)


def get_food_group_name(ma_so: str) -> str:
    """Xác định tên phân nhóm thực phẩm dựa trên mã số thực phẩm.

    Vai trò:
        Tra cứu hàng nghìn của mã số thực phẩm (ví dụ: mã 1015 -> nhóm 1: Ngũ cốc)
        để tự động bổ sung trường phân loại nhóm thực phẩm vào tài liệu.

    Args:
        ma_so: Chuỗi mã số thực phẩm (ví dụ: '1015', '7022').

    Returns:
        Tên nhóm thực phẩm tương ứng theo quy chuẩn Viện Dinh Dưỡng.
    """
    clean_code = re.sub(r'\D', '', ma_so)
    if not clean_code:
        return 'Thực phẩm thông dụng'
    val = int(clean_code)
    group_idx = str(val // 1000)
    return FOOD_GROUPS.get(group_idx, 'Thực phẩm thông dụng')


def extract_smart_lines(page: pymupdf.Page) -> List[Tuple[str, float, bool]]:
    """Trích xuất các dòng văn bản kèm thông tin kích thước font và cờ chữ đậm.

    Vai trò:
        Đọc các span văn bản trong từng khối (block), đo khoảng cách tọa độ (x0 - prev_x1)
        để tự động bù khoảng trắng cho các âm tiết tiếng Việt bị dính liền do lỗi kerning trong PDF,
        đồng thời ghi nhận kích thước font lớn nhất và trạng thái in đậm để phục vụ phân cấp tiêu đề.

    Args:
        page: Trang PDF cần xử lý từ PyMuPDF.

    Returns:
        Danh sách các bộ tuple: `(nội_dung_dòng, kích_thước_font, cờ_in_đậm)`.
    """
    d = page.get_text('dict')
    lines_out: List[Tuple[str, float, bool]] = []
    
    for b in d.get('blocks', []):
        if b.get('type') != 0:
            continue
        for line in b.get('lines', []):
            line_str = ''
            prev_x1 = None
            max_size = 0.0
            is_bold = False
            
            for s in line.get('spans', []):
                txt = s.get('text', '')
                if not txt:
                    continue
                x0, x1 = s['bbox'][0], s['bbox'][2]
                sz = float(s.get('size', 10.0))
                max_size = max(max_size, sz)
                
                font_name = s.get('font', '').lower()
                flags = s.get('flags', 0)
                if 'bold' in font_name or (flags & 2 != 0):
                    is_bold = True
                
                # Bù khoảng cách kerning nếu hai từ đứng cạnh nhau mà thiếu dấu cách
                if (prev_x1 is not None and (x0 - prev_x1) > sz * 0.15 
                        and not line_str.endswith(' ') and not txt.startswith(' ')):
                    line_str += ' '
                
                line_str += txt
                prev_x1 = x1
            
            st = line_str.strip()
            if st:
                lines_out.append((st, max_size, is_bold))
                
    return lines_out


def convert_fitness_to_markdown(pdf_path: Path, out_md_path: Path) -> dict[str, Any]:
    """Chuyển đổi giáo trình đào tạo thể hình (Fitness PDF) sang định dạng Markdown chuẩn.

    Vai trò:
        Tự động nhận diện cấu trúc phân cấp bài giảng:
        - Tiêu đề cấp 1 (#): Kích thước font >= 22 hoặc tiêu đề MỤC LỤC.
        - Tiêu đề cấp 2 (##): Chữ đậm font >= 15.
        - Tiêu đề cấp 3 (###): Chữ đậm font >= 12 hoặc bắt đầu bằng CHƯƠNG, PHẦN, số thứ tự.
        - Danh sách gạch đầu dòng (-): Chuẩn hóa các ký tự bullet `•`, `–` thành `- `.
        - Đánh dấu trang rõ ràng: `[PAGE n]`.

    Args:
        pdf_path: Đường dẫn tới file PDF thể hình nguồn.
        out_md_path: Đường dẫn file Markdown đầu ra.

    Returns:
        Dictionary thống kê số trang, đường dẫn và số lượng ký tự trích xuất.
    """
    doc = pymupdf.open(pdf_path)
    page_count = len(doc)
    markdown_pages: List[str] = []
    
    for page_idx in range(page_count):
        page = doc[page_idx]
        lines = extract_smart_lines(page)
        page_num = page_idx + 1
        
        md_lines: List[str] = [f'[PAGE {page_num}]']
        
        for text, size, is_bold in lines:
            if re.fullmatch(r'\d{1,3}', text):
                continue
            if text in ['Tài liệu lưu hành nội bộ']:
                continue
            
            if size >= 22.0 or (is_bold and size >= 18.0) or text.startswith('MỤC LỤC'):
                md_lines.append(f'\n# {text}\n')
            elif is_bold and size >= 15.0:
                md_lines.append(f'\n## {text}\n')
            elif (is_bold and size >= 12.0) or re.match(r'^(CHƯƠNG|PHẦN|\d+\.)\s+[A-ZÀ-Ỹ]', text):
                md_lines.append(f'\n### {text}\n')
            elif text.startswith('•') or text.startswith('–') or text.startswith('- '):
                clean_bullet = re.sub(r'^[•–\-]\s*', '', text)
                md_lines.append(f'- {clean_bullet}')
            elif re.match(r'^[a-z]\.\s+', text):
                md_lines.append(f'\n**{text}**')
            else:
                md_lines.append(text)
        
        page_content = '\n'.join(md_lines).strip()
        markdown_pages.append(page_content)
    
    full_markdown = '\n\n'.join(markdown_pages)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(full_markdown, encoding='utf-8')
    
    # Đồng thời lưu file .txt để tương thích với các script cũ
    txt_path = out_md_path.with_suffix('.txt')
    txt_path.write_text(full_markdown, encoding='utf-8')
    
    return {
        "pdf_name": pdf_path.name,
        "pages": page_count,
        "output_path": str(out_md_path),
        "characters": len(full_markdown),
    }


def parse_food_table(page: pymupdf.Page) -> List[Tuple[str, str, str]]:
    """Trích xuất cấu trúc bảng dưỡng chất 2 cột từ trang PDF thành danh sách các bộ 3 thông số.

    Vai trò:
        Nhận diện và trích xuất bảng dinh dưỡng từ trang PDF (thường gồm 2 bảng con đặt song song:
        bên trái là dưỡng chất đa lượng, bên phải là vi lượng/khoáng chất).
        Tự động giải mã tên chất từ TCVN3 sang Unicode NFC và tách đơn vị/hàm lượng tương ứng.

    Args:
        page: Trang PDF chứa bảng thành phần thực phẩm.

    Returns:
        Danh sách các bộ tuple `(tên_chất_dinh_dưỡng, đơn_vị, hàm_lượng)`.
    """
    nutrients: List[Tuple[str, str, str]] = []
    tables = page.find_tables()
    if not tables.tables:
        return nutrients
    
    t = tables.tables[0]
    extracted = t.extract()
    if len(extracted) < 2:
        return nutrients
    
    for row in extracted[1:]:
        if row[0] and len(row) > 2 and row[2]:
            names = [decode_tcvn3(n.strip()) for n in str(row[0]).split('\n') if n.strip()]
            units = [u.strip() for u in (str(row[1]) if len(row) > 1 and row[1] else '').split('\n') if u.strip()]
            values = [v.strip() for v in str(row[2]).split('\n') if v.strip()]
            
            if 'Năng lượng (Energy )' in names and 'KCal' in units and 'KJ' in units:
                idx = names.index('Năng lượng (Energy )')
                names.insert(idx + 1, 'Năng lượng KJ (Energy KJ)')
                
            for i, val in enumerate(values):
                if val and val != '-':
                    n_name = names[i] if i < len(names) else f'Chất dinh dưỡng {i+1}'
                    n_unit = units[i] if i < len(units) else ''
                    nutrients.append((n_name, n_unit, val))
        
        if len(row) > 6 and row[4] and row[6]:
            names = [decode_tcvn3(n.strip()) for n in str(row[4]).split('\n') if n.strip()]
            units = [u.strip() for u in (str(row[5]) if row[5] else '').split('\n') if u.strip()]
            values = [v.strip() for v in str(row[6]).split('\n') if v.strip()]
            
            for i, val in enumerate(values):
                if val and val != '-':
                    n_name = names[i] if i < len(names) else f'Chất vi lượng {i+1}'
                    n_unit = units[i] if i < len(units) else ''
                    nutrients.append((n_name, n_unit, val))
                    
    return nutrients


def convert_food_composition_to_markdown(pdf_path: Path, out_md_path: Path) -> dict[str, Any]:
    """Chuyển đổi Bảng Thành Phần Thực Phẩm Việt Nam PDF sang Markdown thẻ thực phẩm chuẩn.

    Vai trò:
        Duyệt qua từng trang PDF của cuốn Bảng thành phần thực phẩm:
        - Bóc tách mã số thực phẩm, tên tiếng Việt, tên tiếng Anh, tỷ lệ thải bỏ.
        - Gán nhóm thực phẩm theo mã số.
        - Chuyển đổi toàn bộ dưỡng chất thành Markdown Table hoàn chỉnh có tiêu đề cột rõ ràng.

    Args:
        pdf_path: Đường dẫn file PDF Bảng thành phần thực phẩm.
        out_md_path: Đường dẫn file Markdown kết quả.

    Returns:
        Dictionary thống kê số trang, số món ăn bóc tách được và số lượng ký tự.
    """
    doc = pymupdf.open(pdf_path)
    page_count = len(doc)
    markdown_pages: List[str] = []
    food_count = 0
    
    for page_idx in range(page_count):
        page = doc[page_idx]
        page_num = page_idx + 1
        txt = page.get_text('text')
        lines = [l.strip() for l in txt.split('\n') if l.strip()]
        
        stt = ''
        ma_so = ''
        thai_bo = '0.0'
        ten_vi = ''
        ten_en = ''
        
        for i, l in enumerate(lines):
            if l.startswith('STT:'):
                stt = lines[i+1] if i+1 < len(lines) else ''
            if 'M· sè' in l or 'Mã số' in l:
                ma_so = lines[i+1] if i+1 < len(lines) else ''
            if 'Th¶i bá' in l or 'Thải bỏ' in l:
                m = re.search(r'([\d\.]+)', l)
                if m:
                    thai_bo = m.group(1)
            if 'Tªn thùc phÈm' in l and i+1 < len(lines):
                ten_vi = decode_tcvn3(lines[i+1])
            if 'Tªn tiÕng Anh' in l and i+1 < len(lines):
                ten_en = lines[i+1]
        
        nutrients = parse_food_table(page)
        
        if nutrients and (ten_vi or ma_so):
            food_count += 1
            group_name = get_food_group_name(ma_so)
            title_display = f'{ten_vi} ({ten_en})' if ten_en else ten_vi
            if not title_display:
                title_display = f'Thực phẩm mã số {ma_so}'
                
            md_card = [
                f'[PAGE {page_num}]',
                f'# {title_display} - Mã số {ma_so}',
                '',
                f'- **Tên tiếng Việt**: {ten_vi or "Đang cập nhật"}',
                f'- **Tên tiếng Anh**: {ten_en or "-"}',
                f'- **Mã số thực phẩm**: {ma_so} (STT: {stt or "-"})',
                f'- **Nhóm thực phẩm**: {group_name}',
                f'- **Tỷ lệ thải bỏ**: {thai_bo}%',
                '- **Quy chuẩn**: Bảng thành phần thực phẩm Việt Nam (Viện Dinh dưỡng - Bộ Y tế, 2007)',
                '',
                '### Thành phần dinh dưỡng trong 100g phần ăn được:',
                '| Thành phần dinh dưỡng | Đơn vị | Hàm lượng |',
                '|---|---|---|',
            ]
            for n_name, n_unit, n_val in nutrients:
                md_card.append(f'| {n_name} | {n_unit} | {n_val} |')
                
            markdown_pages.append('\n'.join(md_card))
        else:
            decoded_text = decode_tcvn3(txt)
            clean_lines = [l.strip() for l in decoded_text.split('\n') if l.strip()]
            page_text = '\n'.join(clean_lines)
            if len(page_text) >= 40:
                markdown_pages.append(f'[PAGE {page_num}]\n{page_text}')
    
    full_markdown = '\n\n'.join(markdown_pages)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(full_markdown, encoding='utf-8')
    
    txt_path = out_md_path.with_suffix('.txt')
    txt_path.write_text(full_markdown, encoding='utf-8')
    
    return {
        "pdf_name": pdf_path.name,
        "pages": page_count,
        "food_count": food_count,
        "output_path": str(out_md_path),
        "characters": len(full_markdown),
    }


def extract_pdf_to_markdown(raw_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Điều phối toàn bộ quá trình trích xuất các nguồn tài liệu PDF trong `source_manifest.json`.

    Vai trò:
        Hàm chính của Giai đoạn 1 (Stage 1 - Extract): Đọc file manifest, lọc các nguồn PDF đang kích hoạt,
        phân loại loại tài liệu (thể hình hay dinh dưỡng) và chuyển đổi đồng loạt sang các file Markdown
        cấu trúc tại `dataset/processed/extracted_text/`.

    Args:
        raw_dir: Thư mục chứa dữ liệu thô (`dataset/raw/`).
        output_dir: Thư mục đích lưu các file Markdown đã bóc tách (`dataset/processed/extracted_text/`).

    Returns:
        Dictionary báo cáo trạng thái và danh sách các nguồn tài liệu đã bóc tách thành công.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "source_manifest.json"
    results: list[dict[str, Any]] = []
    
    if not manifest_path.exists():
        return {"status": "error", "message": "source_manifest.json not found"}
        
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for source in manifest.get("sources", []):
        if source.get("format") != "pdf":
            continue
        status = source.get("status")
        if status in ("empty", "excluded_from_rag"):
            continue
            
        pdf_path = raw_dir / source["path"]
        if not pdf_path.exists():
            continue
            
        source_id = source["source_id"]
        out_md_path = output_dir / f"{source_id}.md"
        
        if "fitness" in source_id or "fitness" in str(pdf_path).lower():
            info = convert_fitness_to_markdown(pdf_path, out_md_path)
            results.append({"source_id": source_id, **info})
        elif "food" in source_id or "vtn" in source_id.lower() or "fct" in str(pdf_path).lower():
            info = convert_food_composition_to_markdown(pdf_path, out_md_path)
            results.append({"source_id": source_id, **info})
            
    return {
        "status": "ok",
        "extracted_sources": results,
    }
