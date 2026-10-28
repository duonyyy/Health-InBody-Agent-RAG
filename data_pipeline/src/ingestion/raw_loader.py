"""Raw Data Ingestion Module (Stage 1 / Ingestion Layer).

Vai trò:
    Đọc, giải mã và hợp nhất toàn bộ các nguồn dữ liệu thô (CSV món ăn, CSV tương tác rating,
    JSON USDA Foundation Foods, thư mục tri thức y khoa InBody JSON, và văn bản trích xuất từ PDF)
    thành tệp bản ghi hợp nhất `all_raw_sources.jsonl` mà không làm thay đổi thư mục `dataset/raw/`.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

PROJECT_DOMAIN = "health_inbody"


def clean_text(value: Any) -> str:
    """Làm sạch và chuẩn hóa văn bản.

    Vai trò:
        Chuẩn hóa văn bản về Unicode NFC, loại bỏ ký tự ngắt dòng thừa và các ký tự
        điều khiển ẩn (zero-width characters) để đảm bảo chất lượng dữ liệu văn bản.

    Args:
        value: Giá trị văn bản đầu vào bất kỳ.

    Returns:
        Chuỗi văn bản đã làm sạch.
    """
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", text)
    return text


def compact_parts(parts: Iterable[str]) -> str:
    """Nối các đoạn văn bản thành một chuỗi duy nhất.

    Vai trò:
        Hợp nhất danh sách các trường thông tin (tên món, khẩu phần, mô tả, calo)
        bỏ qua các phần tử rỗng sau khi làm sạch.

    Args:
        parts: Tập hợp các đoạn văn bản chuỗi.

    Returns:
        Chuỗi kết hợp phân tách bằng dấu xuống dòng.
    """
    return "\n".join(part for part in (clean_text(part) for part in parts) if part)


def read_manifest(raw_dir: Path) -> dict[str, Any]:
    """Đọc tệp kê khai danh mục nguồn dữ liệu thô (source manifest).

    Vai trò:
        Nạp cấu hình danh sách các nguồn dữ liệu raw từ `source_manifest.json`
        để xác định định dạng, quyền hạn và trạng thái của từng tệp nguồn.

    Args:
        raw_dir: Thư mục chứa dữ liệu thô dataset/raw.

    Returns:
        Dict cấu hình manifest.
    """
    manifest_path = raw_dir / "source_manifest.json"
    with manifest_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def make_record(
    doc_id: str,
    title: str,
    content: str,
    source_id: str,
    content_type: str,
    language: str,
    pipeline_role: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tạo bản ghi dữ liệu chuẩn theo schema thống nhất của pipeline.

    Vai trò:
        Đóng gói thông tin văn bản, định danh, nguồn gốc và metadata theo cấu trúc
        chuẩn JSON của dự án trước khi lưu trữ vào processed dataset.

    Args:
        doc_id: Mã định danh tài liệu duy nhất.
        title: Tiêu đề tài liệu.
        content: Nội dung văn bản chi tiết.
        source_id: Mã định danh nguồn thu thập.
        content_type: Loại nội dung (nutrition, inbody_metric, exercise, medical_safety).
        language: Mã ngôn ngữ (vi, en).
        pipeline_role: Vai trò xử lý (rag_corpus, recommender, excluded_from_rag).
        metadata: Metadata bổ sung đính kèm.

    Returns:
        Dict bản ghi chuẩn hóa.
    """
    return {
        "doc_id": doc_id,
        "title": title,
        "content": content,
        "source": source_id,
        "content_type": content_type,
        "domain": PROJECT_DOMAIN,
        "language": language,
        "metadata": {
            "pipeline_role": pipeline_role,
            **(metadata or {}),
        },
    }


def merge_foods(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    """Chuyển đổi dữ liệu món ăn thô dạng CSV sang bản ghi chuẩn hóa.

    Vai trò:
        Đọc các tệp CSV chứa danh sách món ăn, chuẩn hóa thông tin dinh dưỡng
        (calories, fat, protein, carbs) và sinh các bản ghi JSONL có metadata chi tiết.

    Args:
        source: Bản ghi cấu hình nguồn từ manifest.
        raw_dir: Thư mục gốc chứa dữ liệu thô.

    Yields:
        Dict bản ghi tài liệu chuẩn hóa cho từng món ăn.
    """
    path = raw_dir / source["path"]
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            food_id = clean_text(row.get("food_id"))
            dish_name = clean_text(row.get("dish_name")) or f"Food {food_id}"
            nutrition = (
                f"Calories: {clean_text(row.get('calories'))} kcal; "
                f"fat: {clean_text(row.get('fat'))} g; "
                f"fiber: {clean_text(row.get('fiber'))} g; "
                f"sugar: {clean_text(row.get('sugar'))} g; "
                f"protein: {clean_text(row.get('protein'))} g."
            )
            content = compact_parts(
                [
                    f"Ten mon: {dish_name}",
                    f"Loai mon: {row.get('dish_type')}",
                    f"Khau phan: {row.get('serving_size')}",
                    f"Thoi gian nau: {row.get('cooking_time')} phut",
                    f"Mo ta: {row.get('description')}",
                    f"Nguyen lieu: {row.get('ingredients')}",
                    f"Cach nau: {row.get('cooking_method')}",
                    f"Tags: {row.get('dish_tags')}",
                    nutrition,
                ]
            )
            yield make_record(
                doc_id=f"foodrecordfinal_food_{food_id}",
                title=dish_name,
                content=content,
                source_id=source["source_id"],
                content_type=source["content_type"],
                language=source["language"],
                pipeline_role=source["pipeline_role"],
                metadata={
                    "raw_path": source["path"],
                    "food_id": food_id,
                    "dish_type": clean_text(row.get("dish_type")),
                    "image_link": clean_text(row.get("image_link")),
                    "nutrition": {
                        "calories": clean_text(row.get("calories")),
                        "fat_g": clean_text(row.get("fat")),
                        "fiber_g": clean_text(row.get("fiber")),
                        "sugar_g": clean_text(row.get("sugar")),
                        "protein_g": clean_text(row.get("protein")),
                    },
                    "raw_row": row,
                },
            )


def merge_ratings(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    """Chuyển đổi dữ liệu tương tác đánh giá món ăn của người dùng sang bản ghi JSONL.

    Vai trò:
        Nạp các lượt rating từ file CSV phục vụ các bài toán đề xuất (recommender),
        đánh dấu role phù hợp để lọc tách biệt khỏi RAG corpus.

    Args:
        source: Bản ghi cấu hình nguồn từ manifest.
        raw_dir: Thư mục chứa dữ liệu thô.

    Yields:
        Dict bản ghi đánh giá người dùng.
    """
    path = raw_dir / source["path"]
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            user_id = clean_text(row.get("userId"))
            food_id = clean_text(row.get("foodId"))
            rating = clean_text(row.get("rating"))
            yield make_record(
                doc_id=f"rating_{index:06d}",
                title=f"Rating user {user_id} food {food_id}",
                content=f"User {user_id} rated food {food_id} with score {rating}.",
                source_id=source["source_id"],
                content_type=source["content_type"],
                language=source["language"],
                pipeline_role=source["pipeline_role"],
                metadata={
                    "raw_path": source["path"],
                    "user_id": user_id,
                    "food_id": food_id,
                    "rating": rating,
                    "raw_row": row,
                },
            )


def nutrient_map(food: dict[str, Any]) -> dict[str, Any]:
    """Tạo từ điển ánh xạ thông tin dinh dưỡng từ đối tượng USDA food.

    Vai trò:
        Trích xuất và chuẩn hóa cặp giá trị (số lượng, đơn vị) của từng chất dinh dưỡng
        từ payload JSON phân cấp của USDA Foundation Foods.

    Args:
        food: Dict dữ liệu một loại thực phẩm của USDA.

    Returns:
        Dict tra cứu {tên_chất: {amount, unit}}.
    """
    nutrients: dict[str, Any] = {}
    for item in food.get("foodNutrients", []):
        nutrient = item.get("nutrient", {})
        name = clean_text(nutrient.get("name"))
        if not name:
            continue
        nutrients[name] = {
            "amount": item.get("amount"),
            "unit": nutrient.get("unitName"),
        }
    return nutrients


def merge_usda(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    """Chuyển đổi dữ liệu chuẩn USDA Foundation Foods sang bản ghi chuẩn hóa.

    Vai trò:
        Trích chọn các trường dinh dưỡng cốt lõi (Energy, Protein, Lipid, Fiber, Sugar)
        từ cơ sở dữ liệu USDA để làm giàu tri thức dinh dưỡng chuẩn quốc tế cho RAG.

    Args:
        source: Bản ghi cấu hình nguồn từ manifest.
        raw_dir: Thư mục chứa dữ liệu thô.

    Yields:
        Dict bản ghi tài liệu chuẩn hóa thực phẩm USDA.
    """
    path = raw_dir / source["path"]
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    for food in payload.get("FoundationFoods", []):
        if not isinstance(food, dict):
            continue
        fdc_id = food.get("fdcId")
        description = clean_text(food.get("description")) or f"USDA food {fdc_id}"
        category = clean_text((food.get("foodCategory") or {}).get("description"))
        nutrients = nutrient_map(food)
        selected_names = [
            "Energy",
            "Protein",
            "Total lipid (fat)",
            "Carbohydrate, by difference",
            "Carbohydrate, by summation",
            "Fiber, total dietary",
            "Sugars, Total",
            "Sodium, Na",
        ]
        selected = {
            name: nutrients[name]
            for name in selected_names
            if name in nutrients
        }
        nutrient_lines = [
            f"{name}: {value.get('amount')} {value.get('unit')}"
            for name, value in selected.items()
        ]
        content = compact_parts(
            [
                f"Food: {description}",
                f"Category: {category}",
                "Key nutrients: " + "; ".join(nutrient_lines) if nutrient_lines else "",
            ]
        )
        yield make_record(
            doc_id=f"usda_foundation_{fdc_id}",
            title=description,
            content=content,
            source_id=source["source_id"],
            content_type=source["content_type"],
            language=source["language"],
            pipeline_role=source["pipeline_role"],
            metadata={
                "raw_path": source["path"],
                "fdc_id": fdc_id,
                "category": category,
                "publication_date": food.get("publicationDate"),
                "nutrients": selected,
            },
        )


def merge_pdf_placeholder(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    """Xử lý nạp văn bản từ tệp PDF đã qua trích xuất hoặc tạo bản ghi chờ.

    Vai trò:
        Kiểm tra nội dung Markdown/văn bản đã được trích xuất trong thư mục `extracted_text`,
        phân tách theo từng trang `[PAGE n]` thành các tài liệu độc lập; nếu chưa trích xuất
        thì sinh bản ghi placeholder yêu cầu trích xuất trước khi đưa vào RAG.

    Args:
        source: Cấu hình nguồn PDF trong manifest.
        raw_dir: Thư mục chứa tệp PDF thô.

    Yields:
        Dict bản ghi tài liệu cho từng trang hoặc placeholder.
    """
    path = raw_dir / source["path"]
    if not path.exists():
        return
    processed_dir = raw_dir.parent / "processed"
    extracted_md_path = processed_dir / "extracted_text" / f"{source['source_id']}.md"
    extracted_txt_path = processed_dir / "extracted_text" / f"{source['source_id']}.txt"
    extracted_text_path = extracted_md_path if extracted_md_path.exists() else extracted_txt_path
    title = path.stem.replace("-", " ").replace("_", " ")
    if extracted_text_path.exists():
        content = extracted_text_path.read_text(encoding="utf-8").strip()
        if content:
            parts = re.split(r"(?:^|\n)\s*\[PAGE\s+(\d+)\]\s*\n", content)
            if parts and not parts[0].strip():
                parts = parts[1:]
            page_count = 0
            for index in range(0, len(parts), 2):
                page_number = clean_text(parts[index])
                page_text = clean_text(parts[index + 1] if index + 1 < len(parts) else "")
                if len(page_text) < 80:
                    continue
                page_count += 1
                yield make_record(
                    doc_id=f"{source['source_id']}_page_{int(page_number):04d}",
                    title=(
                        next((l.lstrip("# ").strip() for l in page_text.splitlines() if l.strip().startswith("# ")), None)
                        or f"{title} - trang {page_number}"
                    ),
                    content=page_text,
                    source_id=source["source_id"],
                    content_type=source["content_type"],
                    language=source["language"],
                    pipeline_role=source["pipeline_role"],
                    metadata={
                        "raw_path": source["path"],
                        "extracted_text_path": str(extracted_text_path.relative_to(raw_dir.parent)),
                        "file_size_bytes": path.stat().st_size,
                        "page_number": int(page_number),
                        "requires_text_extraction": False,
                    },
                )
            if page_count:
                return

            return

    yield make_record(
        doc_id=f"{source['source_id']}_pdf_pending",
        title=title,
        content=(
            f"PDF source at {source['path']} is available but has not been text-extracted yet. "
            "Extract text to dataset/processed/extracted_text before using it as RAG content."
        ),
        source_id=source["source_id"],
        content_type=source["content_type"],
        language=source["language"],
        pipeline_role=source["pipeline_role"],
        metadata={
            "raw_path": source["path"],
            "file_size_bytes": path.stat().st_size,
            "requires_text_extraction": True,
        },
    )


def merge_inbody_medical_knowledge(
    source: dict[str, Any], raw_dir: Path
) -> Iterable[dict[str, Any]]:
    """Hợp nhất các tài liệu tri thức y khoa và InBody từ tệp JSON.

    Vai trò:
        Quét toàn bộ tệp JSON tri thức chuyên gia trong thư mục nguồn, đọc từng tài liệu
        chuẩn y khoa và gán metadata về review status, tier và publisher.

    Args:
        source: Cấu hình nguồn tri thức y khoa trong manifest.
        raw_dir: Thư mục chứa dữ liệu thô.

    Yields:
        Dict bản ghi tài liệu y tế chuẩn hóa.
    """
    path = raw_dir / source["path"]
    if not path.exists():
        return
    for json_file in sorted(path.glob("*.json")):
        with json_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        default_publisher = clean_text(payload.get("publisher"))
        default_tier = clean_text(payload.get("source_tier"))
        default_url = clean_text(payload.get("source_url"))
        source_id = clean_text(payload.get("source_id")) or source["source_id"]

        for doc in payload.get("documents", []):
            doc_id = clean_text(doc.get("doc_id"))
            title = clean_text(doc.get("title"))
            content = clean_text(doc.get("content"))
            content_type = clean_text(doc.get("content_type")) or source.get("content_type", "inbody_metric")
            language = clean_text(doc.get("language")) or source.get("language", "vi")
            publisher = clean_text(doc.get("publisher")) or default_publisher
            source_tier = clean_text(doc.get("source_tier")) or default_tier
            source_url = clean_text(doc.get("source_url")) or default_url
            published_at = clean_text(doc.get("published_at"))
            reviewed_at = clean_text(doc.get("reviewed_at"))
            review_status = clean_text(doc.get("medical_review_status")) or "approved"

            metadata = {
                "raw_path": str((raw_dir / source["path"] / json_file.name).relative_to(raw_dir.parent)).replace("\\", "/"),
                "raw_file": json_file.name,
                "publisher": publisher,
                "source_tier": source_tier,
                "source_url": source_url,
                "published_at": published_at,
                "reviewed_at": reviewed_at,
                "medical_review_status": review_status,
                "source_name": publisher,
            }
            yield make_record(
                doc_id=doc_id,
                title=title,
                content=content,
                source_id=source_id,
                content_type=content_type,
                language=language,
                pipeline_role=source.get("pipeline_role", "rag_corpus"),
                metadata=metadata,
            )


def merge_source(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    """Phân phối việc chuyển đổi một nguồn dữ liệu theo loại định dạng.

    Vai trò:
        Bộ định tuyến kiểm tra trạng thái và định dạng của nguồn dữ liệu trong manifest
        để gọi hàm chuyển đổi tương ứng (InBody JSON, CSV món ăn, ratings, USDA, hoặc PDF).

    Args:
        source: Bản ghi cấu hình nguồn từ manifest.
        raw_dir: Thư mục chứa dữ liệu thô.

    Returns:
        Iterable chứa các bản ghi tài liệu chuẩn hóa.
    """
    if source.get("status") in ("empty", "excluded_from_rag", "pending_tcvn3_cleaning"):
        return []

    source_id = source["source_id"]
    if source_id == "inbody_medical_knowledge" or source.get("format") == "json_directory":
        return merge_inbody_medical_knowledge(source, raw_dir)
    if source_id == "foodrecordfinal_foods":
        return merge_foods(source, raw_dir)
    if source_id == "foodrecordfinal_ratings":
        return merge_ratings(source, raw_dir)
    if source_id == "usda_fooddata_foundation":
        return merge_usda(source, raw_dir)
    if source.get("format") == "pdf":
        return merge_pdf_placeholder(source, raw_dir)
    return []


def merge_all(raw_dir: Path, output_path: Path, report_path: Path) -> None:
    """Hợp nhất toàn bộ nguồn dữ liệu thô thành một tệp JSONL duy nhất.

    Vai trò:
        Duyệt qua toàn bộ danh sách nguồn trong manifest, gọi chuyển đổi và ghi tuần tự
        vào tệp đầu ra `all_raw_sources.jsonl`, đồng thời xuất báo cáo thống kê số bản ghi.

    Args:
        raw_dir: Đường dẫn tới thư mục dữ liệu thô.
        output_path: Đường dẫn tệp JSONL kết quả hợp nhất.
        report_path: Đường dẫn tệp JSON lưu báo cáo thống kê.
    """
    manifest = read_manifest(raw_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    total = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for source in manifest.get("sources", []):
            source_id = source["source_id"]
            count = 0
            for record in merge_source(source, raw_dir):
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
                total += 1
            counts[source_id] = count

    report = {
        "output_path": str(output_path),
        "total_records": total,
        "counts_by_source": counts,
        "notes": [
            "CSV and JSON sources were converted into normalized JSONL records.",
            "PDF sources are represented as placeholders until text extraction is run.",
            "Ratings are interaction records for recommender experiments, not RAG knowledge documents.",
        ],
    }
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    """Phân tích các đối số dòng lệnh CLI cho raw_loader.

    Vai trò:
        Cung cấp giao diện dòng lệnh cho phép người dùng tùy biến đường dẫn dữ liệu thô,
        tệp đầu ra và tệp báo cáo khi chạy thủ công độc lập.

    Returns:
        Đối tượng argparse.Namespace chứa cấu hình người dùng.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=default_root / "dataset" / "raw",
        help="Path to data_pipeline/dataset/raw.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_root / "dataset" / "processed" / "all_raw_sources.jsonl",
        help="Merged JSONL output path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=default_root / "dataset" / "processed" / "merge_report.json",
        help="Merge report output path.",
    )
    return parser.parse_args()


def main() -> None:
    """Điểm vào thực thi chính khi chạy trực tiếp kịch bản raw_loader.

    Vai trò:
        Nhận tham số dòng lệnh từ người dùng và khởi chạy chu trình merge toàn bộ nguồn dữ liệu.
    """
    args = parse_args()
    merge_all(args.raw_dir, args.output, args.report)
    print(f"Wrote merged JSONL: {args.output}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
