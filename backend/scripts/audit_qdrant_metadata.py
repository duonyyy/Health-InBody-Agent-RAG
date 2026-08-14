"""Read-only audit of trust metadata in the active Qdrant collection."""

import argparse
import json
from collections import Counter

from core.config import DEFAULT_COLLECTION_NAME
from rag.qdrant.client import client


REQUIRED_TRUST_FIELDS = (
    "source_url",
    "publisher",
    "source_tier",
    "published_at",
    "reviewed_at",
    "medical_review_status",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args()

    missing = Counter()
    content_types = Counter()
    source_tiers = Counter()
    review_statuses = Counter()
    total = 0
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=args.collection,
            limit=args.page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points or []:
            payload = point.payload or {}
            total += 1
            content_types[str(payload.get("content_type") or "missing")] += 1
            source_tiers[str(payload.get("source_tier") or "missing")] += 1
            review_statuses[str(payload.get("medical_review_status") or "missing")] += 1
            for field in REQUIRED_TRUST_FIELDS:
                if not str(payload.get(field) or "").strip():
                    missing[field] += 1
        if offset is None or not points:
            break

    complete = total - max(missing.values(), default=0)
    result = {
        "collection": args.collection,
        "total_points": total,
        "required_fields": list(REQUIRED_TRUST_FIELDS),
        "missing_by_field": dict(missing),
        "complete_points_upper_bound": complete,
        "content_types": dict(content_types),
        "source_tiers": dict(source_tiers),
        "medical_review_statuses": dict(review_statuses),
        "production_metadata_gate": total > 0 and not missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["production_metadata_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
