"""Pure metadata helpers shared by Qdrant ingestion and tests."""

from typing import Any, Mapping


PAYLOAD_KEYWORD_INDEX_FIELDS = (
    "content_type",
    "domain",
    "source",
    "language",
    "doc_id",
    "document_id",
    "corpus_version",
    "content_hash",
    "review_status",
    "medical_review_status",
)


def detect_content_type(content: str) -> str:
    """Infer a Health/InBody content type only when the dataset has no label."""
    content_lower = (content or "").lower()

    if any(
        keyword in content_lower
        for keyword in [
            "inbody",
            "bmi",
            "smm",
            "bfm",
            "pbf",
            "mỡ nội tạng",
            "khối lượng cơ",
            "khối lượng mỡ",
        ]
    ):
        return "inbody_metric"
    if any(
        keyword in content_lower
        for keyword in [
            "dinh dưỡng",
            "calo",
            "calorie",
            "protein",
            "carb",
            "chất béo",
            "khẩu phần",
            "ăn uống",
        ]
    ):
        return "nutrition"
    if any(
        keyword in content_lower
        for keyword in [
            "tập luyện",
            "lịch tập",
            "cardio",
            "kháng lực",
            "tăng cơ",
            "giảm mỡ",
            "phục hồi",
        ]
    ):
        return "exercise"
    if any(
        keyword in content_lower
        for keyword in [
            "bác sĩ",
            "triệu chứng",
            "bệnh nền",
            "thuốc",
            "chẩn đoán",
            "cấp cứu",
            "an toàn",
        ]
    ):
        return "medical_safety"
    return "general_health"


def prepare_vector_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Preserve curated dataset metadata and add derived operational fields.

    The previous implementation always replaced ``content_type`` using a
    per-chunk keyword heuristic. That made chunks from one source document land
    in different categories. Explicit pipeline metadata is authoritative; the
    heuristic is only a fallback for legacy/unlabelled records.
    """
    prepared = dict(payload)
    content = str(prepared.get("content") or "")
    explicit_content_type = str(prepared.get("content_type") or "").strip()

    if explicit_content_type:
        prepared["content_type"] = explicit_content_type
        prepared["content_type_source"] = "dataset"
    else:
        prepared["content_type"] = detect_content_type(content)
        prepared["content_type_source"] = "heuristic"

    prepared["doc_length"] = len(content)
    prepared["has_question"] = bool(str(prepared.get("question") or "").strip())
    return prepared
