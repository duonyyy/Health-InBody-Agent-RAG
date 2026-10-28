"""Health biometric and calculation schemas shared across services."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BmiRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=500, description="Cân nặng tính bằng kg")
    height_cm: float = Field(ge=30, le=300, description="Chiều cao tính bằng cm")


class BmiResult(BaseModel):
    bmi: float
    category: str
    risk_level: str
    target_weight_min_kg: float
    target_weight_max_kg: float


class PbfRequest(BaseModel):
    pbf_percent: float = Field(ge=0, le=100, description="Phần trăm mỡ cơ thể")
    sex: Optional[str] = Field(default=None, description="male | female")


class PbfResult(BaseModel):
    pbf_percent: float
    classification: str
    ideal_range_min: float
    ideal_range_max: float


class VisceralFatRequest(BaseModel):
    visceral_fat_level: float = Field(ge=0, le=100, description="Mức mỡ nội tạng (1-59)")


class VisceralFatResult(BaseModel):
    visceral_fat_level: float
    status: str
    risk: str
    recommendation: str


class NutritionRequest(BaseModel):
    goal: str = Field(default="fat_loss", description="fat_loss | muscle_gain | maintenance")
    weight_kg: float = Field(gt=0, le=500)
    activity_level: str = Field(default="moderate", description="sedentary | light | moderate | heavy")


class NutritionResult(BaseModel):
    calories_target: int
    protein_grams: int
    carb_grams: int
    fat_grams: int
    guidance: str


class TrainingRequest(BaseModel):
    goal: str = Field(default="fat_loss")
    fitness_level: str = Field(default="beginner")
    days_per_week: int = Field(default=3, ge=1, le=7)


class TrainingResult(BaseModel):
    schedule: List[Dict[str, Any]]
    guidance: str


class SafetyRequest(BaseModel):
    question: str = Field(min_length=1)
    conditions: Optional[List[str]] = None


class SafetyResult(BaseModel):
    is_safe: bool
    risk_level: str
    flags: List[str]
    disclaimer: str
    fast_path_action: Optional[str] = None
