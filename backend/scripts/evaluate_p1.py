"""Repeatable HTTP acceptance checks for P1 personalization.

Run against a local development-auth API. It creates synthetic users whose
subjects start with ``p1-eval-``; production deployments must not enable the
development header used by this script.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone


BASE_URL = "http://localhost:8000"


def request(method, path, *, user=None, body=None):
    headers = {"Content-Type": "application/json"}
    if user:
        headers["X-Dev-User-Id"] = user
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=payload,
        headers=headers,
        method=method,
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None, round(
                (time.perf_counter() - started) * 1000, 2
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else None, round(
            (time.perf_counter() - started) * 1000, 2
        )


def wait_for_api(timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            status, _, _ = request("GET", "/health")
            if status == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"API did not become ready within {timeout_seconds}s") from last_error


def main():
    wait_for_api()
    suffix = uuid.uuid4().hex[:10]
    user_a = f"p1-eval-a-{suffix}"
    user_b = f"p1-eval-b-{suffix}"
    user_read_only = f"p1-eval-read-{suffix}"
    checks = []

    def check(name, condition, detail=None, latency_ms=None):
        checks.append(
            {
                "name": name,
                "passed": bool(condition),
                "detail": detail,
                "latency_ms": latency_ms,
            }
        )

    status, _, latency = request("GET", "/me/profile")
    check("unauthenticated_me_blocked", status == 401, status, latency)
    status, empty_profile, latency = request(
        "GET", "/me/profile", user=user_read_only
    )
    check(
        "empty_profile_get_has_no_implicit_health_data",
        status == 200
        and empty_profile.get("updated_at") is None
        and empty_profile.get("consent_flags", {}).get("health_data_processing") is False,
        status,
        latency,
    )

    base_profile = {
        "display_name": "Synthetic P1 User",
        "age_range": "25_34",
        "sex_at_birth": "male",
        "height_cm": 170,
        "activity_level": "moderate",
        "dietary_preferences": ["ít muối"],
        "consent_flags": {
            "health_data_processing": True,
            "personalization": True,
        },
    }
    for subject in (user_a, user_b):
        status, profile, latency = request(
            "PUT", "/me/profile", user=subject, body=base_profile
        )
        check(
            f"profile_upsert_{subject[8]}",
            status == 200 and "email" not in profile and "external_id" not in profile,
            status,
            latency,
        )

    now = datetime.now(timezone.utc)
    measurements = [
        (now - timedelta(days=21), 90, False),
        (now - timedelta(days=14), 78, True),
        (now - timedelta(days=7), 77, True),
    ]
    ids = []
    for measured_at, weight, confirmed in measurements:
        status, item, latency = request(
            "POST",
            "/me/measurements",
            user=user_a,
            body={
                "measured_at": measured_at.isoformat(),
                "height_cm": 170,
                "weight_kg": weight,
                "source_type": "manual_confirmed" if confirmed else "ocr_unconfirmed",
                "confirmed_by_user": confirmed,
                "confidence": 0.99 if confirmed else 0.5,
            },
        )
        check(f"measurement_create_{weight}", status == 201, status, latency)
        ids.append(item["id"])

    status, first_page, latency = request(
        "GET", "/me/measurements?limit=1", user=user_a
    )
    cursor = first_page.get("next_cursor")
    status_2, second_page, latency_2 = request(
        "GET",
        "/me/measurements?limit=1&cursor=" + urllib.parse.quote(cursor or ""),
        user=user_a,
    )
    check(
        "measurement_cursor_paginates_without_overlap",
        status == 200
        and status_2 == 200
        and bool(cursor)
        and first_page.get("items", [])[0]["id"] == ids[2]
        and second_page.get("items", [])[0]["id"] == ids[1],
        {"first_status": status, "second_status": status_2},
        round(latency + latency_2, 2),
    )
    status, patched, latency = request(
        "PATCH",
        f"/me/measurements/{ids[0]}",
        user=user_a,
        body={"weight_kg": 89},
    )
    check(
        "owner_can_patch_and_bmi_is_recomputed",
        status == 200 and patched.get("weight_kg") == 89.0 and patched.get("bmi") == 30.8,
        status,
        latency,
    )

    status, _, latency = request("GET", f"/me/measurements/{ids[1]}", user=user_b)
    check("owner_b_cannot_get_a", status == 404, status, latency)
    status, _, latency = request(
        "PATCH",
        f"/me/measurements/{ids[1]}",
        user=user_b,
        body={"weight_kg": 50},
    )
    check("owner_b_cannot_patch_a", status == 404, status, latency)
    status, _, latency = request(
        "DELETE", f"/me/measurements/{ids[1]}", user=user_b
    )
    check("owner_b_cannot_delete_a", status == 404, status, latency)

    status, progress, latency = request("GET", "/me/progress/timeline", user=user_a)
    timeline_ids = [item["id"] for item in progress.get("timeline", [])]
    check(
        "progress_excludes_unconfirmed",
        status == 200
        and ids[0] not in timeline_ids
        and ids[1] in timeline_ids
        and ids[2] in timeline_ids,
        {"status": status, "timeline_count": len(timeline_ids)},
        latency,
    )
    check(
        "progress_delta_is_correct",
        progress.get("delta", {}).get("weight_kg") == -1.0,
        progress.get("delta", {}).get("weight_kg"),
        latency,
    )
    status, summary, latency = request("GET", "/me/progress/summary", user=user_a)
    check(
        "progress_summary_matches_timeline_without_raw_series",
        status == 200
        and summary.get("delta", {}).get("weight_kg") == -1.0
        and "timeline" not in summary,
        status,
        latency,
    )
    status, _, latency = request(
        "DELETE", f"/me/measurements/{ids[0]}?reason=synthetic-test", user=user_a
    )
    check("owner_soft_deletes_measurement", status == 204, status, latency)
    status, _, latency = request("GET", f"/me/measurements/{ids[0]}", user=user_a)
    check("soft_deleted_measurement_is_hidden", status == 404, status, latency)

    extreme_date = (now.date() + timedelta(days=7)).isoformat()
    status, _, latency = request(
        "PUT",
        "/me/goals/current",
        user=user_a,
        body={
            "goal_type": "fat_loss",
            "target_weight_kg": 40,
            "target_date": extreme_date,
            "training_days_per_week": 3,
        },
    )
    check("extreme_goal_rejected", status == 409, status, latency)

    for goal_type in ("maintenance", "fitness"):
        status, goal, latency = request(
            "PUT",
            "/me/goals/current",
            user=user_a,
            body={
                "goal_type": goal_type,
                "training_days_per_week": 3,
                "weekly_activity_level": "moderate",
            },
        )
        check(f"goal_version_{goal_type}", status == 200, status, latency)
    status, history, latency = request("GET", "/me/goals/history", user=user_a)
    versions = [item["version"] for item in history.get("items", [])]
    check(
        "goal_history_preserved",
        status == 200 and versions[:2] == [2, 1],
        versions,
        latency,
    )
    status, current_goal, latency = request("GET", "/me/goals/current", user=user_a)
    check(
        "current_goal_returns_latest_active_version",
        status == 200 and (current_goal.get("goal") or {}).get("version") == 2,
        status,
        latency,
    )

    status, plan, latency = request(
        "POST",
        "/me/plans",
        user=user_a,
        body={
            "status": "active",
            "measurement_ids": [ids[2]],
            "evidence_ids": ["nutrition-guideline-1"],
            "citations": [{"document_id": "nutrition-guideline-1", "title": "Synthetic citation"}],
            "content": {"summary": "Synthetic acceptance-test plan"},
        },
    )
    check(
        "plan_snapshot_and_provenance",
        status == 201
        and plan.get("goal_version") == 2
        and plan.get("measurement_ids") == [ids[2]]
        and bool(plan.get("input_snapshot"))
        and plan.get("safety_result", {}).get("risk_level") == "low",
        status,
        latency,
    )
    status, current_plan, latency = request("GET", "/me/plans/current", user=user_a)
    check(
        "current_plan_returns_active_plan",
        status == 200 and (current_plan.get("plan") or {}).get("id") == plan.get("id"),
        status,
        latency,
    )
    status, plan_history, latency = request("GET", "/me/plans", user=user_a)
    check(
        "plan_list_preserves_version",
        status == 200
        and plan_history.get("items", [])[0].get("id") == plan.get("id")
        and plan_history.get("items", [])[0].get("version") == 1,
        status,
        latency,
    )
    status, _, latency = request(
        "POST",
        "/me/plans",
        user=user_a,
        body={
            "status": "active",
            "measurement_ids": [ids[2]],
            "content": {"summary": "Must be rejected without evidence"},
        },
    )
    check("active_plan_without_evidence_rejected", status == 409, status, latency)
    status, _, latency = request(
        "POST",
        f"/me/plans/{plan['id']}/archive",
        user=user_b,
        body={"reason": "cross-owner-attempt"},
    )
    check("owner_b_cannot_archive_a_plan", status == 404, status, latency)
    status, archived_plan, latency = request(
        "POST",
        f"/me/plans/{plan['id']}/archive",
        user=user_a,
        body={"reason": "acceptance-complete"},
    )
    check(
        "owner_can_archive_plan",
        status == 200 and archived_plan.get("status") == "archived",
        status,
        latency,
    )
    status, current_plan, latency = request("GET", "/me/plans/current", user=user_a)
    check(
        "archived_plan_is_not_current",
        status == 200 and current_plan.get("plan") is None,
        status,
        latency,
    )

    status, _, latency = request(
        "PATCH",
        "/me/profile",
        user=user_b,
        body={
            "consent_flags": {
                "health_data_processing": False,
                "personalization": False,
            }
        },
    )
    check("consent_can_be_revoked", status == 200, status, latency)
    status, _, latency = request(
        "POST",
        "/me/measurements",
        user=user_b,
        body={
            "measured_at": (now - timedelta(days=1)).isoformat(),
            "weight_kg": 70,
            "confirmed_by_user": True,
        },
    )
    check("measurement_write_without_consent_rejected", status == 409, status, latency)

    status, _, latency = request(
        "PATCH",
        "/me/profile",
        user=user_a,
        body={"medical_conditions": ["tăng huyết áp"]},
    )
    check("profile_medical_constraint_patch", status == 200, status, latency)
    status, debug_context, latency = request(
        "GET", "/me/personalization-context", user=user_a
    )
    conditions = (debug_context.get("profile") or {}).get("medical_conditions")
    check(
        "debug_context_redacts_conditions",
        status == 200
        and isinstance(conditions, dict)
        and conditions.get("count") == 1
        and "tăng huyết áp" not in json.dumps(debug_context, ensure_ascii=False),
        status,
        latency,
    )

    status, checkin, latency = request(
        "POST",
        "/me/check-ins",
        user=user_a,
        body={
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "adherence": 80,
            "symptoms": ["đau ngực", "khó thở"],
        },
    )
    check(
        "urgent_checkin_routes_to_safety",
        status == 201 and checkin.get("safety_result", {}).get("risk_level") == "urgent",
        status,
        latency,
    )
    status, checkins, latency = request("GET", "/me/check-ins", user=user_a)
    check(
        "checkin_list_returns_owner_record",
        status == 200
        and checkins.get("items", [])[0].get("id") == checkin.get("id")
        and checkins.get("items", [])[0].get("safety_result", {}).get("risk_level") == "urgent",
        status,
        latency,
    )

    status, _, latency = request(
        "POST",
        "/agent/answer",
        user=user_a,
        body={"question": "Tôi đau ngực và khó thở khi tập", "user_id": user_b},
    )
    check("agent_answer_cannot_borrow_body_user_id", status == 403, status, latency)

    status, _, latency = request(
        "POST",
        "/chat/complete",
        user=user_a,
        body={
            "user_message": "Tôi đau ngực và khó thở khi tập",
            "user_id": user_b,
            "sync_request": True,
        },
    )
    check("chat_complete_cannot_borrow_body_user_id", status == 403, status, latency)

    status, chat_result, latency = request(
        "POST",
        "/chat/complete",
        user=user_a,
        body={
            "user_message": "Tôi đau ngực và khó thở khi tập",
            "sync_request": True,
        },
    )
    chat_response = chat_result.get("response", {}) if isinstance(chat_result, dict) else {}
    check(
        "chat_complete_uses_authenticated_personalization",
        status == 200
        and chat_response.get("fast_path") == "urgent_safety"
        and chat_response.get("personalization_used", {}).get("available") is True
        and "personalization_context" not in chat_response,
        status,
        latency,
    )

    status, answer, latency = request(
        "POST",
        "/agent/answer",
        user=user_a,
        body={"question": "Tôi đau ngực và khó thở khi tập"},
    )
    check(
        "urgent_agent_fast_path_with_profile",
        status == 200
        and answer.get("fast_path") == "urgent_safety"
        and answer.get("safety_result", {}).get("risk_level") == "urgent"
        and answer.get("personalization_used", {}).get("available") is True
        and "personalization_context" not in answer,
        {"status": status, "fast_path": answer.get("fast_path")},
        latency,
    )

    passed = sum(1 for item in checks if item["passed"])
    report = {
        "status": passed == len(checks),
        "passed": passed,
        "total": len(checks),
        "synthetic_user_prefix": f"p1-eval-*-{suffix}",
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] else 1


if __name__ == "__main__":
    sys.exit(main())
