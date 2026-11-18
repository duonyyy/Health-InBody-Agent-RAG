"""Document provenance and medical review verification registry helpers.

Separates four distinct concepts:
1. Source classification / trust tier (requires explicit verification, never inferred from seed status).
2. Schema / structural validation.
3. Privacy review (`privacy_review_status`, PII/shared-scope admission).
4. Medical / clinical content review (`medical_review_status`, backed by a
   project-managed review registry matched to document_id and content_hash).

Legacy records claiming `medical_review_status='approved'` without a matching
registry record are downgraded to `unverified_legacy` rather than silently
accepted as medically reviewed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

PROVENANCE_POLICY_VERSION = "2026-11-19-v2"

DEFAULT_REVIEW_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "medical_review_registry.json"
)

ALLOWED_SOURCE_TIERS = {
    "guideline",
    "government",
    "peer_reviewed",
    "professional_org",
    "clinic_education",
}

ALLOWED_REVIEW_DECISIONS = {"approved", "rejected", "needs_revision"}

LEGACY_CLAIMED_APPROVED_STATUSES = {"approved", "reviewed"}

PROVENANCE_METADATA_FIELDS = (
    "document_id",
    "chunk_id",
    "parent_id",
    "corpus_version",
    "content_hash",
    "document_content_hash",
    "source_url",
    "publisher",
    "source_name",
    "source_origin",
    "source_tier",
    "source_tier_verified",
    "claimed_source_tier",
    "published_at",
    "reviewed_at",
    "medical_review_status",
    "review_verification_status",
    "review_id",
    "reviewer_id",
    "review_role",
    "review_scope",
    "reviewed_content_hash",
    "reviewed_document_version",
    "review_notes",
    "stale_review_id",
    "legacy_claimed_review_status",
    "legacy_claimed_reviewed_at",
    "privacy_review_status",
    "data_scope",
)

_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF\u200E\u200F]")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _ResolvedProvenance(dict):
    """In-process result of registry resolution; JSON payloads cannot create it."""


def normalize_provenance_text(text: str) -> str:
    """Normalize text consistently before hashing document content."""
    normalized = unicodedata.normalize("NFC", str(text or ""))
    normalized = _ZERO_WIDTH_RE.sub("", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def compute_document_content_hash(content: str) -> str:
    """Compute a deterministic SHA-256 hex digest for document content."""
    normalized = normalize_provenance_text(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_http_url(value: Any) -> Optional[str]:
    """Return a clean absolute http(s) URL, or None for missing/non-URL values."""
    text = str(value or "").strip()
    if not text:
        return None
    # Handle semicolon-separated reference lists only if the first token is a valid URL
    candidate = text.split(";")[0].strip() if ";" in text else text
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def is_valid_iso_date(value: Any) -> bool:
    """Validate that a string starts with an ISO-8601 calendar date YYYY-MM-DD."""
    text = str(value or "").strip()
    if len(text) < 10:
        return False
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


def _first_non_empty(
    record: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *keys: str,
) -> Optional[str]:
    for key in keys:
        for container in (record, metadata):
            value = container.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return None


def empty_review_registry() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "registry_version": "unloaded",
        "is_synthetic_fixture": False,
        "reviewers": {},
        "reviews": [],
    }


def load_review_registry(
    path: str | Path | None = None,
    *,
    allow_synthetic: bool = False,
) -> Dict[str, Any]:
    """Load the project-managed medical review registry JSON.

    Synthetic test fixtures are rejected unless `allow_synthetic=True`.
    """
    env_path = os.getenv("MEDICAL_REVIEW_REGISTRY_PATH")
    target = Path(path) if path is not None else Path(env_path or DEFAULT_REVIEW_REGISTRY_PATH)
    if not target.exists():
        return empty_review_registry()

    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Review registry must be a JSON object")
    if payload.get("is_synthetic_fixture") and not allow_synthetic:
        raise ValueError(
            "Synthetic medical review fixture cannot be loaded as a real review registry"
        )
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported medical review registry schema_version")
    reviewers = payload.get("reviewers")
    reviews = payload.get("reviews")
    if not isinstance(reviewers, dict) or not isinstance(reviews, list):
        raise ValueError("Review registry must define 'reviewers' object and 'reviews' list")

    filtered_reviews: List[Dict[str, Any]] = []
    for entry in reviews:
        if not isinstance(entry, dict):
            continue
        if entry.get("is_synthetic_fixture") and not allow_synthetic:
            raise ValueError(
                "Synthetic review record cannot be packaged in a real review registry"
            )
        filtered_reviews.append(entry)

    return {
        "schema_version": 1,
        "registry_version": str(payload.get("registry_version") or "unknown"),
        "is_synthetic_fixture": bool(payload.get("is_synthetic_fixture", False)),
        "reviewers": reviewers,
        "reviews": filtered_reviews,
    }


def validate_review_record(
    review: Mapping[str, Any],
    reviewers: Mapping[str, Any],
    *,
    allow_synthetic: bool = False,
) -> Tuple[bool, List[str]]:
    """Validate that a medical review record has complete, auditable provenance."""
    errors: List[str] = []
    if not isinstance(review, Mapping):
        return False, ["review record must be a mapping"]
    if review.get("is_synthetic_fixture") and not allow_synthetic:
        errors.append("synthetic review fixture is not permitted")

    review_id = str(review.get("review_id") or "").strip()
    if not review_id:
        errors.append("missing review_id")

    document_id = str(review.get("document_id") or "").strip()
    if not document_id:
        errors.append("missing document_id")

    reviewer_id = str(review.get("reviewer_id") or "").strip()
    reviewer_info = reviewers.get(reviewer_id) if reviewer_id and isinstance(reviewers, Mapping) else None
    if not reviewer_id or not isinstance(reviewer_info, Mapping):
        errors.append("reviewer_id is not registered in managed reviewers directory")
    elif reviewer_info.get("active") is not True:
        errors.append("reviewer_id is inactive or has no explicit active status")

    review_scope = str(review.get("review_scope") or "").strip()
    if not review_scope:
        errors.append("missing review_scope")
    if isinstance(reviewer_info, Mapping) and reviewer_info.get("allowed_scopes") is not None:
        allowed = reviewer_info.get("allowed_scopes")
        if not isinstance(allowed, list) or review_scope not in allowed:
            errors.append("reviewer is not authorized for review_scope")
    if review.get("revoked") or review.get("revoked_at"):
        errors.append("review record is revoked")
    expires = review.get("expires_at") or review.get("valid_until")
    if expires:
        if not is_valid_iso_date(expires) or date.fromisoformat(str(expires)[:10]) < date.today():
            errors.append("review record is expired or has an invalid expiry")

    review_role = str(
        review.get("review_role")
        or (reviewer_info.get("role") if isinstance(reviewer_info, Mapping) else "")
        or ""
    ).strip()
    if not review_role:
        errors.append("missing review_role")

    reviewed_at = str(review.get("reviewed_at") or "").strip()
    if not is_valid_iso_date(reviewed_at):
        errors.append("reviewed_at must be a valid ISO date")

    content_hash = str(review.get("content_hash") or "").strip().lower()
    if not _HEX_SHA256_RE.fullmatch(content_hash):
        errors.append("content_hash must be a 64-character lowercase SHA-256 hex digest")

    decision = str(review.get("decision") or "").strip().lower()
    if decision not in ALLOWED_REVIEW_DECISIONS:
        errors.append("decision must be approved, rejected, or needs_revision")

    notes = str(review.get("notes") or review.get("rationale") or "").strip()
    if not notes:
        errors.append("missing review notes/rationale")

    return len(errors) == 0, errors


def _assert_registry_allowed(
    registry: Mapping[str, Any],
    *,
    allow_synthetic_registry: bool,
) -> None:
    if registry.get("is_synthetic_fixture") and not allow_synthetic_registry:
        raise ValueError(
            "Synthetic medical review fixture cannot be used as a real review registry"
        )


def resolve_document_provenance(
    record: Mapping[str, Any],
    *,
    content: Optional[str] = None,
    registry: Optional[Mapping[str, Any]] = None,
    is_seed: bool = False,
    allow_synthetic_registry: bool = False,
) -> Dict[str, Any]:
    """Resolve authoritative provenance metadata for a document.

    Input claims such as `medical_review_status='approved'` or `source_tier='guideline'`
    are never trusted without a valid, content-hash-matched entry in the managed
    review registry.
    """
    metadata = dict(record.get("metadata") or {}) if isinstance(record.get("metadata"), Mapping) else {}
    document_id = _first_non_empty(record, metadata, "document_id", "doc_id", "id") or ""
    raw_content = content if content is not None else str(record.get("content") or record.get("page_content") or "")
    # A supplied hash is not authority for missing document content.
    doc_hash = compute_document_content_hash(raw_content) if raw_content.strip() else ""
    doc_version = _first_non_empty(record, metadata, "document_version", "version")

    raw_claimed_status = _first_non_empty(
        record,
        metadata,
        "legacy_claimed_review_status",
        "medical_review_status",
        "review_status",
    )
    raw_claimed_reviewed_at = _first_non_empty(
        record,
        metadata,
        "legacy_claimed_reviewed_at",
        "reviewed_at",
    )
    raw_claimed_tier = _first_non_empty(record, metadata, "source_tier")
    raw_source_url = _first_non_empty(record, metadata, "source_url")
    clean_source_url = sanitize_http_url(raw_source_url)
    raw_publisher = _first_non_empty(record, metadata, "publisher")
    raw_source_name = _first_non_empty(record, metadata, "source_name")
    raw_published_at = _first_non_empty(record, metadata, "published_at")
    clean_published_at = raw_published_at if is_valid_iso_date(raw_published_at) else None
    privacy_review_status = _first_non_empty(record, metadata, "privacy_review_status")
    data_scope = _first_non_empty(record, metadata, "data_scope")

    active_registry = (
        registry
        if registry is not None
        else load_review_registry(allow_synthetic=allow_synthetic_registry)
    )
    if not isinstance(active_registry, Mapping):
        raise ValueError("Review registry must be a mapping")
    if "schema_version" in active_registry and active_registry["schema_version"] != 1:
        raise ValueError("Unsupported medical review registry schema_version")
    _assert_registry_allowed(active_registry, allow_synthetic_registry=allow_synthetic_registry)
    if not isinstance(active_registry.get("reviewers"), Mapping) or not isinstance(active_registry.get("reviews"), list):
        raise ValueError("Review registry must define 'reviewers' object and 'reviews' list")
    reviewers = active_registry.get("reviewers") or {}
    reviews = active_registry.get("reviews") or []

    valid_doc_reviews: List[Dict[str, Any]] = []
    revoked_review_present = False
    invalid_review_present = False
    for entry in reviews:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("document_id") or "").strip() != document_id:
            continue
        if entry.get("revoked") or entry.get("revoked_at"):
            revoked_review_present = True
        if entry.get("is_synthetic_fixture") and not allow_synthetic_registry:
            continue
        ok, _ = validate_review_record(
            entry,
            reviewers,
            allow_synthetic=allow_synthetic_registry,
        )
        if ok:
            valid_doc_reviews.append(dict(entry))
        else:
            invalid_review_present = True

    # A revocation cannot be bypassed by falling back to an older approval.
    if revoked_review_present or invalid_review_present:
        valid_doc_reviews = []
    valid_doc_reviews.sort(key=lambda item: str(item.get("reviewed_at") or ""), reverse=True)

    matching_review: Optional[Dict[str, Any]] = None
    for entry in valid_doc_reviews[:1]:
        entry_hash = str(entry.get("content_hash") or "").strip().lower()
        entry_version = str(entry.get("document_version") or "").strip()
        version_ok = not entry_version or entry_version == doc_version
        content_type = _first_non_empty(record, metadata, "content_type") or ""
        scope_ok = str(entry.get("review_scope") or "").strip() in {"whole_document", content_type}
        if doc_hash and entry_hash == doc_hash and version_ok and scope_ok:
            matching_review = entry
            break

    base: Dict[str, Any] = {
        "document_id": document_id or None,
        "document_content_hash": doc_hash or None,
        "source_origin": "internal_seed" if is_seed or str(record.get("source") or "") == "internal_seed" else str(record.get("source") or "external"),
        "source_name": raw_source_name,
        "source_url": clean_source_url,
        "publisher": None if is_seed and not matching_review else raw_publisher,
        "published_at": None if is_seed and not matching_review else clean_published_at,
        "source_tier": None,
        "source_tier_verified": False,
        "claimed_source_tier": raw_claimed_tier,
        "reviewed_at": None,
        "medical_review_status": "provisional" if is_seed else "unreviewed",
        "review_verification_status": "unreviewed",
        "review_id": None,
        "reviewer_id": None,
        "review_role": None,
        "review_scope": None,
        "reviewed_content_hash": None,
        "reviewed_document_version": None,
        "review_notes": None,
        "stale_review_id": None,
        "legacy_claimed_review_status": None,
        "legacy_claimed_reviewed_at": None,
        "privacy_review_status": privacy_review_status,
        "data_scope": data_scope,
    }

    if matching_review is not None:
        decision = str(matching_review["decision"]).strip().lower()
        reviewer_info = reviewers.get(str(matching_review["reviewer_id"]).strip()) or {}
        review_role = str(matching_review.get("review_role") or reviewer_info.get("role") or "").strip() or None

        verified_tier = str(matching_review.get("verified_source_tier") or "").strip() or None
        if verified_tier not in ALLOWED_SOURCE_TIERS:
            verified_tier = None
        verified_url = sanitize_http_url(matching_review.get("verified_source_url"))
        verified_publisher = str(matching_review.get("verified_publisher") or "").strip() or None
        verified_published_at = str(matching_review.get("verified_published_at") or "").strip() or None
        if verified_published_at and not is_valid_iso_date(verified_published_at):
            verified_published_at = None

        base.update({
            "review_id": str(matching_review["review_id"]).strip(),
            "reviewer_id": str(matching_review["reviewer_id"]).strip(),
            "review_role": review_role,
            "review_scope": str(matching_review["review_scope"]).strip(),
            "reviewed_at": str(matching_review["reviewed_at"]).strip(),
            "reviewed_content_hash": str(matching_review["content_hash"]).strip().lower(),
            "reviewed_document_version": str(matching_review.get("document_version") or "").strip() or None,
            "review_notes": str(matching_review.get("notes") or matching_review.get("rationale") or "").strip(),
            "source_url": verified_url or clean_source_url,
            "publisher": verified_publisher or raw_publisher,
            "published_at": verified_published_at or clean_published_at,
        })
        if decision == "approved":
            base["medical_review_status"] = "approved"
            base["review_verification_status"] = "verified"
            base["source_tier"] = verified_tier
            base["source_tier_verified"] = bool(verified_tier)
        else:
            base["medical_review_status"] = decision
            base["review_verification_status"] = "verified_not_approved"
            base["source_tier"] = None
            base["source_tier_verified"] = False
        return _ResolvedProvenance(base)

    if valid_doc_reviews:
        latest_stale = valid_doc_reviews[0]
        base.update({
            "medical_review_status": "stale_review",
            "review_verification_status": "stale_content_mismatch",
            "stale_review_id": str(latest_stale["review_id"]).strip(),
            "reviewed_content_hash": str(latest_stale["content_hash"]).strip().lower(),
            "reviewed_at": None,
            "source_tier": None,
            "source_tier_verified": False,
        })
        return _ResolvedProvenance(base)

    # No valid registry entry exists for this document.
    if raw_claimed_status and raw_claimed_status.lower() in (
        LEGACY_CLAIMED_APPROVED_STATUSES | {"unverified_legacy"}
    ):
        base.update({
            "medical_review_status": "unverified_legacy",
            "review_verification_status": "unverified_legacy",
            "legacy_claimed_review_status": (
                raw_claimed_status if raw_claimed_status.lower() != "unverified_legacy" else "approved"
            ),
            "legacy_claimed_reviewed_at": raw_claimed_reviewed_at,
            "reviewed_at": None,
            "source_tier": None,
            "source_tier_verified": False,
        })
    return _ResolvedProvenance(base)


def is_verified_medical_review(metadata: Mapping[str, Any]) -> bool:
    """Return True only when a record carries a verified, non-stale approved review."""
    if not isinstance(metadata, _ResolvedProvenance):
        return False
    if metadata.get("is_synthetic_fixture"):
        return False
    if str(metadata.get("review_verification_status") or "").strip() != "verified":
        return False
    if str(metadata.get("medical_review_status") or "").strip() != "approved":
        return False
    required = (
        metadata.get("review_id"),
        metadata.get("reviewer_id"),
        metadata.get("review_scope"),
        metadata.get("reviewed_at"),
        metadata.get("reviewed_content_hash"),
    )
    if any(not str(item or "").strip() for item in required):
        return False
    if not is_valid_iso_date(metadata.get("reviewed_at")):
        return False
    reviewed_hash = str(metadata.get("reviewed_content_hash") or "").strip().lower()
    if not _HEX_SHA256_RE.fullmatch(reviewed_hash):
        return False
    doc_hash = str(metadata.get("document_content_hash") or "").strip().lower()
    if doc_hash and doc_hash != reviewed_hash:
        return False
    return True


def normalize_evidence_provenance(
    doc: Mapping[str, Any],
    *,
    registry: Optional[Mapping[str, Any]] = None,
    allow_synthetic_registry: bool = False,
) -> Dict[str, Any]:
    """Normalize provenance for a retrieved chunk before exposing it as evidence.

    Prevents legacy/unverified payloads from being presented as medically approved
    or verified guidelines, while preserving legitimately verified review records.
    """
    metadata = dict(doc.get("metadata") or {}) if isinstance(doc.get("metadata"), Mapping) else {}
    merged: Dict[str, Any] = {**metadata, **doc}
    is_seed = str(merged.get("source") or "") == "internal_seed" or str(merged.get("source_origin") or "") == "internal_seed"

    # Retrieved payload stamps and document hashes are claims, not authority.  Hash
    # the complete supplied content, before the composer truncates it. A chunk
    # whose relationship to the reviewed document is not independently provable
    # therefore fails closed instead of trusting its document_content_hash.
    content = str(merged.get("content") or merged.get("page_content") or "")
    try:
        resolved = resolve_document_provenance(
            merged, content=content, registry=registry, is_seed=is_seed,
            allow_synthetic_registry=allow_synthetic_registry,
        )
    except (ValueError, OSError, TypeError, KeyError) as exc:
        resolved = resolve_document_provenance(
            merged, content=content, registry=empty_review_registry(), is_seed=is_seed,
        )
        resolved["review_verification_status"] = "registry_unavailable"
        resolved["review_failure_reason"] = type(exc).__name__

    if resolved["review_verification_status"] == "verified":
        scope = str(resolved.get("review_scope") or "")
        content_type = str(merged.get("content_type") or "")
        inconsistent = not content.strip() or scope not in {"whole_document", content_type}
        identity_claims = {
            str(source[key]).strip()
            for source in (metadata, doc) for key in ("document_id", "doc_id")
            if source.get(key) is not None and str(source[key]).strip()
        }
        if len(identity_claims) > 1:
            inconsistent = True
        for field in ("document_id", "document_version", "review_id", "reviewer_id", "review_role", "review_scope", "reviewed_at", "reviewed_content_hash", "document_content_hash", "medical_review_status", "review_verification_status"):
            if field in {"document_id", "document_version"}:
                expected = _first_non_empty(doc, metadata, field)
            else:
                expected = resolved.get(field)
            for source in (metadata, doc):
                claimed = source.get(field)
                if claimed is not None and str(claimed).strip() != str(expected or "").strip():
                    inconsistent = True
        if inconsistent:
            resolved["medical_review_status"] = "unverified_legacy"
            resolved["review_verification_status"] = "binding_unverified"
            resolved["review_id"] = None
            resolved["reviewer_id"] = None
            resolved["review_scope"] = None
            resolved["source_tier"] = None
            resolved["source_tier_verified"] = False

    return _ResolvedProvenance({
        "source_url": resolved["source_url"],
        "publisher": resolved["publisher"],
        "source_tier": resolved["source_tier"],
        "source_tier_verified": resolved["source_tier_verified"],
        "published_at": resolved["published_at"],
        "reviewed_at": resolved["reviewed_at"],
        "medical_review_status": resolved["medical_review_status"],
        "review_verification_status": resolved["review_verification_status"],
        "review_id": resolved["review_id"],
        "reviewer_id": resolved["reviewer_id"],
        "review_role": resolved["review_role"],
        "review_scope": resolved["review_scope"],
        "reviewed_content_hash": resolved["reviewed_content_hash"],
        "document_content_hash": resolved["document_content_hash"],
        "stale_review_id": resolved["stale_review_id"],
        "legacy_claimed_review_status": resolved["legacy_claimed_review_status"],
        "privacy_review_status": resolved["privacy_review_status"],
        "review_failure_reason": resolved.get("review_failure_reason"),
    })
