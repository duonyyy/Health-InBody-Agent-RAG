"""Public API schemas for Health/InBody Agent RAG backend."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from core.config import DEFAULT_VECTOR_SIZE


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1500)


class CompleteRequest(BaseModel):
    bot_id: str = Field(default="health-inbody-agent", max_length=128)
    user_id: Optional[str] = Field(default=None, min_length=1)
    user_message: str = Field(min_length=1, max_length=4000)
    # Deprecated compatibility input; never used as server history.
    history: Optional[List[HistoryTurn]] = Field(default=None, max_length=10)
    conversation_id: Optional[UUID] = None
    sync_request: Optional[bool] = True


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: Optional[List[HistoryTurn]] = Field(default=None, max_length=10)
    user_id: Optional[str] = None
    conversation_id: Optional[UUID] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class CollectionCreateRequest(BaseModel):
    collection_name: str = Field(min_length=3, max_length=255)
    vector_size: int = Field(default=DEFAULT_VECTOR_SIZE, ge=1)


class DocumentCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    question: Optional[str] = Field(default="", max_length=2000)
    content: str = Field(min_length=1, max_length=100000)
    collection_name: str = Field(min_length=3, max_length=255)
    corpus_version: Optional[str] = Field(default=None, max_length=128)
    metadata: Optional[Dict[str, Any]] = None


class DocumentsIndexRequest(BaseModel):
    documents: List[Dict[str, Any]] = Field(min_length=1, max_length=100)
    collection_name: str = Field(min_length=3, max_length=255)
    corpus_version: Optional[str] = Field(default=None, max_length=128)


class SummaryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    report_mode: bool = False


class BmiRequest(BaseModel):
    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(ge=30, le=300)


class PbfRequest(BaseModel):
    pbf_percent: float = Field(ge=0, le=100)
    sex: Optional[str] = None


class VisceralFatRequest(BaseModel):
    visceral_fat_level: float = Field(ge=0, le=100)


class NutritionRequest(BaseModel):
    goal: str = "fat_loss"
    weight_kg: float = Field(gt=0, le=500)
    activity_level: str = "moderate"


class TrainingRequest(BaseModel):
    goal: str = "fat_loss"
    fitness_level: str = "beginner"
    days_per_week: int = Field(default=3, ge=1, le=7)


class SafetyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conditions: Optional[List[str]] = None


class UserProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    sex: Optional[str] = None
    birth_year: Optional[int] = None
    height_cm: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    medical_conditions: Optional[str] = None


class InBodyMeasurementRequest(BaseModel):
    measurement_date: date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None
    smm_kg: Optional[float] = None
    bfm_kg: Optional[float] = None
    pbf_percent: Optional[float] = None
    visceral_fat_level: Optional[float] = None
    body_water_l: Optional[float] = None
    recommendation_goal: Optional[str] = None
    source_file: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


__all__ = [
    "HistoryTurn",
    "AgentRequest",
    "BmiRequest",
    "CollectionCreateRequest",
    "CompleteRequest",
    "DocumentCreateRequest",
    "DocumentsIndexRequest",
    "InBodyMeasurementRequest",
    "NutritionRequest",
    "PbfRequest",
    "SafetyRequest",
    "SearchRequest",
    "SummaryRequest",
    "TrainingRequest",
    "UserProfileRequest",
    "VisceralFatRequest",
]
