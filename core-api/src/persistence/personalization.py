"""Personalization helpers for Health/InBody users and measurements."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from persistence.database import session_scope
from persistence.models import InBodyMeasurement, User

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
