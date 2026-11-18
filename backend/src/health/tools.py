"""
Health/InBody tools for the chatbot agent.

This module replaces the old legal-domain prototype tools with practical
health, nutrition, exercise, and safety helpers for the InBody RAG chatbot.
"""

import logging
import re
from typing import Dict, List, Optional

from health.validation import normalize_match_text

logger = logging.getLogger(__name__)


def calculate_bmi(weight_kg: float, height_cm: float) -> Dict:
    """
    Tinh BMI va phan loai tinh trang can nang theo nguong WHO/Asia tham khao.

    Args:
        weight_kg: Can nang tinh bang kg.
        height_cm: Chieu cao tinh bang cm.

    Returns:
        Dict gom BMI, phan loai va khuyen nghi tong quan.
    """
    try:
        if weight_kg <= 0 or height_cm <= 0:
            return {"error": "Can nang va chieu cao phai lon hon 0"}

        height_m = height_cm / 100
        bmi = weight_kg / (height_m**2)

        if bmi < 18.5:
            category = "underweight"
            status = "Thieu can"
            recommendation = "Nen uu tien tang nang lanh manh, tang protein va tap khang luc."
        elif bmi < 23:
            category = "normal"
            status = "Binh thuong"
            recommendation = "Nen duy tri van dong, dinh duong can bang va theo doi chi so co/mo."
        elif bmi < 25:
            category = "overweight_risk"
            status = "Tien thua can theo nguong chau A"
            recommendation = "Nen kiem soat nang luong va tang van dong de giam mo tu tu."
        elif bmi < 30:
            category = "overweight"
            status = "Thua can"
            recommendation = "Nen uu tien giam mo, tap khang luc ket hop cardio vua suc."
        else:
            category = "obesity"
            status = "Beo phi"
            recommendation = "Nen tham khao chuyen gia y te/dinh duong truoc khi thay doi manh che do tap an."

        result = {
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "bmi": round(bmi, 2),
            "category": category,
            "status": status,
            "recommendation": recommendation,
            "note": "BMI chi la chi so sang loc, can doc kem PBF, SMM va mo noi tang.",
        }
        logger.info("[TOOL] BMI calculated")
        return result
    except Exception as e:
        logger.error("Error calculating BMI: %s", e)
        return {"error": str(e)}


def evaluate_body_fat_percentage(pbf_percent: float, sex: Optional[str] = None) -> Dict:
    """
    Danh gia phan tram mo co the (PBF) theo gioi tinh neu co.

    Args:
        pbf_percent: Phan tram mo co the.
        sex: male, female hoac None.

    Returns:
        Dict gom phan loai PBF va goi y huong cai thien.
    """
    try:
        if pbf_percent < 0:
            return {"error": "PBF khong duoc am"}

        sex_key = (sex or "unknown").lower()

        if sex_key == "male":
            thresholds = [(10, "low"), (20, "normal"), (25, "high"), (100, "very_high")]
        elif sex_key == "female":
            thresholds = [(18, "low"), (28, "normal"), (33, "high"), (100, "very_high")]
        else:
            thresholds = [(15, "low"), (25, "normal"), (32, "high"), (100, "very_high")]

        category = "very_high"
        for upper, name in thresholds:
            if pbf_percent < upper:
                category = name
                break

        messages = {
            "low": "Ty le mo thap; can dam bao nang luong, hormone va suc khoe tong quat.",
            "normal": "Ty le mo trong vung tham khao; nen duy tri tap luyen va an uong can bang.",
            "high": "Ty le mo cao; nen uu tien giam mo bang thieu hut calo nhe va tap khang luc.",
            "very_high": "Ty le mo rat cao; nen giam mo tu tu va can nhac tu van chuyen gia neu co benh nen.",
        }

        result = {
            "pbf_percent": pbf_percent,
            "sex": sex_key,
            "category": category,
            "status": messages[category],
            "note": "Nguong PBF co the thay doi theo tuoi, gioi tinh va thiet bi do.",
        }
        logger.info("[TOOL] PBF evaluated")
        return result
    except Exception as e:
        logger.error("Error evaluating PBF: %s", e)
        return {"error": str(e)}


def evaluate_visceral_fat(visceral_fat_level: float) -> Dict:
    """
    Danh gia muc mo noi tang tu bao cao InBody.

    Args:
        visceral_fat_level: Muc mo noi tang, thuong la thang diem level.

    Returns:
        Dict gom muc rui ro va khuyen nghi hanh dong.
    """
    try:
        if visceral_fat_level < 0:
            return {"error": "Muc mo noi tang khong duoc am"}

        if visceral_fat_level <= 9:
            risk = "normal"
            status = "Trong nguong tham khao"
            recommendation = "Duy tri dinh duong va van dong hien tai, tiep tuc theo doi dinh ky."
        elif visceral_fat_level <= 14:
            risk = "elevated"
            status = "Hoi cao"
            recommendation = "Nen uu tien giam mo bung, tang cardio vua suc va tap khang luc."
        else:
            risk = "high"
            status = "Cao"
            recommendation = "Nen giam mo co ke hoach va tham khao bac si neu co benh nen tim mach/chuyen hoa."

        result = {
            "visceral_fat_level": visceral_fat_level,
            "risk": risk,
            "status": status,
            "recommendation": recommendation,
            "safety_note": "Khong dung chi so nay de chan doan benh; can danh gia cung bac si khi co trieu chung.",
        }
        logger.info("[TOOL] Visceral fat evaluated")
        return result
    except Exception as e:
        logger.error("Error evaluating visceral fat: %s", e)
        return {"error": str(e)}


def suggest_nutrition_goal(
    goal: str,
    weight_kg: float,
    activity_level: str = "moderate",
) -> Dict:
    """
    Goi y muc protein va huong nang luong theo muc tieu suc khoe.

    Args:
        goal: fat_loss, muscle_gain hoac maintenance.
        weight_kg: Can nang hien tai.
        activity_level: low, moderate hoac high.

    Returns:
        Dict gom goi y dinh duong an toan o muc tham khao.
    """
    try:
        if weight_kg <= 0:
            return {"error": "Can nang phai lon hon 0"}

        normalized_goal = goal.lower()
        protein_ranges = {
            "fat_loss": (1.6, 2.2),
            "muscle_gain": (1.6, 2.0),
            "maintenance": (1.2, 1.8),
        }
        calorie_notes = {
            "fat_loss": "Giam nhe 300-500 kcal/ngay, tranh cat giam qua nhanh.",
            "muscle_gain": "Tang nhe 150-300 kcal/ngay neu tap khang luc deu.",
            "maintenance": "Duy tri nang luong gan muc tieu hao hang ngay.",
        }

        if normalized_goal not in protein_ranges:
            return {
                "error": f"Muc tieu '{goal}' khong hop le",
                "valid_goals": list(protein_ranges.keys()),
            }

        low, high = protein_ranges[normalized_goal]
        result = {
            "goal": normalized_goal,
            "activity_level": activity_level,
            "protein_g_per_day": {
                "min": round(weight_kg * low),
                "max": round(weight_kg * high),
            },
            "calorie_strategy": calorie_notes[normalized_goal],
            "food_priority": [
                "uu tien thuc pham it che bien",
                "du protein moi bua",
                "them rau va chat xo",
                "uong du nuoc",
            ],
            "safety_note": "Khong ap dung an kieng cuc doan; nguoi co benh nen nen hoi chuyen gia y te.",
        }
        logger.info("[TOOL] Nutrition goal suggested")
        return result
    except Exception as e:
        logger.error("Error suggesting nutrition goal: %s", e)
        return {"error": str(e)}


def suggest_training_plan(
    goal: str,
    fitness_level: str = "beginner",
    days_per_week: int = 3,
) -> Dict:
    """
    Goi y lich tap co ban theo muc tieu va so ngay/tuần.

    Args:
        goal: fat_loss, muscle_gain hoac maintenance.
        fitness_level: beginner, intermediate hoac advanced.
        days_per_week: So buoi tap moi tuan.

    Returns:
        Dict gom lich tap goi y va luu y an toan.
    """
    try:
        if days_per_week < 1 or days_per_week > 7:
            return {"error": "days_per_week phai nam trong khoang 1-7"}

        normalized_goal = goal.lower()
        normalized_level = fitness_level.lower()

        if normalized_goal == "fat_loss":
            focus = "khang luc toan than ket hop cardio vua suc"
            sessions = ["Full-body strength", "Cardio zone 2", "Full-body strength"]
        elif normalized_goal == "muscle_gain":
            focus = "tap khang luc tien bo dan, uu tien ky thuat va phuc hoi"
            sessions = ["Upper body", "Lower body", "Full-body hypertrophy"]
        else:
            focus = "duy tri suc khoe, linh hoat giua suc manh va tim mach"
            sessions = ["Full-body strength", "Mobility/Cardio", "Full-body strength"]

        while len(sessions) < days_per_week:
            sessions.append("Light cardio or mobility")

        result = {
            "goal": normalized_goal,
            "fitness_level": normalized_level,
            "days_per_week": days_per_week,
            "focus": focus,
            "weekly_plan": sessions[:days_per_week],
            "progression": "Tang khoi luong/so rep tu tu moi 1-2 tuan neu khong dau bat thuong.",
            "safety_note": "Dung tap neu dau nguc, kho tho, chong mat hoac dau khop bat thuong.",
        }
        logger.info("[TOOL] Training plan suggested")
        return result
    except Exception as e:
        logger.error("Error suggesting training plan: %s", e)
        return {"error": str(e)}


_URGENT_PATTERNS = [
    # Chest / Heart
    r"\b(dau|tuc|that|nhoi)\s+nguc\b",
    r"\b(ep|nhoi|dau)\s+tim\b",
    # Breathing
    r"\b(kho|ngat|ngung|tac)\s+tho\b",
    r"\bkhong\s+tho\s+duoc\b",
    # Consciousness / Neuro
    r"\b(hon\s+me|bat\s+tinh|mat\s+y\s+thuc)\b",
    r"\b(co\s+giat|dong\s+kinh)\b",
    r"\b(dot\s+quy|tai\s+bien)\b",
    r"\b(lo\s+mo|choang\s+vang)\b",
    r"\bchoang\b",
    # Hemorrhage
    r"\b(non|ho)\s+ra\s+mau\b",
    r"\bchay\s+mau\s+(o\s+at|nhieu|du\s+doi)\b",
    r"\bchay\s+mau\b",
]

# Refined NGAT pattern: exclude 'ngat quang', 'ngat mui', 'ngat ket noi'
_NGAT_URGENT_PATTERN = r"\b(ngat\s+xiu|ngat\s+di|ngat\s+tai\s+cho)\b|\b(?:bi\s+)?ngat\b(?!\s+(?:quang|mui|ket\s+noi))\b"

# Medical Caution patterns
_CAUTION_PATTERNS = [
    # Chronic conditions
    r"\b(tieu\s+duong|duong\s+huyet|dai\s+thao\s+duong)\b",
    r"\b(huyet\s+ap|cao\s+huyet\s+ap|ha\s+huyet\s+ap|tut\s+huyet\s+ap)\b",
    r"\b(tim\s+mach|suy\s+tim|suy\s+than|suy\s+gan|benh\s+than|benh\s+gan|benh\s+phoi)\b",
    r"\b(dau\s+khop|thoai\s+hoa\s+khop|thoat\s+vi|viem\s+khop|dau\s+lung|dau\s+cot\s+song)\b",
    r"\b(chan\s+thuong|rach\s+co|dut\s+day\s+chang)\b",
    # Medical consultation / prescription
    r"\b(chan\s+doan|ke\s+don|phac\s+do|toa\s+thuoc|don\s+thuoc)\b",
    r"\b(bac\s+si\s+kham|kham\s+benh)\b",
    # Medicine (unaccented: exclude 'thuoc nhom', 'phu thuoc', 'thuoc ve')
    r"(?<!phu\s)\bthuoc\b(?!\s+(?:nhom|ve|loai|dien))\b",
    # Dosage (unaccented: require dosage terms, do not match alone 'lieu' or 'tai lieu')
    r"\b(lieu\s+luong|lieu\s+dung|qua\s+lieu|tang\s+lieu|giam\s+lieu|dung\s+lieu)\b",
    # Disease (unaccented: exclude 'benh vuc')
    r"\b(benh\s+nen|benh\s+ly|mac\s+benh|bi\s+benh)\b",
    r"\bbenh\b(?!\s+vuc)\b",
]


def check_medical_safety(question: str, conditions: Optional[List[str]] = None) -> Dict:
    """
    Kiem tra cau hoi co dau hieu can canh bao y te hay khong.

    Args:
        question: Cau hoi cua nguoi dung.
        conditions: Danh sach benh nen/hạn che neu co.

    Returns:
        Dict gom muc do rui ro va huong phan hoi an toan.
    """
    try:
        raw_lower = (question or "").lower()
        norm = normalize_match_text(question)
        conditions = conditions or []

        # 1. Deterministic urgent life-threatening checks
        is_urgent = False
        for pat in _URGENT_PATTERNS:
            if re.search(pat, norm):
                is_urgent = True
                break
        if not is_urgent and re.search(_NGAT_URGENT_PATTERN, norm):
            is_urgent = True

        if is_urgent:
            risk_level = "urgent"
            action = "Khuyến nghị người dùng liên hệ cấp cứu hoặc cơ sở y tế ngay."
        else:
            # 2. Medical caution checks (chronic diseases, medications, injuries)
            is_caution = bool(conditions)
            if not is_caution:
                # Check accented raw text first for precise terms
                if re.search(r"\bthuốc\b", raw_lower) and not re.search(r"\bthuộc\b", raw_lower):
                    is_caution = True
                elif re.search(r"\bbệnh\b", raw_lower) and not re.search(r"\bbênh\b", raw_lower):
                    is_caution = True
                elif re.search(r"\bliều\b", raw_lower) and not re.search(
                    r"\b(tài\s+liệu|liệu\s+(?:rằng|có|chừng))\b", raw_lower
                ):
                    is_caution = True
                else:
                    for pat in _CAUTION_PATTERNS:
                        if re.search(pat, norm):
                            is_caution = True
                            break

            if is_caution:
                risk_level = "medical_caution"
                action = "Trả lời ở mức tham khảo và khuyến nghị hỏi bác sĩ/chuyên gia khi cần."
            else:
                risk_level = "low"
                action = "Có thể trả lời về sức khỏe, dinh dưỡng, tập luyện ở mức tham khảo."

        result = {
            "risk_level": risk_level,
            "conditions": conditions,
            "recommended_action": action,
            "disclaimer": "Thông tin chỉ mang tính tham khảo, không thay thế chẩn đoán hoặc điều trị y khoa.",
        }
        logger.info("[TOOL] Medical safety checked: risk_level=%s", risk_level)
        return result
    except Exception as e:
        logger.error("Error checking medical safety: %s", e)
        return {"error": str(e)}


__all__ = [
    "calculate_bmi",
    "evaluate_body_fat_percentage",
    "evaluate_visceral_fat",
    "suggest_nutrition_goal",
    "suggest_training_plan",
    "check_medical_safety",
]
