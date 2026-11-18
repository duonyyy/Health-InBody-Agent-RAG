"""Safe CLI for versioned Qdrant collection creation, verification, and alias activation."""

import argparse
import json
import sys
from pathlib import Path

from core.config import DEFAULT_COLLECTION_ALIAS, DEFAULT_VECTOR_SIZE
from rag.corpus_lifecycle import CorpusLeaseManager, verify_staging_write_target
from rag.qdrant.client import (
    activate_collection_alias,
    client as qdrant_client,
    create_collection,
    ensure_payload_indexes,
    get_alias_target,
    verify_collection_integrity,
)
from rag.qdrant.naming import validate_collection_name


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage versioned Health/InBody Qdrant collections safely"
    )
    parser.add_argument(
        "--lock-dir",
        type=Path,
        default=None,
        help="Optional shared directory for corpus write/activation locks.",
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
    verify_parser.add_argument("--expected-fingerprint", default=None)
    verify_parser.add_argument("--expected-corpus-version", default=None)
    verify_parser.add_argument("--release-manifest", type=Path, default=None)

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
    alias_parser.add_argument("--expected-points", type=int, default=None)
    alias_parser.add_argument("--expected-vector-size", type=int, default=None)
    alias_parser.add_argument("--expected-fingerprint", default=None)
    alias_parser.add_argument("--expected-corpus-version", default=None)
    alias_parser.add_argument("--release-manifest", type=Path, default=None)
    alias_parser.add_argument("--require-verified-eval", action="store_true")

    rollback_parser = subparsers.add_parser("rollback-alias")
    rollback_parser.add_argument(
        "--previous-collection",
        required=True,
        type=validate_collection_name,
    )
    rollback_parser.add_argument(
        "--alias",
        default=DEFAULT_COLLECTION_ALIAS,
        type=validate_collection_name,
    )
    rollback_parser.add_argument("--expected-points", type=int, required=True)
    rollback_parser.add_argument("--expected-fingerprint", default=None)

    target_parser = subparsers.add_parser("alias-target")
    target_parser.add_argument(
        "--alias",
        default=DEFAULT_COLLECTION_ALIAS,
        type=validate_collection_name,
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    manager = CorpusLeaseManager(lock_dir=args.lock_dir)

    try:
        if args.command == "create":
            verify_staging_write_target(
                args.collection,
                qdrant_client=qdrant_client,
                require_corpus_version=False,
                require_allowlist=False,
                dry_run=False,
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
            expected_points = args.expected_points
            expected_vector_size = args.expected_vector_size
            expected_fp = args.expected_fingerprint
            expected_ver = args.expected_corpus_version
            if args.release_manifest:
                from rag.corpus_lifecycle import load_release_manifest

                manifest = load_release_manifest(args.release_manifest)
                chunk_manifest = manifest.get("chunk_manifest") or {}
                emb_cfg = manifest.get("embedding_config") or {}
                if expected_points is None:
                    expected_points = chunk_manifest.get("expected_count")
                if expected_fp is None:
                    expected_fp = chunk_manifest.get("chunk_set_fingerprint")
                if expected_ver is None:
                    expected_ver = manifest.get("corpus_version")
                if emb_cfg.get("vector_size"):
                    expected_vector_size = int(emb_cfg["vector_size"])

            result = verify_collection_integrity(
                args.collection,
                expected_points=expected_points,
                expected_vector_size=expected_vector_size,
                expected_chunk_set_fingerprint=expected_fp,
                expected_corpus_version=expected_ver,
            )
            if not result["verified"]:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
                return 1
        elif args.command == "ensure-indexes":
            verify_staging_write_target(
                args.collection,
                qdrant_client=qdrant_client,
                require_corpus_version=False,
                require_allowlist=False,
                dry_run=False,
            )
            result = {
                "status": True,
                "collection": args.collection,
                "payload_indexes": ensure_payload_indexes(
                    args.collection,
                    raise_on_error=True,
                ),
            }
        elif args.command == "activate-alias":
            if args.expected_points is None and args.release_manifest is None:
                raise ValueError(
                    "activate-alias requires --expected-points or --release-manifest"
                )
            result = activate_collection_alias(
                args.collection,
                args.alias,
                expected_points=args.expected_points,
                expected_vector_size=args.expected_vector_size,
                expected_chunk_set_fingerprint=args.expected_fingerprint,
                expected_corpus_version=args.expected_corpus_version,
                release_manifest_path=args.release_manifest,
                require_verified_eval=args.require_verified_eval,
                lease_manager=manager,
            )
        elif args.command == "rollback-alias":
            result = activate_collection_alias(
                args.previous_collection,
                args.alias,
                expected_points=args.expected_points,
                expected_chunk_set_fingerprint=args.expected_fingerprint,
                lease_manager=manager,
            )
            result["operation"] = "rollback_alias"
        else:
            result = {
                "alias": args.alias,
                "active_collection": get_alias_target(args.alias),
            }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": False,
                    "command": args.command,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
