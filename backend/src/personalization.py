"""Personalization helpers for Health/InBody users and measurements."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database import session_scope
from models import InBodyMeasurement, User

logger = logging.getLogger(__name__)


PROFILE_FIELDS = [
    "full_name",
    "email",
    "sex",
    "birth_year",
    "height_cm",
    "activity_level",
    "goal",
    "medical_conditions",
]

MEASUREMENT_FIELDS = [
    "measurement_date",
    "height_cm",
    "weight_kg",
    "bmi",
    "smm_kg",
    "bfm_kg",
    "pbf_percent",
    "visceral_fat_level",
    "body_water_l",
    "recommendation_goal",
    "source_file",
    "raw_payload",
]


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _drop_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _user_to_dict(user: User) -> Dict[str, Any]:
    return {
        "id": str(user.id),
        "external_id": user.external_id,
        **{
            field: _json_value(getattr(user, field))
            for field in PROFILE_FIELDS
        },
        "created_at": _json_value(user.created_at),
        "updated_at": _json_value(user.updated_at),
    }


def _measurement_to_dict(measurement: InBodyMeasurement) -> Dict[str, Any]:
    return {
        "id": str(measurement.id),
        "user_id": str(measurement.user_id),
        **{
            field: _json_value(getattr(measurement, field))
            for field in MEASUREMENT_FIELDS
        },
        "created_at": _json_value(measurement.created_at),
        "updated_at": _json_value(measurement.updated_at),
    }


def get_or_create_user(external_id: str) -> Dict[str, Any]:
    with session_scope() as db:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user is None:
            user = User(external_id=external_id)
            db.add(user)
            db.flush()
        return _user_to_dict(user)


def get_user_profile(external_id: str, auto_create: bool = True) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user is None:
            if not auto_create:
                return None
            user = User(external_id=external_id)
            db.add(user)
            db.flush()
        return _user_to_dict(user)


def upsert_user_profile(external_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    updates = {field: profile.get(field) for field in PROFILE_FIELDS if field in profile}
    with session_scope() as db:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user is None:
            user = User(external_id=external_id)
            db.add(user)
            db.flush()

        for field, value in updates.items():
            setattr(user, field, value)
        db.flush()
        return _user_to_dict(user)


def add_inbody_measurement(external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with session_scope() as db:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user is None:
            user = User(external_id=external_id)
            db.add(user)
            db.flush()

        measurement_data = {
            field: payload.get(field)
            for field in MEASUREMENT_FIELDS
            if field in payload
        }
        measurement = InBodyMeasurement(
            user_id=user.id,
            **measurement_data,
        )
        db.add(measurement)
        db.flush()
        return _measurement_to_dict(measurement)


def list_inbody_measurements(external_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    with session_scope() as db:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user is None:
            return []
        measurements = (
            db.query(InBodyMeasurement)
            .filter(InBodyMeasurement.user_id == user.id)
            .order_by(InBodyMeasurement.measurement_date.desc(), InBodyMeasurement.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_measurement_to_dict(item) for item in measurements]


def get_latest_inbody_measurement(external_id: str) -> Optional[Dict[str, Any]]:
    measurements = list_inbody_measurements(external_id, limit=1)
    return measurements[0] if measurements else None


def build_personalization_context(external_id: str) -> Dict[str, Any]:
    profile = get_user_profile(external_id, auto_create=True)
    latest_measurement = get_latest_inbody_measurement(external_id)

    profile_summary = _drop_none(
        {
            "sex": profile.get("sex") if profile else None,
            "birth_year": profile.get("birth_year") if profile else None,
            "height_cm": profile.get("height_cm") if profile else None,
            "activity_level": profile.get("activity_level") if profile else None,
            "goal": profile.get("goal") if profile else None,
            "medical_conditions": profile.get("medical_conditions") if profile else None,
        }
    )

    measurement_summary = _drop_none(
        {
            key: latest_measurement.get(key)
            for key in [
                "measurement_date",
                "height_cm",
                "weight_kg",
                "bmi",
                "smm_kg",
                "bfm_kg",
                "pbf_percent",
                "visceral_fat_level",
                "recommendation_goal",
            ]
        }
    ) if latest_measurement else {}

    return {
        "external_user_id": external_id,
        "has_profile": bool(profile_summary),
        "has_latest_measurement": bool(measurement_summary),
        "profile": profile_summary,
        "latest_measurement": measurement_summary,
    }


def safe_build_personalization_context(external_id: Optional[str]) -> Dict[str, Any]:
    if not external_id:
        return {
            "external_user_id": None,
            "has_profile": False,
            "has_latest_measurement": False,
            "profile": {},
            "latest_measurement": {},
            "error": "missing_user_id",
        }
    try:
        return build_personalization_context(str(external_id))
    except Exception as exc:
        logger.warning("Personalization context unavailable for user_id=%s: %s", external_id, exc)
        return {
            "external_user_id": str(external_id),
            "has_profile": False,
            "has_latest_measurement": False,
            "profile": {},
            "latest_measurement": {},
            "error": "personalization_unavailable",
        }
