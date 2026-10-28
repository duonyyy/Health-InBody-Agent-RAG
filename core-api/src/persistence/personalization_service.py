"""Owner-scoped P1 personalization services.

Every lookup starts from the authenticated external subject and applies the owner
filter in SQL. Callers never pass a database user id obtained from a request body.
"""

import base64
import json
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, or_

from health.tools import check_medical_safety
from persistence.database import session_scope
from persistence.models import (
    CheckIn,
    InBodyMeasurement,
    PersonalizationGoal,
    PersonalizedPlan,
    User,
)

logger = logging.getLogger(__name__)

PROFILE_FIELDS = (
    "display_name",
    "age_range",
    "birth_date",
    "sex_at_birth",
    "height_cm",
    "activity_level",
    "goal",
    "dietary_preferences",
    "exercise_constraints",
    "medical_conditions_data",
    "consent_flags",
)
HEALTH_PROFILE_FIELDS = frozenset(PROFILE_FIELDS) - {"display_name", "consent_flags"}
METRIC_FIELDS = (
    "height_cm",
    "weight_kg",
    "bmi",
    "smm_kg",
    "bfm_kg",
    "pbf_percent",
    "visceral_fat_level",
    "body_water_l",
)
DEFAULT_CONSENT = {
    "health_data_processing": False,
    "personalization": False,
    "external_memory": False,
    "external_memory_deletion_pending": False,
}


class PersonalizationError(Exception):
    status_code = 400
    public_message = "Invalid personalization request"


class PersonalizationNotFound(PersonalizationError):
    status_code = 404
    public_message = "Resource not found"


class PersonalizationConflict(PersonalizationError):
    status_code = 409

    def __init__(self, message: str):
        super().__init__(message)
        self.public_message = message


def _value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _json_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _value(value) for key, value in values.items()}


def _get_user(db, subject: str, *, create: bool, for_update: bool = False) -> Optional[User]:
    query = db.query(User).filter(User.external_id == subject, User.deleted_at.is_(None))
    if for_update:
        query = query.with_for_update()
    user = query.first()
    if user is None and create:
        user = User(external_id=subject, consent_flags=dict(DEFAULT_CONSENT))
        db.add(user)
        db.flush()
    return user


def _lock_user(db, user: User) -> None:
    """Serialize per-user version allocation for goals and plans."""
    db.query(User.id).filter(User.id == user.id).with_for_update().one()


def _consent(user: User) -> Dict[str, bool]:
    stored = user.consent_flags if isinstance(user.consent_flags, dict) else {}
    return {
        "health_data_processing": bool(stored.get("health_data_processing", False)),
        "personalization": bool(stored.get("personalization", False)),
        "external_memory": bool(stored.get("external_memory", False)),
        "external_memory_deletion_pending": bool(stored.get("external_memory_deletion_pending", False)),
    }


def _save_consent(user: User, flags: Dict[str, bool], **audit: Any) -> None:
    stored = user.consent_flags if isinstance(user.consent_flags, dict) else {}
    user.consent_flags = {**stored, **flags, **audit}


def grant_external_memory_consent(subject: str) -> Dict[str, bool]:
    """External cloud processing requires a distinct, explicit opt-in."""
    with session_scope() as db:
        user = _get_user(db, subject, create=False, for_update=True)
        if user is None:
            raise PersonalizationConflict("Confirm your profile and data-processing consent first")
        consent = _consent(user)
        if not (consent["health_data_processing"] and consent["personalization"]):
            raise PersonalizationConflict("Health-data and personalization consent are required first")
        if consent["external_memory_deletion_pending"]:
            raise PersonalizationConflict("Previous external-memory deletion is still pending")
        consent["external_memory"] = True
        _save_consent(user, consent,
                      external_memory_sync_pending=True,
                      external_memory_consented_at=datetime.now(timezone.utc).isoformat())
        db.flush()
        return {"enabled": True}


def revoke_external_memory_consent(subject: str) -> Dict[str, bool]:
    """Disable all reads/writes before attempting remote deletion."""
    with session_scope() as db:
        user = _get_user(db, subject, create=False, for_update=True)
        if user is None:
            return {"deletion_pending": False}
        consent = _consent(user)
        pending = consent["external_memory"] or consent["external_memory_deletion_pending"]
        consent["external_memory"] = False
        consent["external_memory_deletion_pending"] = pending
        _save_consent(user, consent,
                      external_memory_revoked_at=datetime.now(timezone.utc).isoformat())
        db.flush()
        return {"deletion_pending": pending}


def mark_external_memory_deleted(subject: str) -> None:
    with session_scope() as db:
        user = _get_user(db, subject, create=False, for_update=True)
        if user is not None:
            consent = _consent(user)
            consent["external_memory_deletion_pending"] = False
            _save_consent(user, consent,
                          external_memory_deleted_at=datetime.now(timezone.utc).isoformat())
            db.flush()


def _require_health_consent(user: User) -> None:
    if not _consent(user)["health_data_processing"]:
        raise PersonalizationConflict(
            "Health-data processing consent is required before storing measurements"
        )


def _profile_to_dict(user: User) -> Dict[str, Any]:
    return {
        "display_name": user.display_name,
        "age_range": user.age_range,
        "birth_date": _value(user.birth_date),
        "sex_at_birth": user.sex_at_birth,
        "height_cm": _value(user.height_cm),
        "activity_level": user.activity_level,
        "goal": user.goal,
        "dietary_preferences": user.dietary_preferences or [],
        "exercise_constraints": user.exercise_constraints or [],
        "medical_conditions": user.medical_conditions_data or [],
        "consent_flags": _consent(user),
        "confirmed_at": _value(user.profile_confirmed_at),
        "updated_at": _value(user.updated_at),
    }


def _empty_profile() -> Dict[str, Any]:
    return {
        "display_name": None,
        "age_range": None,
        "birth_date": None,
        "sex_at_birth": None,
        "height_cm": None,
        "activity_level": None,
        "goal": None,
        "dietary_preferences": [],
        "exercise_constraints": [],
        "medical_conditions": [],
        "consent_flags": dict(DEFAULT_CONSENT),
        "confirmed_at": None,
        "updated_at": None,
    }


def get_profile(subject: str) -> Dict[str, Any]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        return _profile_to_dict(user) if user is not None else _empty_profile()


def update_profile(subject: str, payload: Dict[str, Any], *, replace: bool) -> Dict[str, Any]:
    field_map = {"medical_conditions": "medical_conditions_data"}
    with session_scope() as db:
        user = _get_user(db, subject, create=True, for_update=True)
        proposed_consent = _consent(user)
        consent_payload = payload.get("consent_flags")
        if hasattr(consent_payload, "model_dump"):
            consent_payload = consent_payload.model_dump(mode="python")
        if isinstance(consent_payload, dict):
            proposed_consent = {
                "health_data_processing": bool(
                    consent_payload.get("health_data_processing", False)
                ),
                "personalization": bool(consent_payload.get("personalization", False)),
                "external_memory": proposed_consent["external_memory"],
                "external_memory_deletion_pending": proposed_consent["external_memory_deletion_pending"],
            }
        if proposed_consent["external_memory"] and not (
            proposed_consent["health_data_processing"] and proposed_consent["personalization"]
        ):
            raise PersonalizationConflict("Delete external memory before revoking parent consents")
        supplied_health_fields = {
            field_map.get(key, key)
            for key, value in payload.items()
            if value not in (None, [], {})
        } & HEALTH_PROFILE_FIELDS
        if supplied_health_fields and not proposed_consent["health_data_processing"]:
            raise PersonalizationConflict(
                "Health-data processing consent is required before storing health profile fields"
            )
        if replace:
            for field in PROFILE_FIELDS:
                if field == "consent_flags":
                    _save_consent(user, proposed_consent)
                else:
                    setattr(user, field, None)
        for key, value in payload.items():
            target = field_map.get(key, key)
            if target not in PROFILE_FIELDS:
                continue
            if isinstance(value, Enum):
                value = value.value
            elif hasattr(value, "model_dump"):
                value = value.model_dump(mode="python")
            if target == "consent_flags":
                _save_consent(user, proposed_consent)
            else:
                setattr(user, target, value)
        user.profile_confirmed_at = datetime.now(timezone.utc)
        db.flush()
        return _profile_to_dict(user)


def _goal_to_dict(goal: PersonalizationGoal) -> Dict[str, Any]:
    return {
        "id": str(goal.id),
        "version": goal.version,
        "goal_type": goal.goal_type,
        "target_weight_kg": _value(goal.target_weight_kg),
        "target_date": _value(goal.target_date),
        "training_days_per_week": goal.training_days_per_week,
        "weekly_activity_level": goal.weekly_activity_level,
        "constraints": goal.constraints or [],
        "status": goal.status,
        "supersedes_goal_id": _value(goal.supersedes_goal_id),
        "created_at": _value(goal.created_at),
        "updated_at": _value(goal.updated_at),
    }


def get_current_goal(subject: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return None
        goal = (
            db.query(PersonalizationGoal)
            .filter(
                PersonalizationGoal.user_id == user.id,
                PersonalizationGoal.status == "active",
            )
            .order_by(PersonalizationGoal.version.desc())
            .first()
        )
        return _goal_to_dict(goal) if goal else None


def list_goal_history(subject: str, limit: int = 50) -> List[Dict[str, Any]]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return []
        goals = (
            db.query(PersonalizationGoal)
            .filter(PersonalizationGoal.user_id == user.id)
            .order_by(PersonalizationGoal.version.desc())
            .limit(limit)
            .all()
        )
        return [_goal_to_dict(item) for item in goals]


def _latest_confirmed_query(db, user_id: uuid.UUID):
    return (
        db.query(InBodyMeasurement)
        .filter(
            InBodyMeasurement.user_id == user_id,
            InBodyMeasurement.deleted_at.is_(None),
            InBodyMeasurement.confirmed_by_user.is_(True),
        )
        .order_by(InBodyMeasurement.measured_at.desc(), InBodyMeasurement.id.desc())
    )


def _validate_goal_rate(db, user: User, payload: Dict[str, Any]) -> Optional[str]:
    target_weight = payload.get("target_weight_kg")
    target_date = payload.get("target_date")
    if target_weight is None or target_date is None:
        return "Target-rate validation was not applicable because weight or date was omitted"
    latest = _latest_confirmed_query(db, user.id).first()
    if latest is None or latest.weight_kg is None:
        return "No confirmed starting weight was available for target-rate validation"
    days = (target_date - date.today()).days
    weeks = max(days / 7.0, 1 / 7.0)
    current_weight = float(latest.weight_kg)
    weekly_fraction = abs(float(target_weight) - current_weight) / current_weight / weeks
    if weekly_fraction > 0.01:
        raise PersonalizationConflict(
            "Target weight changes faster than the supported 1% body-weight per week limit"
        )
    return None


def set_current_goal(subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _json_dict(payload)
    if isinstance(payload.get("target_date"), date):
        normalized["target_date"] = payload["target_date"]
    with session_scope() as db:
        user = _get_user(db, subject, create=True)
        _require_health_consent(user)
        _lock_user(db, user)
        quality_note = _validate_goal_rate(db, user, normalized)
        previous = (
            db.query(PersonalizationGoal)
            .filter(
                PersonalizationGoal.user_id == user.id,
                PersonalizationGoal.status == "active",
            )
            .with_for_update()
            .first()
        )
        max_version = (
            db.query(PersonalizationGoal.version)
            .filter(PersonalizationGoal.user_id == user.id)
            .order_by(PersonalizationGoal.version.desc())
            .first()
        )
        version = (max_version[0] if max_version else 0) + 1
        if previous is not None:
            previous.status = "superseded"
            db.flush()
        goal = PersonalizationGoal(
            user_id=user.id,
            version=version,
            goal_type=normalized["goal_type"],
            target_weight_kg=normalized.get("target_weight_kg"),
            target_date=normalized.get("target_date"),
            training_days_per_week=normalized.get("training_days_per_week"),
            weekly_activity_level=normalized.get("weekly_activity_level"),
            constraints=normalized.get("constraints", []),
            status=normalized.get("status", "active"),
            supersedes_goal_id=previous.id if previous else None,
        )
        db.add(goal)
        db.flush()
        result = _goal_to_dict(goal)
        result["data_quality_note"] = quality_note
        return result


def _measurement_to_dict(item: InBodyMeasurement) -> Dict[str, Any]:
    result = {
        "id": str(item.id),
        "measured_at": _value(item.measured_at),
        "measurement_date": _value(item.measurement_date),
        "source_type": item.source_type,
        "confidence": _value(item.confidence),
        "confirmed_by_user": bool(item.confirmed_by_user),
        "confirmed_at": _value(item.confirmed_at),
        "created_at": _value(item.created_at),
        "updated_at": _value(item.updated_at),
    }
    result.update({field: _value(getattr(item, field)) for field in METRIC_FIELDS})
    return result


def _validate_and_compute_bmi(data: Dict[str, Any], user: User) -> None:
    height = data.get("height_cm")
    if height is None:
        height = _value(user.height_cm)
    weight = data.get("weight_kg")
    if height is None or weight is None:
        return
    computed = round(float(weight) / ((float(height) / 100.0) ** 2), 2)
    supplied = data.get("bmi")
    if supplied is not None and abs(float(supplied) - computed) > 0.5:
        raise PersonalizationConflict("Supplied BMI conflicts with height and weight")
    data["bmi"] = computed


def create_measurement(subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _json_dict(payload)
    measured_at = payload["measured_at"]
    normalized["measured_at"] = measured_at
    with session_scope() as db:
        user = _get_user(db, subject, create=True)
        _require_health_consent(user)
        _validate_and_compute_bmi(normalized, user)
        confirmed = bool(normalized.get("confirmed_by_user", False))
        item = InBodyMeasurement(
            user_id=user.id,
            measurement_date=measured_at.date(),
            measured_at=measured_at,
            source_type=normalized.get("source_type", "manual"),
            confidence=normalized.get("confidence"),
            confirmed_by_user=confirmed,
            confirmed_at=datetime.now(timezone.utc) if confirmed else None,
            **{field: normalized.get(field) for field in METRIC_FIELDS},
        )
        db.add(item)
        db.flush()
        return _measurement_to_dict(item)


def _parse_uuid(resource_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(resource_id))
    except (ValueError, TypeError, AttributeError):
        raise PersonalizationNotFound()


def get_measurement(subject: str, measurement_id: str) -> Dict[str, Any]:
    resource_id = _parse_uuid(measurement_id)
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            raise PersonalizationNotFound()
        item = (
            db.query(InBodyMeasurement)
            .filter(
                InBodyMeasurement.id == resource_id,
                InBodyMeasurement.user_id == user.id,
                InBodyMeasurement.deleted_at.is_(None),
            )
            .first()
        )
        if item is None:
            raise PersonalizationNotFound()
        return _measurement_to_dict(item)


def _encode_cursor(item: InBodyMeasurement) -> str:
    raw = json.dumps({"measured_at": item.measured_at.isoformat(), "id": str(item.id)})
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> Tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        measured_at = datetime.fromisoformat(value["measured_at"])
        if measured_at.tzinfo is None or measured_at.utcoffset() is None:
            raise ValueError("cursor timestamp requires timezone")
        return measured_at, uuid.UUID(value["id"])
    except Exception as exc:
        raise PersonalizationConflict("Invalid measurement cursor") from exc


def list_measurements(
    subject: str,
    *,
    limit: int,
    cursor: Optional[str],
    confirmed_only: bool = False,
) -> Dict[str, Any]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return {"items": [], "next_cursor": None}
        query = db.query(InBodyMeasurement).filter(
            InBodyMeasurement.user_id == user.id,
            InBodyMeasurement.deleted_at.is_(None),
        )
        if confirmed_only:
            query = query.filter(InBodyMeasurement.confirmed_by_user.is_(True))
        if cursor:
            measured_at, resource_id = _decode_cursor(cursor)
            query = query.filter(
                or_(
                    InBodyMeasurement.measured_at < measured_at,
                    and_(
                        InBodyMeasurement.measured_at == measured_at,
                        InBodyMeasurement.id < resource_id,
                    ),
                )
            )
        rows = (
            query.order_by(InBodyMeasurement.measured_at.desc(), InBodyMeasurement.id.desc())
            .limit(limit + 1)
            .all()
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        return {
            "items": [_measurement_to_dict(item) for item in page],
            "next_cursor": _encode_cursor(page[-1]) if has_more and page else None,
        }


def patch_measurement(subject: str, measurement_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        raise PersonalizationConflict("At least one field is required")
    resource_id = _parse_uuid(measurement_id)
    normalized = _json_dict(payload)
    if isinstance(payload.get("measured_at"), datetime):
        normalized["measured_at"] = payload["measured_at"]
    if "measured_at" in normalized and normalized["measured_at"] is None:
        raise PersonalizationConflict("measured_at cannot be null")
    if "source_type" in normalized and normalized["source_type"] is None:
        raise PersonalizationConflict("source_type cannot be null")
    if "confirmed_by_user" in normalized and normalized["confirmed_by_user"] is None:
        raise PersonalizationConflict("confirmed_by_user cannot be null")
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            raise PersonalizationNotFound()
        _require_health_consent(user)
        item = (
            db.query(InBodyMeasurement)
            .filter(
                InBodyMeasurement.id == resource_id,
                InBodyMeasurement.user_id == user.id,
                InBodyMeasurement.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        if item is None:
            raise PersonalizationNotFound()
        candidate = {field: normalized.get(field, _value(getattr(item, field))) for field in METRIC_FIELDS}
        if ("height_cm" in normalized or "weight_kg" in normalized) and "bmi" not in normalized:
            candidate["bmi"] = None
        if not any(candidate.get(field) is not None for field in METRIC_FIELDS):
            raise PersonalizationConflict("At least one measurement metric is required")
        _validate_and_compute_bmi(candidate, user)
        for field in METRIC_FIELDS:
            if field in normalized or field == "bmi":
                setattr(item, field, candidate[field])
        for field in ("source_type", "confidence"):
            if field in normalized:
                setattr(item, field, normalized[field])
        if "measured_at" in normalized:
            item.measured_at = normalized["measured_at"]
            item.measurement_date = normalized["measured_at"].date()
        if "confirmed_by_user" in normalized:
            item.confirmed_by_user = bool(normalized["confirmed_by_user"])
            item.confirmed_at = datetime.now(timezone.utc) if item.confirmed_by_user else None
        db.flush()
        return _measurement_to_dict(item)


def delete_measurement(subject: str, measurement_id: str, reason: Optional[str]) -> None:
    resource_id = _parse_uuid(measurement_id)
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            raise PersonalizationNotFound()
        item = (
            db.query(InBodyMeasurement)
            .filter(
                InBodyMeasurement.id == resource_id,
                InBodyMeasurement.user_id == user.id,
                InBodyMeasurement.deleted_at.is_(None),
            )
            .first()
        )
        if item is None:
            raise PersonalizationNotFound()
        item.deleted_at = datetime.now(timezone.utc)
        item.delete_reason = reason


def _delta(current: InBodyMeasurement, previous: InBodyMeasurement) -> Dict[str, Optional[float]]:
    deltas: Dict[str, Optional[float]] = {}
    for field in METRIC_FIELDS:
        current_value = getattr(current, field)
        previous_value = getattr(previous, field)
        deltas[field] = (
            round(float(current_value) - float(previous_value), 2)
            if current_value is not None and previous_value is not None
            else None
        )
    return deltas


def get_progress(subject: str, timeline_limit: int = 30) -> Dict[str, Any]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            rows: List[InBodyMeasurement] = []
            total_count = 0
        else:
            confirmed_query = _latest_confirmed_query(db, user.id)
            total_count = confirmed_query.count()
            rows = confirmed_query.limit(timeline_limit).all()
        current = rows[0] if rows else None
        previous = rows[1] if len(rows) > 1 else None
        missing = []
        if current:
            missing = [field for field in METRIC_FIELDS if getattr(current, field) is None]
        return {
            "basis": "confirmed_non_deleted_measurements_only",
            "confirmed_record_count": total_count,
            "timeline_returned_count": len(rows),
            "current": _measurement_to_dict(current) if current else None,
            "previous": _measurement_to_dict(previous) if previous else None,
            "delta": _delta(current, previous) if current and previous else None,
            "days_between": (
                (current.measured_at - previous.measured_at).total_seconds() / 86400
                if current and previous
                else None
            ),
            "timeline": [_measurement_to_dict(item) for item in rows],
            "data_quality": {
                "missing_current_metrics": missing,
                "limitations": [
                    "Deltas describe recorded values and do not establish health improvement or causality",
                    "Device, timing, hydration and measurement conditions can affect comparability",
                ],
            },
        }


def _plan_to_dict(plan: PersonalizedPlan) -> Dict[str, Any]:
    return {
        "id": str(plan.id),
        "version": plan.version,
        "status": plan.status,
        "input_snapshot": plan.input_snapshot,
        "goal_version": plan.goal_version,
        "measurement_ids": plan.measurement_ids,
        "evidence_ids": plan.evidence_ids,
        "citations": plan.citations,
        "safety_result": plan.safety_result,
        "content": plan.content,
        "archived_at": _value(plan.archived_at),
        "archive_reason": plan.archive_reason,
        "created_at": _value(plan.created_at),
        "updated_at": _value(plan.updated_at),
    }


def _owned_confirmed_measurements(db, user: User, measurement_ids: Iterable[str]) -> List[InBodyMeasurement]:
    parsed = [_parse_uuid(item) for item in measurement_ids]
    if parsed:
        rows = (
            db.query(InBodyMeasurement)
            .filter(
                InBodyMeasurement.user_id == user.id,
                InBodyMeasurement.id.in_(parsed),
                InBodyMeasurement.deleted_at.is_(None),
                InBodyMeasurement.confirmed_by_user.is_(True),
            )
            .all()
        )
        if len(rows) != len(set(parsed)):
            raise PersonalizationNotFound()
        by_id = {row.id: row for row in rows}
        return [by_id[item] for item in parsed]
    latest = _latest_confirmed_query(db, user.id).first()
    return [latest] if latest else []


def create_plan(subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    serialized_size = len(json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8"))
    if serialized_size > 100_000:
        raise PersonalizationConflict("Plan payload exceeds 100 KB")
    normalized = _json_dict(payload)
    with session_scope() as db:
        user = _get_user(db, subject, create=True)
        consent = _consent(user)
        if not (consent["health_data_processing"] and consent["personalization"]):
            raise PersonalizationConflict("Health-data and personalization consent are required")
        _lock_user(db, user)
        measurements = _owned_confirmed_measurements(
            db, user, normalized.get("measurement_ids", [])
        )
        if normalized.get("status") == "active" and not measurements:
            raise PersonalizationConflict(
                "An active plan requires at least one confirmed measurement"
            )
        evidence_ids = normalized.get("evidence_ids", [])
        citations = normalized.get("citations", [])
        citation_ids = {
            str(item.get("document_id") or item.get("doc_id") or item.get("id"))
            for item in citations
            if isinstance(item, dict)
            and (item.get("document_id") or item.get("doc_id") or item.get("id"))
        }
        if normalized.get("status") == "active" and (
            not evidence_ids or not citations or not set(evidence_ids).issubset(citation_ids)
        ):
            raise PersonalizationConflict(
                "An active plan requires citations matching every evidence_id"
            )
        goal = (
            db.query(PersonalizationGoal)
            .filter(
                PersonalizationGoal.user_id == user.id,
                PersonalizationGoal.status == "active",
            )
            .first()
        )
        symptoms = normalized.get("symptoms", [])
        safety = check_medical_safety(
            " ".join(symptoms) if symptoms else "Lập kế hoạch sức khỏe cá nhân",
            user.medical_conditions_data or [],
        )
        if normalized.get("status") == "active" and safety.get("risk_level") != "low":
            raise PersonalizationConflict(
                "An active plan cannot be created while medical safety review is required"
            )
        max_version = (
            db.query(PersonalizedPlan.version)
            .filter(PersonalizedPlan.user_id == user.id)
            .order_by(PersonalizedPlan.version.desc())
            .first()
        )
        version = (max_version[0] if max_version else 0) + 1
        if normalized.get("status") == "active":
            active = (
                db.query(PersonalizedPlan)
                .filter(
                    PersonalizedPlan.user_id == user.id,
                    PersonalizedPlan.status == "active",
                )
                .with_for_update()
                .first()
            )
            if active:
                active.status = "archived"
                active.archived_at = datetime.now(timezone.utc)
                active.archive_reason = "superseded"
                db.flush()
        input_snapshot = {
            "profile": {
                "age_range": user.age_range,
                "sex_at_birth": user.sex_at_birth,
                "height_cm": _value(user.height_cm),
                "activity_level": user.activity_level,
                "dietary_preferences": user.dietary_preferences or [],
                "exercise_constraints": user.exercise_constraints or [],
                "medical_conditions": user.medical_conditions_data or [],
            },
            "goal": _goal_to_dict(goal) if goal else None,
            "measurements": [_measurement_to_dict(item) for item in measurements],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        plan = PersonalizedPlan(
            user_id=user.id,
            version=version,
            status=normalized.get("status", "draft"),
            input_snapshot=input_snapshot,
            goal_version=goal.version if goal else None,
            measurement_ids=[str(item.id) for item in measurements],
            evidence_ids=evidence_ids,
            citations=citations,
            safety_result=safety,
            content=normalized.get("content", {}),
        )
        db.add(plan)
        db.flush()
        return _plan_to_dict(plan)


def get_current_plan(subject: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return None
        plan = (
            db.query(PersonalizedPlan)
            .filter(
                PersonalizedPlan.user_id == user.id,
                PersonalizedPlan.status == "active",
            )
            .order_by(PersonalizedPlan.version.desc())
            .first()
        )
        return _plan_to_dict(plan) if plan else None


def list_plans(subject: str, limit: int = 50) -> List[Dict[str, Any]]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return []
        plans = (
            db.query(PersonalizedPlan)
            .filter(PersonalizedPlan.user_id == user.id)
            .order_by(PersonalizedPlan.version.desc())
            .limit(limit)
            .all()
        )
        return [_plan_to_dict(item) for item in plans]


def archive_plan(subject: str, plan_id: str, reason: Optional[str]) -> Dict[str, Any]:
    resource_id = _parse_uuid(plan_id)
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            raise PersonalizationNotFound()
        plan = (
            db.query(PersonalizedPlan)
            .filter(PersonalizedPlan.id == resource_id, PersonalizedPlan.user_id == user.id)
            .first()
        )
        if plan is None:
            raise PersonalizationNotFound()
        plan.status = "archived"
        plan.archived_at = datetime.now(timezone.utc)
        plan.archive_reason = reason
        db.flush()
        return _plan_to_dict(plan)


def _checkin_to_dict(item: CheckIn) -> Dict[str, Any]:
    return {
        "id": str(item.id),
        "checked_at": _value(item.checked_at),
        "adherence": item.adherence,
        "energy_level": item.energy_level,
        "sleep_quality": item.sleep_quality,
        "soreness": item.soreness,
        "symptoms": item.symptoms or [],
        "note": item.note,
        "safety_result": item.safety_result,
        "created_at": _value(item.created_at),
    }


def create_checkin(subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _json_dict(payload)
    checked_at = payload["checked_at"]
    with session_scope() as db:
        user = _get_user(db, subject, create=True)
        _require_health_consent(user)
        symptoms = normalized.get("symptoms", [])
        safety = check_medical_safety(
            " ".join(symptoms) if symptoms else "Không có triệu chứng được khai báo",
            user.medical_conditions_data or [],
        )
        item = CheckIn(
            user_id=user.id,
            checked_at=checked_at,
            adherence=normalized.get("adherence"),
            energy_level=normalized.get("energy_level"),
            sleep_quality=normalized.get("sleep_quality"),
            soreness=normalized.get("soreness"),
            symptoms=symptoms,
            note=normalized.get("note"),
            safety_result=safety,
        )
        db.add(item)
        db.flush()
        return _checkin_to_dict(item)


def list_checkins(subject: str, limit: int = 50) -> List[Dict[str, Any]]:
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return []
        rows = (
            db.query(CheckIn)
            .filter(CheckIn.user_id == user.id)
            .order_by(CheckIn.checked_at.desc(), CheckIn.id.desc())
            .limit(limit)
            .all()
        )
        return [_checkin_to_dict(item) for item in rows]


def build_confirmed_personalization_context(subject: str) -> Dict[str, Any]:
    """Return only consented profile and confirmed, non-deleted measurements."""
    with session_scope() as db:
        user = _get_user(db, subject, create=False)
        if user is None:
            return {"available": False, "reason": "profile_not_found", "provenance": []}
        consent = _consent(user)
        if not (consent["health_data_processing"] and consent["personalization"]):
            return {"available": False, "reason": "consent_required", "provenance": []}
        latest = _latest_confirmed_query(db, user.id).first()
        goal = (
            db.query(PersonalizationGoal)
            .filter(
                PersonalizationGoal.user_id == user.id,
                PersonalizationGoal.status == "active",
            )
            .first()
        )
        provenance: List[Dict[str, Any]] = [
            {"type": "profile", "confirmed_at": _value(user.profile_confirmed_at)}
        ]
        if latest:
            provenance.append(
                {
                    "type": "measurement",
                    "id": str(latest.id),
                    "measured_at": _value(latest.measured_at),
                    "confirmed_at": _value(latest.confirmed_at),
                }
            )
        if goal:
            provenance.append({"type": "goal", "id": str(goal.id), "version": goal.version})
        from memory.store import facts_for_context
        from memory.context import event_context
        facts = facts_for_context(db, user)
        events = event_context(db, user, goal)
        return {
            "available": True,
            "confirmed_memory": facts,
            "memory_events": events,
            "external_memory_consent": consent["external_memory"] and not consent["external_memory_deletion_pending"],
            "profile": {
                "age_range": user.age_range,
                "sex_at_birth": user.sex_at_birth,
                "height_cm": _value(user.height_cm),
                "activity_level": user.activity_level,
                "goal": user.goal,
                "dietary_preferences": user.dietary_preferences or [],
                "exercise_constraints": user.exercise_constraints or [],
                "medical_conditions": user.medical_conditions_data or [],
            },
            "active_goal": _goal_to_dict(goal) if goal else None,
            "latest_confirmed_measurement": _measurement_to_dict(latest) if latest else None,
            "provenance": provenance,
        }


def safe_build_confirmed_context(subject: Optional[str]) -> Dict[str, Any]:
    if not subject:
        return {"available": False, "reason": "authentication_required", "provenance": []}
    try:
        return build_confirmed_personalization_context(subject)
    except Exception:
        logger.warning("Personalization context unavailable due to a persistence error")
        return {
            "available": False,
            "reason": "personalization_temporarily_unavailable",
            "provenance": [],
        }


def redacted_context(subject: str) -> Dict[str, Any]:
    context = safe_build_confirmed_context(subject)
    profile = context.get("profile") or {}
    if "medical_conditions" in profile:
        profile["medical_conditions"] = {
            "present": bool(profile["medical_conditions"]),
            "count": len(profile["medical_conditions"]),
        }
    context["profile"] = profile
    return context
