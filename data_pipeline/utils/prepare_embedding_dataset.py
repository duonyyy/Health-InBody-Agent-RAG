"""Prepare Health/InBody documents that are ready for embedding/indexing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_CONTENT_TYPES = {
    "nutrition",
    "exercise",
    "inbody_metric",
    "medical_safety",
    "general_health",
}

SKIP_CONTENT_TYPES = {
    "recommender_interaction",
}

EMBEDDING_DATASET_NAME = "health_inbody_embedding_v1"


SEED_DOCUMENTS = [
    {
        "doc_id": "internal_inbody_bmi_001",
        "title": "BMI trong bao cao InBody",
        "content_type": "inbody_metric",
        "content": (
            "BMI la chi so khoi co the, duoc tinh bang can nang chia cho binh phuong "
            "chieu cao. BMI giup sang loc tinh trang thieu can, binh thuong, thua can "
            "hoac beo phi, nhung khong phan biet duoc khoi luong co va khoi luong mo. "
            "Khi doc bao cao InBody, BMI nen duoc xem cung PBF, SMM, BFM va muc mo noi tang."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_001",
        "title": "PBF va phan tram mo co the",
        "content_type": "inbody_metric",
        "content": (
            "PBF la phan tram mo co the. PBF cao cho thay ty le mo trong co the cao, "
            "co the lien quan den nguy co suc khoe neu di kem vong eo lon, mo noi tang cao "
            "hoac loi song it van dong. PBF can danh gia theo gioi tinh, tuoi, muc tieu "
            "tap luyen va cac chi so khac trong bao cao InBody."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_001",
        "title": "SMM va khoi luong co xuong",
        "content_type": "inbody_metric",
        "content": (
            "SMM la khoi luong co xuong, phan anh luong co tham gia van dong va ho tro "
            "trao doi chat. SMM thap co the goi y can tang tap khang luc, an du protein "
            "va ngu phuc hoi tot hon. Khi giam can, nen co gang giu SMM thay vi chi tap "
            "trung giam can nang."
        ),
    },
    {
        "doc_id": "internal_inbody_bfm_001",
        "title": "BFM va khoi luong mo co the",
        "content_type": "inbody_metric",
        "content": (
            "BFM la khoi luong mo co the tinh theo kg. BFM giup nguoi dung hieu ro can "
            "giam bao nhieu mo thay vi chi nhin can nang. Khi BFM cao, chien luoc tham "
            "khao thuong la tao thieu hut nang luong vua phai, tang protein, tap khang luc "
            "va duy tri cardio phu hop."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_001",
        "title": "Mo noi tang trong bao cao InBody",
        "content_type": "inbody_metric",
        "content": (
            "Mo noi tang la luong mo quanh cac co quan trong o bung. Muc mo noi tang cao "
            "co the lien quan den nguy co chuyen hoa va tim mach. Neu chi so mo noi tang "
            "cao, nguoi dung nen uu tien giam mo ben vung bang an uong can bang, van dong "
            "thuong xuyen, ngu du va tham khao bac si neu co benh nen."
        ),
    },
    {
        "doc_id": "internal_nutrition_fat_loss_001",
        "title": "Nguyen tac dinh duong khi giam mo",
        "content_type": "nutrition",
        "content": (
            "Giam mo nen bat dau bang thieu hut nang luong vua phai, thuong khoang "
            "300-500 kcal moi ngay tuy the trang va muc van dong. Nen uu tien protein "
            "du, rau cu, nguon tinh bot phuc hop, chat beo tot va han che do uong co duong. "
            "Khong nen nhin an cuc doan hoac giam can qua nhanh."
        ),
    },
    {
        "doc_id": "internal_nutrition_muscle_gain_001",
        "title": "Nguyen tac dinh duong khi tang co",
        "content_type": "nutrition",
        "content": (
            "Tang co can tap khang luc deu dan, an du nang luong va du protein. Nguoi tap "
            "nen phan bo protein trong ngay, ket hop tinh bot de co nang luong tap luyen, "
            "va theo doi can nang, so do, suc manh de dieu chinh khau phan."
        ),
    },
    {
        "doc_id": "internal_exercise_beginner_001",
        "title": "Tap luyen co ban cho nguoi moi",
        "content_type": "exercise",
        "content": (
            "Nguoi moi nen bat dau voi 2-3 buoi tap khang luc moi tuan, moi buoi gom cac "
            "dong tac day, keo, squat/hinge va core o cuong do vua phai. Cardio co the "
            "thuc hien 2-3 buoi moi tuan. Tang khoi luong tap tu tu va uu tien ky thuat dung."
        ),
    },
    {
        "doc_id": "internal_medical_safety_001",
        "title": "Gioi han tu van y te cua chatbot",
        "content_type": "medical_safety",
        "content": (
            "He thong chi ho tro thong tin tham khao ve suc khoe, InBody, dinh duong va "
            "tap luyen. He thong khong chan doan benh, khong ke don thuoc va khong thay the "
            "bac si. Neu nguoi dung co dau nguc, kho tho, ngat, dau dau du doi, trieu chung "
            "bat thuong, benh nen phuc tap, dang mang thai hoac dang dung thuoc, nen gap "
            "chuyen gia y te."
        ),
    },
]


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc


def normalize_document(record: dict[str, Any]) -> dict[str, Any] | None:
    content_type = record.get("content_type")
    metadata = dict(record.get("metadata") or {})

    if content_type in SKIP_CONTENT_TYPES:
        return None
    if content_type not in ALLOWED_CONTENT_TYPES:
        return None
    if metadata.get("requires_text_extraction"):
        return None

    content = str(record.get("content") or "").strip()
    if len(content) < 40:
        return None

    return {
        "doc_id": str(record.get("doc_id") or record.get("id")),
        "title": str(record.get("title") or record.get("question") or "Untitled"),
        "content": content,
        "source": str(record.get("source") or "processed_dataset"),
        "content_type": content_type,
        "domain": str(record.get("domain") or "health_inbody"),
        "language": str(record.get("language") or "vi"),
        "metadata": {
            **metadata,
            "embedding_dataset": EMBEDDING_DATASET_NAME,
        },
    }


def seed_document(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": record["doc_id"],
        "title": record["title"],
        "content": record["content"],
        "source": "internal_seed",
        "content_type": record["content_type"],
        "domain": "health_inbody",
        "language": "vi",
        "metadata": {
            "embedding_dataset": EMBEDDING_DATASET_NAME,
            "review_status": "draft",
            "medical_disclaimer_required": record["content_type"] == "medical_safety",
        },
    }


def prepare_dataset(input_path: Path, output_path: Path, report_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    skipped = 0
    written = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for seed in SEED_DOCUMENTS:
            document = seed_document(seed)
            output_file.write(json.dumps(document, ensure_ascii=False) + "\n")
            written += 1
            counts[document["content_type"]] = counts.get(document["content_type"], 0) + 1

        for record in load_jsonl(input_path):
            document = normalize_document(record)
            if document is None:
                skipped += 1
                continue
            output_file.write(json.dumps(document, ensure_ascii=False) + "\n")
            written += 1
            counts[document["content_type"]] = counts.get(document["content_type"], 0) + 1

    report = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "total_documents": written,
        "skipped_records": skipped,
        "counts_by_content_type": counts,
        "ready_for_endpoint": "/documents/index",
        "collection_name": "nmk_chatbot_collection",
        "embedding_dataset": EMBEDDING_DATASET_NAME,
        "notes": [
            "Ratings were excluded because they are recommender interactions, not RAG documents.",
            "PDF placeholders were excluded until text extraction is available.",
            "Internal seed documents were added for InBody metrics, nutrition, exercise, and medical safety.",
        ],
    }
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--input",
        type=Path,
        default=default_root / "dataset" / "processed" / "all_raw_sources.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_root / "dataset" / "processed" / "embedding_documents.jsonl",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=default_root / "dataset" / "processed" / "embedding_report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_dataset(args.input, args.output, args.report)
    print(f"Wrote embedding dataset: {args.output}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
