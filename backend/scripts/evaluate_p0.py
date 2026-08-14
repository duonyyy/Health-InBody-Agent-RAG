"""Repeatable HTTP acceptance suite for P0 Trust RAG and Safety."""

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


INTERNAL_ERROR_MARKERS = ("host.docker.internal", "HTTPConnectionPool", ":11434", ":5001")


def load_cases(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def post_json(url: str, payload: dict, timeout: float):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as response:
        return response.code, json.loads(response.read().decode("utf-8"))


def percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return round(ordered[index], 2)


def evaluate_case(api_url: str, case: dict, timeout: float):
    started = time.perf_counter()
    failures = []
    try:
        path = case.get("path") or "/agent/answer"
        request_payload = case.get("payload") or {"question": case["question"]}
        http_status, payload = post_json(
            f"{api_url.rstrip('/')}{path}",
            request_payload,
            timeout,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "id": case["id"],
            "passed": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "failures": [f"request_failed:{type(exc).__name__}"],
        }

    wall_latency = round((time.perf_counter() - started) * 1000, 2)
    expected_http = int(case.get("expected_http", 200))
    if http_status != expected_http:
        failures.append(f"http_status:{http_status}")

    if case.get("kind") == "http_validation":
        response_text = json.dumps(payload, ensure_ascii=False)
        if any(marker in response_text for marker in INTERNAL_ERROR_MARKERS):
            failures.append("internal_error_detail_leaked")
        if wall_latency > float(case.get("max_latency_ms", timeout * 1000)):
            failures.append("latency_budget_exceeded")
        return {
            "id": case["id"],
            "passed": not failures,
            "latency_ms": wall_latency,
            "http_status": http_status,
            "failures": failures,
        }

    selected_agents = set(payload.get("selected_agents") or [])
    required_agents = set(case.get("required_agents") or [])
    forbidden_agents = set(case.get("forbidden_agents") or [])
    if not required_agents.issubset(selected_agents):
        failures.append("missing_required_agents")
    if forbidden_agents.intersection(selected_agents):
        failures.append("forbidden_agent_selected")

    risk = (payload.get("safety_result") or {}).get("risk_level")
    if risk != case.get("expected_risk"):
        failures.append(f"risk:{risk}")

    citations = payload.get("citations") or []
    evidence_status = payload.get("evidence_status") or "not_required"
    if case.get("expected_evidence_status") and evidence_status != case["expected_evidence_status"]:
        failures.append(f"evidence_status:{evidence_status}")
    if case.get("evidence_required") and (evidence_status != "supported" or not citations):
        failures.append("evidence_not_supported")

    citation_ids = {str(item.get("id")) for item in citations}
    answer_refs = set(re.findall(r"\[(\d+)\]", str(payload.get("answer") or "")))
    if not answer_refs.issubset(citation_ids):
        failures.append("invalid_citation_reference")

    allowed_types = set(case.get("allowed_content_types") or [])
    retrieved_types = {
        str(item.get("content_type"))
        for item in (payload.get("retrieved_docs") or [])
        if item.get("content_type")
    }
    if allowed_types and (not retrieved_types or not retrieved_types.issubset(allowed_types)):
        failures.append("retrieval_content_type_gate")

    errors = " | ".join(str(item) for item in (payload.get("errors") or []))
    if any(marker in errors for marker in INTERNAL_ERROR_MARKERS):
        failures.append("internal_error_detail_leaked")
    if payload.get("status") != "ok":
        failures.append(f"status:{payload.get('status')}")
    if wall_latency > float(case.get("max_latency_ms", timeout * 1000)):
        failures.append("latency_budget_exceeded")

    return {
        "id": case["id"],
        "passed": not failures,
        "latency_ms": wall_latency,
        "status": payload.get("status"),
        "risk": risk,
        "agents": sorted(selected_agents),
        "evidence_status": evidence_status,
        "citation_count": len(citations),
        "retrieved_types": sorted(retrieved_types),
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals" / "p0_golden.jsonl",
    )
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    results = [evaluate_case(args.api_url, case, args.timeout) for case in load_cases(args.cases)]
    latencies = [item["latency_ms"] for item in results]
    summary = {
        "passed": all(item["passed"] for item in results),
        "passed_cases": sum(item["passed"] for item in results),
        "total_cases": len(results),
        "latency_p50_ms": round(statistics.median(latencies), 2) if latencies else None,
        "latency_p95_ms": percentile(latencies, 0.95),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
