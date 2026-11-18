"""Bridge to shared provenance helpers in backend/src/rag/provenance.py."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[3] / "backend" / "src"
if _BACKEND_SRC.exists() and str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from rag.provenance import (  # noqa: E402
    PROVENANCE_METADATA_FIELDS,
    compute_document_content_hash,
    empty_review_registry,
    is_verified_medical_review,
    load_review_registry,
    normalize_evidence_provenance,
    resolve_document_provenance,
    sanitize_http_url,
    validate_review_record,
)

__all__ = [
    "PROVENANCE_METADATA_FIELDS",
    "compute_document_content_hash",
    "empty_review_registry",
    "is_verified_medical_review",
    "load_review_registry",
    "normalize_evidence_provenance",
    "resolve_document_provenance",
    "sanitize_http_url",
    "validate_review_record",
]
