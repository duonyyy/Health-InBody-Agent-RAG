"""Safe CLI for versioned Qdrant collection creation and alias activation."""

import argparse
import json

from core.config import DEFAULT_COLLECTION_ALIAS, DEFAULT_VECTOR_SIZE
from rag.qdrant.client import (
    activate_collection_alias,
    create_collection,
    ensure_payload_indexes,
    get_alias_target,
    get_collection_stats,
)
from rag.qdrant.naming import validate_collection_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage versioned Health/InBody Qdrant collections safely"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--collection", required=True, type=validate_collection_name)
    create_parser.add_argument("--vector-size", type=int, default=DEFAULT_VECTOR_SIZE)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--collection", required=True, type=validate_collection_name)
    verify_parser.add_argument("--expected-points", type=int, default=None)
    verify_parser.add_argument(
        "--expected-vector-size",
        type=int,
        default=DEFAULT_VECTOR_SIZE,
    )

    index_parser = subparsers.add_parser("ensure-indexes")
    index_parser.add_argument(
        "--collection",
        required=True,
        type=validate_collection_name,
    )

    alias_parser = subparsers.add_parser("activate-alias")
    alias_parser.add_argument("--collection", required=True, type=validate_collection_name)
    alias_parser.add_argument(
        "--alias",
        default=DEFAULT_COLLECTION_ALIAS,
        type=validate_collection_name,
    )
    alias_parser.add_argument("--expected-points", required=True, type=int)

    target_parser = subparsers.add_parser("alias-target")
    target_parser.add_argument(
        "--alias",
        default=DEFAULT_COLLECTION_ALIAS,
        type=validate_collection_name,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "create":
        if args.collection == DEFAULT_COLLECTION_ALIAS:
            raise ValueError(
                "Create a versioned physical collection, not the stable runtime alias"
            )
        create_collection(args.collection, vector_size=args.vector_size)
        result = {
            "status": True,
            "collection": args.collection,
            "vector_size": args.vector_size,
            "payload_indexes": ensure_payload_indexes(
                args.collection,
                raise_on_error=True,
            ),
        }
    elif args.command == "verify":
        result = get_collection_stats(args.collection)
        if "error" in result:
            raise RuntimeError(result["error"])
        if (
            args.expected_points is not None
            and int(result["points_count"] or 0) != args.expected_points
        ):
            raise ValueError(
                f"Expected {args.expected_points} points, "
                f"found {result['points_count']}"
            )
        if result["vector_size"] != args.expected_vector_size:
            raise ValueError(
                f"Expected vector size {args.expected_vector_size}, "
                f"found {result['vector_size']}"
            )
        result["verified"] = True
    elif args.command == "ensure-indexes":
        result = {
            "status": True,
            "collection": args.collection,
            "payload_indexes": ensure_payload_indexes(
                args.collection,
                raise_on_error=True,
            ),
        }
    elif args.command == "activate-alias":
        result = activate_collection_alias(
            args.collection,
            args.alias,
            expected_points=args.expected_points,
        )
    else:
        result = {
            "alias": args.alias,
            "active_collection": get_alias_target(args.alias),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
