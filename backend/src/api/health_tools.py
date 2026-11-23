"""Deterministic health calculation endpoints."""

from fastapi import APIRouter

from health.tools import (
    calculate_bmi,
    check_medical_safety,
    evaluate_body_fat_percentage,
    evaluate_visceral_fat,
    suggest_nutrition_goal,
    suggest_training_plan,
)
from api.schemas import (
    BmiRequest,
    NutritionRequest,
    PbfRequest,
    SafetyRequest,
    TrainingRequest,
    VisceralFatRequest,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/bmi")
async def bmi_endpoint(data: BmiRequest):
    return calculate_bmi(data.weight_kg, data.height_cm)


@router.post("/pbf")
async def pbf_endpoint(data: PbfRequest):
    return evaluate_body_fat_percentage(data.pbf_percent, data.sex)


@router.post("/visceral-fat")
async def visceral_fat_endpoint(data: VisceralFatRequest):
    return evaluate_visceral_fat(data.visceral_fat_level)


@router.post("/nutrition")
async def nutrition_endpoint(data: NutritionRequest):
    return suggest_nutrition_goal(data.goal, data.weight_kg, data.activity_level)


@router.post("/training")
async def training_endpoint(data: TrainingRequest):
    return suggest_training_plan(data.goal, data.fitness_level, data.days_per_week)


@router.post("/safety")
async def safety_endpoint(data: SafetyRequest):
    return check_medical_safety(data.question, data.conditions)
