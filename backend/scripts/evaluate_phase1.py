"""Offline, read-only Phase-1 evaluation on a pinned BM25 snapshot.

Default runs development cases only. It never writes to Qdrant, calls an LLM,
or treats citation syntax as proof that an answer is clinically supported.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_CASES = BACKEND / "evals" / "phase1" / "cases_v1.jsonl"
DEFAULT_SNAPSHOT = BACKEND / "data" / "generated" / "bm25_snapshot.json.gz"
GROUPS = {
    "routing", "retrieval", "claim_citation", "safety", "prompt_injection",
    "insufficient_evidence", "tool_failure",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        required = (
            "case_id", "suite_version", "corpus_version", "group", "split",
            "source", "query", "expected_content_type", "relevant_document_ids",
            "forbidden_document_ids", "expected", "review",
        )
        missing = [key for key in required if key not in case]
        if missing:
            raise ValueError(f"line {number}: missing {missing}")
        if case["case_id"] in seen:
            raise ValueError(f"line {number}: duplicate case_id {case['case_id']}")
        seen.add(case["case_id"])
        if case["group"] not in GROUPS or case["split"] not in ("development", "holdout"):
            raise ValueError(f"line {number}: invalid group/split")
        if not isinstance(case["relevant_document_ids"], list) or not isinstance(case["forbidden_document_ids"], list):
            raise ValueError(f"line {number}: document IDs must be lists")
        if not case["review"].get("reviewer") or not case["review"].get("status") or not case["review"].get("reason"):
            raise ValueError(f"line {number}: incomplete review provenance")
        cases.append(case)
    if not cases:
        raise ValueError("empty evaluation suite")
    if len({case["suite_version"] for case in cases}) != 1:
        raise ValueError("mixed suite versions")
    return cases


def load_snapshot_header(path: Path) -> tuple[dict[str, Any], set[str], dict[str, int]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    documents = snapshot.get("documents", [])
    if snapshot.get("document_count") != len(documents):
        raise ValueError("snapshot document count mismatch")
    ids = [document.get("doc_id") for document in documents]
    return snapshot, set(ids), {
        "unique_document_ids": len(set(ids)),
        "duplicate_id_rows": len(ids) - len(set(ids)),
        "duplicate_id_values": sum(count > 1 for count in Counter(ids).values()),
    }


def retrieval_result(documents: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    ids = list(dict.fromkeys(item["doc_id"] for item in documents))
    relevant = set(case["relevant_document_ids"])
    forbidden = set(case["forbidden_document_ids"])
    hits = len(relevant.intersection(ids))
    rank = next((position for position, doc_id in enumerate(ids, 1) if doc_id in relevant), None)
    expected_type = case["expected_content_type"]
    type_errors = sum(item.get("content_type") != expected_type for item in documents)
    return {
        "document_ids": ids,
        "raw_result_count": len(documents),
        "duplicate_result_ids": len(documents) - len(ids),
        "recall_at_k": hits / len(relevant) if relevant else None,
        "precision_at_k": hits / len(ids) if ids else 0.0,
        "reciprocal_rank": 1 / rank if rank else 0.0,
        "forbidden_hits": sorted(forbidden.intersection(ids)),
        "wrong_content_type_count": type_errors,
        "passed": bool(relevant) and hits == len(relevant) and not forbidden.intersection(ids) and type_errors == 0,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.cases)
    snapshot, known_ids, duplicate_stats = load_snapshot_header(args.snapshot)
    corpus_version = snapshot.get("metadata", {}).get("corpus_version")
    if not corpus_version or any(case["corpus_version"] != corpus_version for case in cases):
        raise ValueError("fixture corpus_version does not match snapshot")
    missing_ids = sorted({doc_id for case in cases for doc_id in (
        case["relevant_document_ids"] + case["forbidden_document_ids"]
    ) if doc_id not in known_ids})
    if missing_ids:
        raise ValueError(f"fixture IDs absent from snapshot: {missing_ids}")

    selected = [case for case in cases if case["split"] == args.split]
    if not selected:
        raise ValueError(f"no {args.split} cases")
    sys.path.insert(0, str(BACKEND / "src"))
    from agents.graph import supervisor_agent
    from health.tools import check_medical_safety
    from rag.search import bm25_search, get_search_stats, load_search_snapshot

    if not load_search_snapshot(args.snapshot):
        raise RuntimeError("current BM25 code could not load pinned snapshot")
    stats = get_search_stats()
    details = []
    for case in selected:
        group = case["group"]
        result: dict[str, Any] = {"case_id": case["case_id"], "group": group}
        if group == "routing":
            state = {"question": case["query"], "history": [], "safety_result": {}}
            actual = supervisor_agent(state).get("selected_agents", [])
            expected = case["expected"]["selected_agents"]
            result.update(status="measured", actual_agents=actual,
                          expected_agents=expected, passed=set(actual) == set(expected))
        elif group == "safety":
            actual = check_medical_safety(case["query"]).get("risk_level")
            result.update(status="partial", actual_risk=actual,
                          expected_risk=case["expected"]["risk_level"],
                          passed=actual == case["expected"]["risk_level"],
                          unmeasured=["fast_path", "LLM/retrieval calls", "response safety"])
        elif group == "retrieval":
            k = case["expected"].get("top_k", 5)
            content_type = case["expected"].get("filter_content_type")
            variants = {
                "current_bm25_filtered": bm25_search(case["query"], k, {"content_type": content_type}),
                "topk_unfiltered": bm25_search(case["query"], k),
            }
            result.update(status="measured", variants={
                name: retrieval_result(docs, case) for name, docs in variants.items()
            })
            # A blind dump is exactly unfiltered top-k copied as answer. It can
            # have valid IDs, but semantic/clinical claim support is NOT measured.
            result["variants"]["blind_retrieval_dump"] = {
                **retrieval_result(variants["topk_unfiltered"], case),
                "answer_sha256": hashlib.sha256("\n\n".join(
                    str(doc.get("content") or "") for doc in variants["topk_unfiltered"]
                ).encode("utf-8")).hexdigest(),
                "answer_char_count": sum(len(str(doc.get("content") or ""))
                                         for doc in variants["topk_unfiltered"]),
                "claim_support": "not_measured",
                "answer_policy": "copy_top_k_without_synthesis",
            }
        else:
            result.update(status="not_measured", reason=(
                "Requires isolated evidence/tool fault fixture and response-level runtime review; "
                "offline BM25 cannot score this contract."
            ))
        details.append(result)

    counts = Counter(case["group"] for case in selected)
    summary: dict[str, Any] = {}
    for group in sorted(counts):
        rows = [row for row in details if row["group"] == group]
        summary[group] = {
            "case_count": len(rows),
            "measured": sum(row["status"] == "measured" for row in rows),
            "partial": sum(row["status"] == "partial" for row in rows),
            "not_measured": sum(row["status"] == "not_measured" for row in rows),
            "failed_case_ids": [row["case_id"] for row in rows if row.get("passed") is False],
        }
    retrieval_rows = [row for row in details if row["group"] == "retrieval"]
    for variant in ("current_bm25_filtered", "topk_unfiltered", "blind_retrieval_dump"):
        if retrieval_rows:
            items = [row["variants"][variant] for row in retrieval_rows]
            summary["retrieval"][variant] = {
                "mean_recall_at_k": sum(item["recall_at_k"] for item in items) / len(items),
                "mean_precision_at_k": sum(item["precision_at_k"] for item in items) / len(items),
                "mrr": sum(item["reciprocal_rank"] for item in items) / len(items),
                "passed": sum(item["passed"] for item in items),
                "forbidden_case_count": sum(bool(item["forbidden_hits"]) for item in items),
                "wrong_type_document_count": sum(item["wrong_content_type_count"] for item in items),
                "failed_case_ids": [row["case_id"] for row in retrieval_rows
                                    if not row["variants"][variant]["passed"]],
                "duplicate_result_ids": sum(item["duplicate_result_ids"] for item in items),
            }
    return {
        "schema_version": 1,
        "suite_version": cases[0]["suite_version"],
        "split": args.split,
        "case_count": len(selected),
        "holdout_excluded_by_default": args.split == "development",
        "fixture_sha256": sha256_file(args.cases),
        "snapshot_sha256": sha256_file(args.snapshot),
        "corpus_version": corpus_version,
        "collection_name": snapshot["collection_name"],
        "snapshot_document_count": snapshot["document_count"],
        "snapshot_id_stats": duplicate_stats,
        "search_stats": stats,
        "code_sha256": {name: sha256_file(BACKEND / path) for name, path in {
            "search": "src/rag/search.py", "graph": "src/agents/graph.py",
            "safety": "src/health/tools.py",
        }.items()},
        "model_config": "none; offline deterministic only",
        "review_status": dict(Counter(case["review"]["status"] for case in selected)),
        "clinical_review_pending": sum(case["review"].get("clinical_review") == "pending" for case in selected),
        "summary": summary,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--output", type=Path, help="Optional path for JSON report")
    args = parser.parse_args()
    report = run(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.output}; cases={report['case_count']}; split={args.split}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
