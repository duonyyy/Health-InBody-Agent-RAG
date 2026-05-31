"""Build the canonical dataset files used for Health/InBody embedding.

Pipeline:
1. Merge raw CSV/JSON/PDF placeholders into processed/all_raw_sources.jsonl.
2. Filter and normalize only RAG-ready records into processed/embedding_documents.jsonl.
3. Copy the same corpus to dataset/rag_documents/health_inbody_corpus.jsonl.
4. Create normalized recommender CSV files separately, because ratings are not RAG docs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from merge_raw_sources import merge_all
from prepare_embedding_dataset import ALLOWED_CONTENT_TYPES, prepare_dataset


REQUIRED_FIELDS = {
    "doc_id",
    "title",
    "content",
    "source",
    "content_type",
    "domain",
    "language",
    "metadata",
}


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if line:
                yield line_number, json.loads(line)


def validate_embedding_file(path: Path) -> dict[str, Any]:
    seen_doc_ids: set[str] = set()
    counts: dict[str, int] = {}
    errors: list[str] = []
    total = 0

    for line_number, record in load_jsonl(path):
        total += 1
        missing = sorted(REQUIRED_FIELDS - set(record))
        if missing:
            errors.append(f"line {line_number}: missing {', '.join(missing)}")

        doc_id = str(record.get("doc_id") or "")
        if not doc_id:
            errors.append(f"line {line_number}: empty doc_id")
        elif doc_id in seen_doc_ids:
            errors.append(f"line {line_number}: duplicate doc_id {doc_id}")
        seen_doc_ids.add(doc_id)

        content = str(record.get("content") or "").strip()
        if len(content) < 40:
            errors.append(f"line {line_number}: content too short")

        content_type = record.get("content_type")
        if content_type not in ALLOWED_CONTENT_TYPES:
            errors.append(f"line {line_number}: invalid content_type {content_type}")
        else:
            counts[content_type] = counts.get(content_type, 0) + 1

        if record.get("domain") != "health_inbody":
            errors.append(f"line {line_number}: domain must be health_inbody")

        if not isinstance(record.get("metadata"), dict):
            errors.append(f"line {line_number}: metadata must be object")

    return {
        "total_documents": total,
        "counts_by_content_type": counts,
        "is_valid": not errors,
        "errors": errors[:100],
        "error_count": len(errors),
    }


def normalize_recommender_files(raw_dir: Path, processed_dir: Path) -> dict[str, Any]:
    foods_path = raw_dir / "foodrecordfinal" / "Data" / "Clean Dataset" / "foods.csv"
    ratings_path = raw_dir / "ratings" / "ratings.csv"
    foods_output = processed_dir / "foods_normalized.csv"
    ratings_output = processed_dir / "ratings_normalized.csv"

    valid_food_ids: set[str] = set()
    food_rows = 0

    if foods_path.exists():
        with foods_path.open("r", encoding="utf-8-sig", newline="") as input_file, foods_output.open(
            "w", encoding="utf-8", newline=""
        ) as output_file:
            reader = csv.DictReader(input_file)
            fieldnames = [
                "food_id",
                "dish_name",
                "dish_type",
                "serving_size",
                "cooking_time",
                "calories",
                "fat_g",
                "fiber_g",
                "sugar_g",
                "protein_g",
                "image_link",
            ]
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                food_id = str(row.get("food_id") or "").strip()
                if not food_id:
                    continue
                valid_food_ids.add(food_id)
                food_rows += 1
                writer.writerow(
                    {
                        "food_id": food_id,
                        "dish_name": str(row.get("dish_name") or "").strip(),
                        "dish_type": str(row.get("dish_type") or "").strip(),
                        "serving_size": str(row.get("serving_size") or "").strip(),
                        "cooking_time": str(row.get("cooking_time") or "").strip(),
                        "calories": str(row.get("calories") or "").strip(),
                        "fat_g": str(row.get("fat") or "").strip(),
                        "fiber_g": str(row.get("fiber") or "").strip(),
                        "sugar_g": str(row.get("sugar") or "").strip(),
                        "protein_g": str(row.get("protein") or "").strip(),
                        "image_link": str(row.get("image_link") or "").strip(),
                    }
                )

    rating_rows = 0
    skipped_ratings = 0
    if ratings_path.exists():
        with ratings_path.open("r", encoding="utf-8-sig", newline="") as input_file, ratings_output.open(
            "w", encoding="utf-8", newline=""
        ) as output_file:
            reader = csv.DictReader(input_file)
            writer = csv.DictWriter(output_file, fieldnames=["user_id", "food_id", "rating"])
            writer.writeheader()
            for row in reader:
                food_id = str(row.get("foodId") or "").strip()
                if food_id not in valid_food_ids:
                    skipped_ratings += 1
                    continue
                writer.writerow(
                    {
                        "user_id": str(row.get("userId") or "").strip(),
                        "food_id": food_id,
                        "rating": str(row.get("rating") or "").strip(),
                    }
                )
                rating_rows += 1

    return {
        "foods_normalized": str(foods_output),
        "ratings_normalized": str(ratings_output),
        "foods_rows": food_rows,
        "ratings_rows": rating_rows,
        "skipped_ratings_invalid_food_id": skipped_ratings,
    }


def extract_pdf_sources(raw_dir: Path, processed_dir: Path) -> dict[str, Any]:
    extracted_dir = processed_dir / "extracted_text"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = raw_dir / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pdf_sources = [
        source
        for source in manifest.get("sources", [])
        if source.get("format") == "pdf" and source.get("status") != "empty"
    ]

    try:
        from pypdf import PdfReader
    except ImportError:
        return {
            "status": "missing_dependency",
            "dependency": "pypdf",
            "message": "Install backend requirements, then rerun build_embedding_dataset.py.",
            "pdf_count": len(pdf_sources),
            "extracted_files": [],
        }

    extracted_files: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for source in pdf_sources:
        pdf_path = raw_dir / source["path"]
        output_path = extracted_dir / f"{source['source_id']}.txt"
        try:
            reader = PdfReader(str(pdf_path))
            pages: list[str] = []
            for page_index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(f"\n\n[PAGE {page_index}]\n{text}")
            output_path.write_text("\n".join(pages).strip(), encoding="utf-8")
            extracted_files.append(
                {
                    "source_id": source["source_id"],
                    "raw_path": source["path"],
                    "output_path": str(output_path),
                    "pages": len(reader.pages),
                    "characters": output_path.stat().st_size,
                }
            )
        except Exception as exc:
            errors.append({"source_id": source["source_id"], "error": str(exc)})

    return {
        "status": "ok" if not errors else "partial",
        "pdf_count": len(pdf_sources),
        "extracted_files": extracted_files,
        "errors": errors,
    }


def build(root: Path) -> None:
    raw_dir = root / "dataset" / "raw"
    processed_dir = root / "dataset" / "processed"
    rag_dir = root / "dataset" / "rag_documents"

    processed_dir.mkdir(parents=True, exist_ok=True)
    rag_dir.mkdir(parents=True, exist_ok=True)

    merged_path = processed_dir / "all_raw_sources.jsonl"
    merge_report_path = processed_dir / "merge_report.json"
    embedding_path = processed_dir / "embedding_documents.jsonl"
    embedding_report_path = processed_dir / "embedding_report.json"
    rag_corpus_path = rag_dir / "health_inbody_corpus.jsonl"
    build_report_path = processed_dir / "embedding_build_report.json"

    pdf_extraction = extract_pdf_sources(raw_dir, processed_dir)
    merge_all(raw_dir, merged_path, merge_report_path)
    prepare_dataset(merged_path, embedding_path, embedding_report_path)
    shutil.copyfile(embedding_path, rag_corpus_path)

    validation = validate_embedding_file(embedding_path)
    recommender = normalize_recommender_files(raw_dir, processed_dir)

    report = {
        "raw_dir": str(raw_dir),
        "merged_path": str(merged_path),
        "embedding_documents": str(embedding_path),
        "rag_corpus": str(rag_corpus_path),
        "pdf_extraction": pdf_extraction,
        "validation": validation,
        "recommender_outputs": recommender,
        "next_step": "Run index_mvp_dataset.py when backend is running.",
    }
    with build_report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    if not validation["is_valid"]:
        raise RuntimeError(f"Embedding dataset is invalid. See {build_report_path}")

    print(f"Wrote embedding dataset: {embedding_path}")
    print(f"Wrote RAG corpus copy: {rag_corpus_path}")
    print(f"Wrote build report: {build_report_path}")


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build(args.root)


if __name__ == "__main__":
    main()
