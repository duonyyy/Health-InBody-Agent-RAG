"""Contracts for the read-only Phase-1 evaluation harness."""

import json
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
from scripts.evaluate_phase1 import load_cases, retrieval_result  # noqa: E402


def test_fixture_has_all_groups_and_separate_holdout():
    cases = load_cases(BACKEND / "evals" / "phase1" / "cases_v1.jsonl")
    assert {case["group"] for case in cases} == {
        "routing", "retrieval", "claim_citation", "safety",
        "prompt_injection", "insufficient_evidence", "tool_failure",
    }
    assert {case["split"] for case in cases} == {"development", "holdout"}
    assert all(case["review"].get("clinical_review") for case in cases)


def test_duplicate_case_id_is_rejected():
    case = load_cases(BACKEND / "evals" / "phase1" / "cases_v1.jsonl")[0]
    class InMemoryPath:
        def read_text(self, encoding):
            assert encoding == "utf-8"
            return json.dumps(case) + "\n" + json.dumps(case)

    with pytest.raises(ValueError, match="duplicate case_id"):
        load_cases(InMemoryPath())


def test_retrieval_deduplicates_ids_but_records_duplicate_rows():
    case = {
        "relevant_document_ids": ["a"],
        "forbidden_document_ids": ["x"],
        "expected_content_type": "medical_safety",
    }
    result = retrieval_result([
        {"doc_id": "a", "content_type": "medical_safety"},
        {"doc_id": "a", "content_type": "medical_safety"},
        {"doc_id": "x", "content_type": "nutrition"},
    ], case)
    assert result["document_ids"] == ["a", "x"]
    assert result["duplicate_result_ids"] == 1
    assert result["forbidden_hits"] == ["x"]
    assert result["passed"] is False
