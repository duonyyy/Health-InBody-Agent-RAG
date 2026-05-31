"""Merge raw dataset sources into one normalized JSONL file.

This script keeps files under dataset/raw unchanged and writes a single
line-delimited JSON file under dataset/processed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable


PROJECT_DOMAIN = "health_inbody"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def compact_parts(parts: Iterable[str]) -> str:
    return "\n".join(part for part in (clean_text(part) for part in parts) if part)


def read_manifest(raw_dir: Path) -> dict[str, Any]:
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
    path = raw_dir / source["path"]
    if not path.exists():
        return
    processed_dir = raw_dir.parent / "processed"
    extracted_text_path = processed_dir / "extracted_text" / f"{source['source_id']}.txt"
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
                    title=f"{title} - trang {page_number}",
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


def merge_source(source: dict[str, Any], raw_dir: Path) -> Iterable[dict[str, Any]]:
    if source.get("status") == "empty":
        return []

    source_id = source["source_id"]
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
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
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
    args = parse_args()
    merge_all(args.raw_dir, args.output, args.report)
    print(f"Wrote merged JSONL: {args.output}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
