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
        "source_name": "CDC Adult BMI Categories; WHO Obesity and Overweight",
        "source_url": "https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html; https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
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
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
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
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
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
        "source_name": "InBody Result Sheet; CDC BMI limitations",
        "source_url": "https://inbodyusa.com/general/result-sheet/; https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html",
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
        "source_name": "Cleveland Clinic Visceral Fat",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
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
        "source_name": "WHO obesity prevention; Cleveland Clinic visceral fat care",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight; https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
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
        "source_name": "Sports nutrition principles",
        "source_url": "internal_curated",
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
        "source_name": "WHO physical activity and obesity prevention principles",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
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
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "He thong chi ho tro thong tin tham khao ve suc khoe, InBody, dinh duong va "
            "tap luyen. He thong khong chan doan benh, khong ke don thuoc va khong thay the "
            "bac si. Neu nguoi dung co dau nguc, kho tho, ngat, dau dau du doi, trieu chung "
            "bat thuong, benh nen phuc tap, dang mang thai hoac dang dung thuoc, nen gap "
            "chuyen gia y te."
        ),
    },
    {
        "doc_id": "internal_inbody_bmi_limitations_001",
        "title": "Gioi han cua BMI khi doc bao cao InBody",
        "content_type": "inbody_metric",
        "source_name": "CDC Adult BMI Categories; WHO Obesity and Overweight",
        "source_url": "https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html; https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "BMI la cong cu sang loc nhanh, khong phai chan doan ca nhan. BMI khong tach "
            "duoc khoi luong co, mo, xuong va nuoc, nen nguoi tap khang luc co nhieu co "
            "co the co BMI cao nhung PBF khong cao. Khi doc InBody, nen ket hop BMI voi "
            "PBF, SMM, BFM, vong eo, mo noi tang, tien su benh va muc tieu cua nguoi dung."
        ),
    },
    {
        "doc_id": "internal_inbody_bmi_asian_cutoff_001",
        "title": "BMI va nguong nguy co o nguoi chau A",
        "content_type": "inbody_metric",
        "source_name": "WHO BMI public health action points for Asian populations",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "Mot so quan the chau A co nguy co chuyen hoa o BMI thap hon nguong quoc te. "
            "Trong tu van tieng Viet, BMI tu 23 den duoi 25 co the duoc xem la vung can "
            "canh bao som, nhat la khi PBF, vong eo hoac mo noi tang cung cao. Nen trinh bay "
            "day la nguong tham khao, khong dung rieng BMI de ket luan benh."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_interpretation_001",
        "title": "Cach doc PBF trong InBody",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "PBF cho biet ti le khoi luong mo tren tong can nang. Hai nguoi co cung can "
            "nang va BMI co the co PBF rat khac nhau neu mot nguoi co nhieu co hon. PBF "
            "nen duoc doc cung SMM, BFM, gioi tinh, tuoi, muc tieu tap luyen va tien su suc "
            "khoe. PBF cao thuong uu tien giam mo ben vung, khong nen an kieng cuc doan."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_vs_bfm_001",
        "title": "PBF khac BFM nhu the nao",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "PBF la phan tram mo co the, con BFM la khoi luong mo tinh bang kg. PBF giup "
            "so sanh ti le mo giua nhung nguoi co can nang khac nhau, trong khi BFM giup "
            "uoc tinh muc mo can giam hoac theo doi thay doi theo thoi gian. Khi giam mo, "
            "PBF va BFM nen giam tu tu trong khi SMM duoc duy tri cang tot cang tot."
        ),
    },
    {
        "doc_id": "internal_inbody_bfm_fat_loss_tracking_001",
        "title": "Dung BFM de theo doi giam mo",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "BFM phu hop de theo doi tien trinh giam mo vi no bieu dien khoi luong mo bang "
            "kg. Neu can nang giam nhung BFM khong giam, nguoi dung co the dang mat nuoc "
            "hoac mat co. Neu BFM giam va SMM giu on dinh, chien luoc giam mo co kha nang "
            "dang di dung huong. Nen so sanh cac lan do trong dieu kien do tuong tu."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_interpretation_001",
        "title": "Cach doc SMM va khoi luong co xuong",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "SMM phan anh khoi luong co xuong, la phan co quan trong cho van dong, suc "
            "manh va tieu hao nang luong. SMM thap so voi can nang hoac giam nhanh trong "
            "qua trinh an kieng la tin hieu can tang protein, tap khang luc va cai thien "
            "phuc hoi. SMM khong nen doc tach roi khoi can nang, PBF va muc hoat dong."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_gain_strategy_001",
        "title": "Chien luoc tang hoac bao toan SMM",
        "content_type": "exercise",
        "source_name": "Sports nutrition and resistance training principles",
        "source_url": "internal_curated",
        "content": (
            "De tang hoac bao toan SMM, nen tap khang luc 2-4 buoi moi tuan voi cac dong "
            "tac lon nhu squat, hinge, day, keo va core. Tang khoi luong tap tu tu, an du "
            "protein, ngu du va tranh thieu hut calo qua lon. Khi dang giam mo, muc tieu "
            "thuc te la giam BFM/PBF trong khi SMM giam it nhat co the."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_risk_001",
        "title": "Y nghia suc khoe cua mo noi tang",
        "content_type": "inbody_metric",
        "source_name": "Cleveland Clinic Visceral Fat",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
        "content": (
            "Mo noi tang nam sau trong o bung va bao quanh nhieu co quan noi tang. Co mot "
            "luong mo noi tang la binh thuong, nhung qua nhieu co the lien quan den nguy "
            "co tim mach, tieu duong, roi loan lipid mau va cac van de chuyen hoa. Chi so "
            "mo noi tang cao nen duoc uu tien trong muc tieu giam mo an toan."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_action_001",
        "title": "Nen lam gi khi mo noi tang cao",
        "content_type": "inbody_metric",
        "source_name": "Cleveland Clinic Visceral Fat; Mayo Clinic belly fat guidance",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat; https://www.mayoclinic.org/healthy-lifestyle/womens-health/in-depth/belly-fat/art-20045809",
        "content": (
            "Khi mo noi tang cao, chien luoc nen tap trung vao thoi quen ben vung: an nhieu "
            "thuc pham it che bien, du protein va chat xo, giam do uong co duong va ruou, "
            "tap cardio ket hop khang luc, ngu du va quan ly stress. Neu co benh nen tim "
            "mach, huyet ap, tieu duong hoac trieu chung bat thuong, nen gap bac si."
        ),
    },
    {
        "doc_id": "internal_inbody_bia_preparation_001",
        "title": "Dieu kien do InBody va BIA de ket qua on dinh",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet FAQ; BIA measurement principles",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "InBody dung phan tich tro khang dien sinh hoc, nen ket qua co the bi anh huong "
            "boi nuoc trong co the, bua an, tap luyen, nhiet do, tu the, trang phuc va tiep "
            "xuc dien cuc. De so sanh tien trinh, nen do cung thoi diem trong ngay, tranh "
            "tap nang ngay truoc khi do, di ve sinh truoc khi do va giu dieu kien lap lai."
        ),
    },
    {
        "doc_id": "internal_inbody_bia_limitations_001",
        "title": "Gioi han cua phuong phap BIA",
        "content_type": "inbody_metric",
        "source_name": "BIA body composition literature; InBody educational material",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "BIA la phuong phap tien loi de uoc tinh thanh phan co the, nhung khong phai "
            "chuan vang nhu DXA, MRI hoac cac mo hinh da thanh phan. Ket qua mot lan do "
            "khong nen duoc xem la chan doan. Gia tri lon nhat cua BIA trong ung dung ca "
            "nhan la theo doi xu huong qua nhieu lan do trong dieu kien nhat quan."
        ),
    },
    {
        "doc_id": "internal_inbody_recomposition_001",
        "title": "Tai cau truc co the: giam mo va giu co",
        "content_type": "general_health",
        "source_name": "Project curated body recomposition guidance",
        "source_url": "internal_curated",
        "content": (
            "Tai cau truc co the la qua trinh giam BFM/PBF trong khi giu hoac tang SMM. "
            "Nguoi moi tap, nguoi co PBF cao hoac nguoi quay lai tap sau thoi gian nghi "
            "co the thay doi ca hai huong cung luc. Nen uu tien thieu hut calo nhe, du "
            "protein, tap khang luc deu va theo doi xu huong moi 2-4 tuan."
        ),
    },
    {
        "doc_id": "internal_safety_red_flags_exercise_001",
        "title": "Dau hieu can dung tap va tim ho tro y te",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Neu nguoi dung co dau nguc, kho tho bat thuong, ngat, choang vang, dau dau du "
            "doi, yeu liet, dau khop sac nhon, chay mau, hoac trieu chung xau di khi tap, "
            "he thong phai khuyen dung tap va lien he co so y te. Chatbot khong duoc khang "
            "dinh chan doan hay dua phac do dieu tri."
        ),
    },
    {
        "doc_id": "internal_safety_chronic_conditions_001",
        "title": "Tu van thuc trong khi co benh nen",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Voi nguoi co tieu duong, tang huyet ap, benh tim mach, benh than, dang mang "
            "thai, nguoi cao tuoi, tien su chan thuong hoac dang dung thuoc, khuyen nghi "
            "dinh duong va tap luyen can thuc trong. He thong chi nen dua thong tin tham "
            "khao, tranh muc tieu cuc doan va khuyen hoi bac si/chuyen gia truoc khi doi "
            "che do manh."
        ),
    },
    {
        "doc_id": "internal_safety_no_extreme_diet_001",
        "title": "Khong khuyen nghi an kieng cuc doan",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "He thong khong nen khuyen nhin an cuc doan, cat calo qua thap, bo ca nhom "
            "chat dinh duong neu khong co chi dinh y te, dung thuoc giam can trai phep "
            "hoac tap qua suc de giam mo nhanh. Khuyen nghi an toan la thay doi tu tu, "
            "du protein, du rau chat xo, du nuoc, ngu phuc hoi va theo doi trieu chung."
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
            "source_name": record.get("source_name", "internal_curated"),
            "source_url": record.get("source_url", "internal_curated"),
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
            "PDF placeholders without extracted text were excluded from the RAG corpus.",
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
