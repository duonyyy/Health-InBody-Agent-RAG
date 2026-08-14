"""Build a versioned BM25 snapshot from Qdrant payloads without mutating Qdrant."""

import argparse
import json
import sys

from rag.search import (
    BM25_SNAPSHOT_PATH,
    get_search_stats,
    initialize_from_vector_store,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--output", default=BM25_SNAPSHOT_PATH)
    args = parser.parse_args()
    if args.page_size < 1 or args.page_size > 10000:
        parser.error("--page-size must be between 1 and 10000")

    status = initialize_from_vector_store(
        limit=args.page_size,
        persist_snapshot=True,
        snapshot_path=args.output,
    )
    result = {"status": status, "snapshot_path": args.output, "search": get_search_stats()}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status else 1


if __name__ == "__main__":
    sys.exit(main())
