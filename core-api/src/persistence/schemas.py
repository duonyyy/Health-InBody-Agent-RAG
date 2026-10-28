"""Validated P1 request schemas for owner-scoped personalization data."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AgeRange(str, Enum):
    UNDER_18 = "under_18"
    AGE_18_24 = "18_24"
    AGE_25_34 = "25_34"
    AGE_35_44 = "35_44"
    AGE_45_54 = "45_54"
    AGE_55_64 = "55_64"
    AGE_65_PLUS = "65_plus"


class SexAtBirth(str, Enum):
    MALE = "male"
    FEMALE = "female"
    INTERSEX = "intersex"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class ActivityLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class GoalType(str, Enum):
    FAT_LOSS = "fat_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    FITNESS = "fitness"
    OTHER = "other"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class SourceType(str, Enum):
    MANUAL = "manual"
    MANUAL_CONFIRMED = "manual_confirmed"
    OCR_UNCONFIRMED = "ocr_unconfirmed"
    OCR_CONFIRMED = "ocr_confirmed"
    DEVICE_IMPORTED = "device_imported"
    LEGACY_UNCONFIRMED = "legacy_unconfirmed"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"


class ConsentFlags(BaseModel):
    health_data_processing: bool = False
    personalization: bool = False


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _clean_text_list(values: Optional[List[str]], max_items: int = 20) -> Optional[List[str]]:
    if values is None:
        return None
    cleaned: List[str] = []
    for value in values:
        item = _clean_optional_text(str(value))
        if item and item not in cleaned:
            if len(item) > 160:
                raise ValueError("Each list item must contain at most 160 characters")
            cleaned.append(item)
    if len(cleaned) > max_items:
        raise ValueError(f"At most {max_items} items are allowed")
    return cleaned


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    age_range: Optional[AgeRange] = None
    birth_date: Optional[date] = None
    sex_at_birth: Optional[SexAtBirth] = None
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    activity_level: Optional[ActivityLevel] = None
    goal: Optional[GoalType] = None
    dietary_preferences: Optional[List[str]] = None
    exercise_constraints: Optional[List[str]] = None
    medical_conditions: Optional[List[str]] = None
    consent_flags: Optional[ConsentFlags] = None

    _clean_name = field_validator("display_name")(_clean_optional_text)

    @field_validator("dietary_preferences", "exercise_constraints", "medical_conditions")
    def clean_lists(cls, value):
        return _clean_text_list(value)

    @model_validator(mode="after")
    def validate_age_policy(self):
        if self.age_range is not None and self.birth_date is not None:
            raise ValueError("Provide age_range or birth_date, not both")
        birth_date = self.birth_date
        if birth_date is not None:
            today = date.today()
            if birth_date > today:
                raise ValueError("birth_date cannot be in the future")
            if birth_date.year < today.year - 120:
                raise ValueError("birth_date is outside the supported range")
        return self


class GoalCurrentRequest(BaseModel):
    goal_type: GoalType
    target_weight_kg: Optional[float] = Field(default=None, ge=30, le=300)
    target_date: Optional[date] = None
    training_days_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    weekly_activity_level: Optional[ActivityLevel] = None
    constraints: List[str] = Field(default_factory=list)
    status: GoalStatus = GoalStatus.ACTIVE

    @field_validator("constraints")
    def clean_constraints(cls, value):
        return _clean_text_list(value) or []

    @field_validator("target_date")
    def target_date_must_be_future(cls, value):
        if value is not None and value <= date.today():
            raise ValueError("target_date must be in the future")
        return value


class MeasurementBase(BaseModel):
    measured_at: Optional[datetime] = None
    height_cm: Optional[float] = Field(default=None, ge=50, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=20, le=400)
    bmi: Optional[float] = Field(default=None, ge=5, le=80)
    smm_kg: Optional[float] = Field(default=None, ge=0, le=200)
    bfm_kg: Optional[float] = Field(default=None, ge=0, le=250)
    pbf_percent: Optional[float] = Field(default=None, ge=0, le=80)
    visceral_fat_level: Optional[float] = Field(default=None, ge=0, le=50)
    body_water_l: Optional[float] = Field(default=None, ge=0, le=200)
    source_type: Optional[SourceType] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    confirmed_by_user: Optional[bool] = None

    @field_validator("measured_at")
    def measured_at_requires_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("measured_at must include a timezone offset")
        if value is not None and value > datetime.now(value.tzinfo):
            raise ValueError("measured_at cannot be in the future")
        return value


class MeasurementCreate(MeasurementBase):
    measured_at: datetime
    source_type: SourceType = SourceType.MANUAL
    confirmed_by_user: bool = False

    @model_validator(mode="after")
    def require_measurement_value(self):
        metric_fields = (
            "height_cm",
            "weight_kg",
            "bmi",
            "smm_kg",
            "bfm_kg",
            "pbf_percent",
            "visceral_fat_level",
            "body_water_l",
        )
        if not any(getattr(self, field) is not None for field in metric_fields):
            raise ValueError("At least one measurement metric is required")
        return self


class MeasurementPatch(MeasurementBase):
    pass


class PlanCreateRequest(BaseModel):
    status: PlanStatus = PlanStatus.DRAFT
    measurement_ids: List[str] = Field(default_factory=list, max_length=20)
    evidence_ids: List[str] = Field(default_factory=list, max_length=50)
    citations: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    content: Dict[str, Any] = Field(default_factory=dict)
    symptoms: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("measurement_ids", "evidence_ids", "symptoms")
    def clean_string_lists(cls, value):
        return _clean_text_list(value, max_items=50) or []


class PlanArchiveRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=240)

    _clean_reason = field_validator("reason")(_clean_optional_text)


class CheckInCreateRequest(BaseModel):
    checked_at: datetime
    adherence: Optional[int] = Field(default=None, ge=0, le=100)
    energy_level: Optional[int] = Field(default=None, ge=1, le=5)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    soreness: Optional[int] = Field(default=None, ge=1, le=5)
    symptoms: List[str] = Field(default_factory=list, max_length=20)
    note: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("checked_at")
    def checked_at_requires_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("checked_at must include a timezone offset")
        if value > datetime.now(value.tzinfo):
            raise ValueError("checked_at cannot be in the future")
        return value

    @field_validator("symptoms")
    def clean_symptoms(cls, value):
        return _clean_text_list(value) or []

    _clean_note = field_validator("note")(_clean_optional_text)


def model_to_dict(model: BaseModel, *, exclude_unset: bool = True) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset, mode="python")
    return model.dict(exclude_unset=exclude_unset)
