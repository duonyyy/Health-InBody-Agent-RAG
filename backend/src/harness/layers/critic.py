"""Conservative answer and context critique; not medical entailment proof."""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from harness.guards import (
    has_conflicting_evidence,
    suggests_unsafe_medical_change,
    verify_answer_claims,
    verify_answer_claims_detailed,
)


def context_conflicts(docs: List[Dict[str, Any]]) -> bool:
    return has_conflicting_evidence(docs)


def check_claims(
    answer: str,
    evidence: List[Dict[str, Any]],
    *,
    tool_results: Optional[Sequence[Mapping[str, Any]]] = None,
    safety_result: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    return verify_answer_claims(
        answer,
        evidence,
        tool_results=tool_results,
        safety_result=safety_result,
    )


def check_claims_detailed(
    answer: str,
    evidence: List[Dict[str, Any]],
    *,
    tool_results: Optional[Sequence[Mapping[str, Any]]] = None,
    safety_result: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    return verify_answer_claims_detailed(
        answer,
        evidence,
        tool_results=tool_results,
        safety_result=safety_result,
    )


def caution_answer_is_unsafe(answer: str, action: str) -> bool:
    return action not in answer or suggests_unsafe_medical_change(answer)
