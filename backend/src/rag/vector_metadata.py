"""Pure metadata helpers shared by Qdrant ingestion and tests."""

from typing import Any, Mapping

from rag.provenance import normalize_evidence_provenance


PAYLOAD_KEYWORD_INDEX_FIELDS = (
    "content_type",
    "domain",
    "source",
    "language",
    "doc_id",
    "document_id",
    "chunk_id",
    "corpus_version",
    "release_id",
    "embedding_fingerprint",
    "content_hash",
    "review_status",
    "medical_review_status",
    "review_verification_status",
    "review_id",
    "privacy_review_status",
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

    # Normalize provenance so unverified legacy 'approved' or 'guideline' claims
    # cannot enter Qdrant payloads presented as clinically verified.
    provenance = normalize_evidence_provenance(prepared)
    prepared.update(
        {
            "source_url": provenance["source_url"],
            "publisher": provenance["publisher"],
            "source_tier": provenance["source_tier"],
            "source_tier_verified": provenance["source_tier_verified"],
            "published_at": provenance["published_at"],
            "reviewed_at": provenance["reviewed_at"],
            "medical_review_status": provenance["medical_review_status"],
            "review_verification_status": provenance["review_verification_status"],
            "review_id": provenance["review_id"],
            "reviewer_id": provenance["reviewer_id"],
            "review_role": provenance["review_role"],
            "review_scope": provenance["review_scope"],
            "reviewed_content_hash": provenance["reviewed_content_hash"],
            "document_content_hash": provenance["document_content_hash"],
            "privacy_review_status": provenance["privacy_review_status"],
        }
    )
    if provenance.get("legacy_claimed_review_status"):
        prepared["legacy_claimed_review_status"] = provenance["legacy_claimed_review_status"]
    if provenance.get("stale_review_id"):
        prepared["stale_review_id"] = provenance["stale_review_id"]
    prepared.pop("review_status", None)
    return prepared
