"""Bounded, dated personal events; never shared medical evidence."""
import json
import re
import unicodedata
from datetime import timedelta

from harness.guards import has_untrusted_instruction


def event_context(db, user, active_goal) -> list[dict]:
    from persistence.models import PersonalizedPlan, CheckIn
    from memory.store import now
    result = []
    plans = db.query(PersonalizedPlan).filter(
        PersonalizedPlan.user_id == user.id, PersonalizedPlan.status.in_(["active", "archived"]),
        PersonalizedPlan.created_at >= now() - timedelta(days=90),
    ).order_by(PersonalizedPlan.created_at.desc()).limit(3).all()
    for plan in plans:
        content = json.dumps(plan.content, ensure_ascii=False)
        if has_untrusted_instruction(content):
            continue
        current = plan.status == "active" and (active_goal is not None and plan.goal_version == active_goal.version)
        result.append({"type": "plan", "source_id": str(plan.id), "occurred_at": plan.created_at.isoformat(),
                       "status": plan.status, "valid_for_current_goal": current,
                       "summary": content[:1000], "goal_version": plan.goal_version})
    rows = db.query(CheckIn).filter(CheckIn.user_id == user.id, CheckIn.checked_at >= now() - timedelta(days=30)).order_by(
        CheckIn.checked_at.desc()).limit(3).all()
    for item in rows:
        result.append({"type": "check_in", "source_id": str(item.id), "occurred_at": item.checked_at.isoformat(),
                       "status": "user_reported", "adherence": item.adherence, "energy_level": item.energy_level,
                       "sleep_quality": item.sleep_quality, "soreness": item.soreness,
                       "risk_at_event": (item.safety_result or {}).get("risk_level")})
    return result


def answer_memory_question(question: str, context: dict):
    text = "".join(c for c in unicodedata.normalize("NFD", question.lower()) if not unicodedata.combining(c)).replace("đ", "d")
    is_fact = any(x in text for x in ("nho gi ve toi", "ghi nho cua toi", "so thich cua toi"))
    is_event = bool(re.search(r"\b(?:ke hoach lan truoc|ke hoach cu|check-in gan nhat|check in gan nhat)\b", text))
    if not (is_fact or is_event):
        return None
    if not context.get("available"):
        return "Mình chưa có dữ liệu đã được bạn đồng ý và xác nhận để nhắc lại."
    lines = []
    if is_fact:
        for fact in context.get("confirmed_memory") or []:
            lines.append(f"• {fact['text']} (bạn xác nhận {fact['confirmed_at'][:10]}; hết hạn {fact['expires_at'][:10]}).")
    if is_event:
        for event in context.get("memory_events") or []:
            date = event["occurred_at"][:10]
            if event["type"] == "plan":
                label = "đang áp dụng cho mục tiêu hiện tại" if event["valid_for_current_goal"] else "lịch sử, không tự áp dụng lại"
                lines.append(f"• Kế hoạch {date} ({label}): {event['summary']}")
            else:
                lines.append(f"• Check-in {date}: mức tuân thủ {event['adherence']}, năng lượng {event['energy_level']}, giấc ngủ {event['sleep_quality']}. Đây là thông tin bạn tự báo cáo.")
    return "\n".join(lines) if lines else "Mình chưa có ghi nhớ đã xác nhận hoặc sự kiện còn trong thời hạn tra cứu cho yêu cầu này."
