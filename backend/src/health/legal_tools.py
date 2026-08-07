"""
Backward-compatible imports for the old legal_tools module name.

New code should import these helpers from health_tools instead.
"""

from health.tools import (  # noqa: F401
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)

__all__ = [
    "calculate_bmi",
    "evaluate_body_fat_percentage",
    "evaluate_visceral_fat",
    "suggest_nutrition_goal",
    "suggest_training_plan",
    "check_medical_safety",
]
