"""Conservative answer and context critique; not medical entailment proof."""

from typing import Any, Dict, List, Tuple

from harness.guards import has_conflicting_evidence, suggests_unsafe_medical_change, verify_answer_claims


def context_conflicts(docs: List[Dict[str, Any]]) -> bool:
    return has_conflicting_evidence(docs)


def check_claims(answer: str, evidence: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    return verify_answer_claims(answer, evidence)


def caution_answer_is_unsafe(answer: str, action: str) -> bool:
    return action not in answer or suggests_unsafe_medical_change(answer)
