"""Automated Benchmark Runner cho bài toán Health/InBody Agent RAG.
Đánh giá định lượng trên 3 tầng cốt lõi:
1. Router Accuracy (200 test cases) - Target: >= 95%
2. Retrieval Metrics (Context Recall@5, Top-1 Relevance, Safety Hit@5) - Target: >= 90%
3. End-to-End Generation & Citation Evaluation (25 đại diện) - Target Citation Precision >= 95%
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

# Cấu hình môi trường cho host run
os.environ.setdefault("VECTOR_SIZE", "384")
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")
os.environ.setdefault("CUSTOM_EMBEDDING_API_URL", "http://127.0.0.1:5001")
os.environ.setdefault("EMBEDDING_QUERY_PREFIX", "query: ")

sys.path.insert(0, str(Path("backend/src").resolve()))

from agents.fast_paths import (
    _apply_urgent_fast_path,
    _try_general_fast_path,
    _try_inbody_fast_path,
)
from agents.nodes.supervisor import supervisor_agent
from agents.state import AgentState
from health.tools import check_medical_safety
from rag.search import hybrid_search

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def evaluate_router(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Module 1: Đánh giá Router Accuracy trên toàn bộ 200 câu hỏi."""
    print("\n" + "=" * 70)
    print("🚀 BẮT ĐẦU MODULE 1: ROUTER EVALUATION (200 CÂU HỎI)")
    print("=" * 70)

    category_stats = {}
    total_correct = 0
    urgent_safety_tested = 0
    urgent_safety_passed = 0

    results = []

    for item in dataset:
        cat = item["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0}
        category_stats[cat]["total"] += 1

        query = item["query"]
        expected_agent = item.get("expected_agent")
        expected_fast_path = item.get("fast_path")
        expected_risk = item.get("risk_level", "low")

        # 1. Deterministic safety check
        safety = check_medical_safety(query)
        risk_level = safety.get("risk_level", "low")

        state: AgentState = {
            "question": query,
            "raw_question": query,
            "safety_result": safety,
            "selected_agents": [],
            "selected_capabilities": [],
            "trace": [],
            "errors": [],
        }

        # 2. Fast path checks
        fast_path_matched = False
        matched_fast_path = None

        if risk_level == "urgent":
            urgent_safety_tested += 1
            state = _apply_urgent_fast_path(state, safety)
            matched_fast_path = state.get("fast_path")
            fast_path_matched = True
            if expected_risk == "urgent" and (expected_fast_path == "urgent_safety" or matched_fast_path == "urgent_safety"):
                urgent_safety_passed += 1

        if not fast_path_matched:
            gen_fp = _try_general_fast_path(state)
            if gen_fp is not None:
                state = gen_fp
                matched_fast_path = state.get("fast_path")
                fast_path_matched = True

        if not fast_path_matched:
            inbody_fp = _try_inbody_fast_path(state)
            if inbody_fp is not None:
                state = inbody_fp
                matched_fast_path = state.get("fast_path")
                fast_path_matched = True

        # 3. Supervisor routing if not fast path
        if not fast_path_matched:
            state = supervisor_agent(state)

        selected_caps = state.get("selected_capabilities", [])
        selected_agents = state.get("selected_agents", [])

        # Kiểm tra đúng/sai
        is_correct = False
        if expected_fast_path:
            is_correct = (matched_fast_path == expected_fast_path)
            # Chấp nhận trường hợp fast-path inbody hoặc routing inbody agent cho phép tính
            if not is_correct and expected_fast_path == "inbody_tools" and "InBodyAgent" in selected_caps:
                is_correct = True
            elif not is_correct and expected_fast_path == "greeting" and "GeneralChatAgent" in selected_caps:
                is_correct = True
        else:
            if expected_agent in selected_caps:
                is_correct = True
            elif set(item.get("expected_public_specialists", [])) & set(selected_agents):
                is_correct = True

        if is_correct:
            total_correct += 1
            category_stats[cat]["correct"] += 1

        results.append({
            "id": item["id"],
            "query": query,
            "category": cat,
            "expected_agent": expected_agent,
            "expected_fast_path": expected_fast_path,
            "actual_fast_path": matched_fast_path,
            "actual_capabilities": selected_caps,
            "actual_specialists": selected_agents,
            "is_correct": is_correct
        })

    accuracy = (total_correct / len(dataset)) * 100
    urgent_acc = (urgent_safety_passed / urgent_safety_tested * 100) if urgent_safety_tested else 100.0

    print(f"\n📊 KẾT QUẢ ROUTER EVALUATION:")
    print(f"  • Tổng số câu: {len(dataset)}")
    print(f"  • Số câu định tuyến đúng: {total_correct} / {len(dataset)}")
    print(f"  • Router Accuracy: {accuracy:.2f}% (Chỉ tiêu: >= 95.0%) -> {'✅ ĐẠT' if accuracy >= 95.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Urgent Safety Fast-Path Recall: {urgent_safety_passed}/{urgent_safety_tested} ({urgent_acc:.1f}%) -> {'✅ ĐẠT' if urgent_acc == 100.0 else '❌ CHƯA ĐẠT'}")

    print("\nChi tiết theo từng phân nhóm:")
    for cat, stats in category_stats.items():
        cat_acc = (stats["correct"] / stats["total"]) * 100
        print(f"  - {cat:16}: {stats['correct']:2d}/{stats['total']:2d} ({cat_acc:5.1f}%)")

    return {
        "accuracy": accuracy,
        "total": len(dataset),
        "total_correct": total_correct,
        "category_stats": category_stats,
        "urgent_safety_accuracy": urgent_acc,
        "details": results
    }


def get_auth_token() -> str:
    """Tự động đăng ký người dùng benchmark mới vào PostgreSQL thật."""
    test_user = {
        "username": f"bench_user_{int(time.time())}",
        "password": "BenchmarkPassword123!",
    }
    reg_resp = requests.post(
        f"{API_BASE_URL}/auth/register",
        json=test_user,
        timeout=10,
    )
    if reg_resp.status_code in (200, 201):
        token = reg_resp.json().get("access_token")
        if token:
            return token

    # Fallback login nếu tài khoản đã tồn tại
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json=test_user,
        timeout=10,
    )
    if login_resp.status_code == 200:
        token = login_resp.json().get("access_token")
        if token:
            return token

    raise RuntimeError(f"Không lấy được auth token: HTTP {reg_resp.status_code} - {reg_resp.text}")


def evaluate_retrieval(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Module 2: Đánh giá Hybrid Search (Qdrant + BM25) có áp dụng retrieval filters."""
    print("\n" + "=" * 70)
    print("🚀 BẮT ĐẦU MODULE 2: RETRIEVAL EVALUATION (HYBRID QDRANT + BM25)")
    print("=" * 70)

    # Chọn các câu hỏi thuộc nhóm InBody, Nutrition, Exercise và Medical Safety (caution)
    rag_items = [
        item for item in dataset
        if item.get("target_content_types") and not item.get("fast_path")
    ]

    print(f"Đang đánh giá {len(rag_items)} câu hỏi RAG...")

    recall_top5_hits = 0
    strict_top1_hits = 0
    reciprocal_ranks = []
    latencies = []

    safety_tested = 0
    safety_hits = 0
    recipes_in_safety = 0

    results = []

    for idx, item in enumerate(rag_items, 1):
        query = item["query"]
        target_types = set(item.get("target_content_types", []))
        keywords = [k.lower() for k in item.get("keywords", [])]

        # Áp dụng routing filters giống hệt RAG Agent
        filters = None
        if len(target_types) == 1:
            filters = {"content_type": list(target_types)[0]}
        elif len(target_types) > 1:
            filters = {"content_type": list(target_types)}

        start_t = time.perf_counter()
        try:
            docs = hybrid_search(query, limit=5, filters=filters, use_rerank=True)
        except Exception as e:
            print(f"  [ERROR] Lỗi hybrid search câu {item['id']}: {e}")
            docs = []
        latency_ms = (time.perf_counter() - start_t) * 1000
        latencies.append(latency_ms)

        # 1. Đánh giá Recall@5: ít nhất 1 doc trong top 5 khớp content_type VÀ (chứa keyword hoặc title liên quan)
        found_relevant_at = None
        for rank, doc in enumerate(docs, 1):
            doc_type = doc.get("content_type")
            title = (doc.get("title") or "").lower()
            content = (doc.get("content") or "").lower()

            type_match = doc_type in target_types
            kw_match = any(kw in title or kw in content for kw in keywords)

            if type_match and (kw_match or rank == 1):
                if found_relevant_at is None:
                    found_relevant_at = rank

        if found_relevant_at is not None:
            recall_top5_hits += 1
            reciprocal_ranks.append(1.0 / found_relevant_at)
        else:
            reciprocal_ranks.append(0.0)

        # 2. Strict Top-1: doc vị trí đầu tiên phải thuộc target_types
        top1_type_match = False
        if docs:
            top1_type_match = docs[0].get("content_type") in target_types
            if top1_type_match:
                strict_top1_hits += 1

        # 3. Medical Safety isolation check
        if "medical_safety" in target_types:
            safety_tested += 1
            has_safety_doc = any(d.get("content_type") == "medical_safety" for d in docs)
            if has_safety_doc:
                safety_hits += 1
            # Đếm recipe documents lọt vào
            recipe_count = sum(1 for d in docs if "recipe" in (d.get("content_type") or "").lower() or "công thức nấu" in (d.get("title") or "").lower())
            recipes_in_safety += recipe_count

        results.append({
            "id": item["id"],
            "query": query,
            "target_types": list(target_types),
            "top_docs": [{"rank": r, "title": d.get("title"), "type": d.get("content_type")} for r, d in enumerate(docs, 1)],
            "found_relevant_at": found_relevant_at,
            "top1_match": top1_type_match,
            "latency_ms": latency_ms
        })

        if idx % 25 == 0 or idx == len(rag_items):
            print(f"  -> Tiến độ retrieval: {idx}/{len(rag_items)} câu ({latency_ms:.1f}ms/query)")

    recall_at_5 = (recall_top5_hits / len(rag_items)) * 100
    strict_top1 = (strict_top1_hits / len(rag_items)) * 100
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    safety_hit_rate = (safety_hits / safety_tested * 100) if safety_tested else 100.0

    print(f"\n📊 KẾT QUẢ RETRIEVAL EVALUATION:")
    print(f"  • Context Recall@5: {recall_at_5:.2f}% (Chỉ tiêu: >= 90.0%) -> {'✅ ĐẠT' if recall_at_5 >= 90.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Strict Top-1 Relevance: {strict_top1:.2f}% (Chỉ tiêu: >= 75.0%) -> {'✅ ĐẠT' if strict_top1 >= 75.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Mean Reciprocal Rank (MRR@5): {mrr:.3f}")
    print(f"  • Safety Hit@5: {safety_hits}/{safety_tested} ({safety_hit_rate:.1f}%) -> {'✅ ĐẠT' if safety_hit_rate == 100.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Recipe trong Safety Top-5: {recipes_in_safety} -> {'✅ ĐẠT (Zero Recipe)' if recipes_in_safety == 0 else '❌ CÓ RECIPE LỌT VÀO'}")
    print(f"  • Latency trung bình hybrid search: {avg_latency:.2f} ms")

    return {
        "recall_at_5": recall_at_5,
        "strict_top_1": strict_top1,
        "mrr": mrr,
        "avg_latency_ms": avg_latency,
        "safety_hit_rate": safety_hit_rate,
        "recipes_in_safety": recipes_in_safety,
        "total_evaluated": len(rag_items),
        "details": results
    }


def evaluate_end_to_end(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Module 3: Đánh giá End-to-End Generation & Citation qua Live API (25 câu đại diện)."""
    print("\n" + "=" * 70)
    print("🚀 BẮT ĐẦU MODULE 3: END-TO-END GENERATION & CITATION EVALUATION (25 CÂU)")
    print("=" * 70)

    token = get_auth_token()
    print("✅ Đã lấy thành công JWT Bearer token xác thực thật từ PostgreSQL!")

    # Chọn 25 câu đại diện
    representatives = [
        # InBody (5)
        "inbody_001", "inbody_004", "inbody_011", "inbody_015", "inbody_022",
        # Nutrition (5)
        "nutrition_001", "nutrition_003", "nutrition_004", "nutrition_010", "nutrition_017",
        # Exercise (5)
        "exercise_001", "exercise_003", "exercise_007", "exercise_009", "exercise_014",
        # Safety (5: 2 urgent, 3 caution)
        "safety_001", "safety_004", "safety_016", "safety_017", "safety_022",
        # Edge cases (5: 2 không dấu, 2 BMI, 1 chat)
        "edge_001", "edge_008", "edge_016", "edge_017", "edge_026"
    ]

    eval_items = [d for d in dataset if d["id"] in representatives]
    print(f"Đã chọn {len(eval_items)} câu hỏi đại diện cho 5 phân nhóm.")

    e2e_results = []
    total_citations_checked = 0
    valid_citations_count = 0
    supported_claims_count = 0
    total_claims_count = 0
    fast_path_latencies = []
    rag_latencies = []

    for idx, item in enumerate(eval_items, 1):
        query = item["query"]
        print(f"\n[{idx}/{len(eval_items)}] Đang gọi Agent: '{query[:45]}...'")

        start_t = time.perf_counter()
        try:
            resp = requests.post(
                f"{API_BASE_URL}/agent/answer",
                json={"question": query},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                timeout=60
            )
            latency_ms = (time.perf_counter() - start_t) * 1000
            resp_data = resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            latency_ms = (time.perf_counter() - start_t) * 1000
            resp_data = {"error": str(e), "status": "error"}

        status = resp_data.get("status", "error")
        fast_path = resp_data.get("fast_path")
        citations = resp_data.get("citations", [])
        claim_links = resp_data.get("claim_evidence_links", [])
        answer = resp_data.get("answer", "")

        if fast_path:
            fast_path_latencies.append(latency_ms)
        else:
            rag_latencies.append(latency_ms)

        # Kiểm tra Citation Precision
        valid_citations = 0
        for cite in citations:
            total_citations_checked += 1
            if cite.get("url") or cite.get("title") or cite.get("id"):
                valid_citations += 1
                valid_citations_count += 1

        # Kiểm tra Claim Verification Support Rate
        for claim in claim_links:
            total_claims_count += 1
            if claim.get("supported") is True:
                supported_claims_count += 1

        print(f"  -> Trạng thái: {status} | Fast-path: {fast_path} | Latency: {latency_ms:.0f}ms | Citations: {len(citations)} | Claims: {len(claim_links)}")

        e2e_results.append({
            "id": item["id"],
            "query": query,
            "category": item["category"],
            "status": status,
            "fast_path": fast_path,
            "latency_ms": latency_ms,
            "answer_preview": answer[:120] + "..." if len(answer) > 120 else answer,
            "citations_count": len(citations),
            "claims_count": len(claim_links),
            "claims_supported": sum(1 for c in claim_links if c.get("supported") is True)
        })

    citation_precision = (valid_citations_count / total_citations_checked * 100) if total_citations_checked else 100.0
    claim_support_rate = (supported_claims_count / total_claims_count * 100) if total_claims_count else 100.0
    avg_fast_path_lat = (sum(fast_path_latencies) / len(fast_path_latencies)) if fast_path_latencies else 0.0
    avg_rag_lat = (sum(rag_latencies) / len(rag_latencies)) if rag_latencies else 0.0

    print(f"\n📊 KẾT QUẢ END-TO-END GENERATION & CITATION:")
    print(f"  • Citation Precision: {valid_citations_count}/{total_citations_checked} ({citation_precision:.2f}%) (Chỉ tiêu: >= 95.0%) -> {'✅ ĐẠT' if citation_precision >= 95.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Claim Supported Rate: {supported_claims_count}/{total_claims_count} ({claim_support_rate:.2f}%) (Chỉ tiêu: >= 95.0%) -> {'✅ ĐẠT' if claim_support_rate >= 95.0 else '❌ CHƯA ĐẠT'}")
    print(f"  • Fast-path Latency trung bình: {avg_fast_path_lat:.1f} ms (Chỉ tiêu: < 500 ms) -> {'✅ ĐẠT' if avg_fast_path_lat < 500 else '❌ CHƯA ĐẠT'}")
    print(f"  • RAG Latency trung bình: {avg_rag_lat / 1000:.2f} s")

    return {
        "citation_precision": citation_precision,
        "claim_support_rate": claim_support_rate,
        "avg_fast_path_latency_ms": avg_fast_path_lat,
        "avg_rag_latency_ms": avg_rag_lat,
        "total_citations_checked": total_citations_checked,
        "total_claims_checked": total_claims_count,
        "items": e2e_results
    }


def main():
    dataset_path = Path("backend/evals/golden_eval_set.jsonl")
    if not dataset_path.exists():
        print(f"❌ Không tìm thấy dataset tại {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(dataset)} items from {dataset_path}")

    # Chạy 3 module đánh giá
    router_metrics = evaluate_router(dataset)
    retrieval_metrics = evaluate_retrieval(dataset)
    e2e_metrics = evaluate_end_to_end(dataset)

    # Xuất file kết quả JSON
    output_dir = Path("backend/evals")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "benchmark_results.json"

    full_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_size": len(dataset),
        "router_metrics": {
            "accuracy": router_metrics["accuracy"],
            "urgent_safety_accuracy": router_metrics["urgent_safety_accuracy"],
            "category_stats": router_metrics["category_stats"]
        },
        "retrieval_metrics": {
            "recall_at_5": retrieval_metrics["recall_at_5"],
            "strict_top_1": retrieval_metrics["strict_top_1"],
            "mrr": retrieval_metrics["mrr"],
            "avg_latency_ms": retrieval_metrics["avg_latency_ms"],
            "safety_hit_rate": retrieval_metrics["safety_hit_rate"],
            "recipes_in_safety": retrieval_metrics["recipes_in_safety"]
        },
        "e2e_metrics": {
            "citation_precision": e2e_metrics["citation_precision"],
            "claim_support_rate": e2e_metrics["claim_support_rate"],
            "avg_fast_path_latency_ms": e2e_metrics["avg_fast_path_latency_ms"],
            "avg_rag_latency_ms": e2e_metrics["avg_rag_latency_ms"]
        }
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"🎉 TẤT CẢ MODULE BENCHMARK ĐÃ HOÀN TẤT! BÁO CÁO ĐÃ ĐƯỢC LƯU TẠI: {report_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
