"""Boundary validation for P1 personalization request models."""

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from persistence.schemas import (
    CheckInCreateRequest,
    GoalCurrentRequest,
    MeasurementCreate,
    ProfileUpdate,
)


def test_profile_rejects_two_age_representations_and_extreme_height():
    with pytest.raises(ValidationError):
        ProfileUpdate(age_range="25_34", birth_date=date(1995, 1, 1))
    with pytest.raises(ValidationError):
        ProfileUpdate(height_cm=400)


def test_profile_sanitizes_text_and_deduplicates_lists():
    profile = ProfileUpdate(
        display_name="  Nguyen   Van A  ",
        dietary_preferences=["  an chay ", "an chay", " it muoi "],
    )
    assert profile.display_name == "Nguyen Van A"
    assert profile.dietary_preferences == ["an chay", "it muoi"]


def test_goal_rejects_past_date_and_invalid_training_frequency():
    with pytest.raises(ValidationError):
        GoalCurrentRequest(goal_type="fat_loss", target_date=date.today())
    with pytest.raises(ValidationError):
        GoalCurrentRequest(goal_type="fitness", training_days_per_week=8)


def test_measurement_requires_timezone_and_at_least_one_metric():
    with pytest.raises(ValidationError):
        MeasurementCreate(measured_at=datetime.now(), weight_kg=70)
    with pytest.raises(ValidationError):
        MeasurementCreate(measured_at=datetime.now(timezone.utc))


def test_measurement_and_checkin_reject_future_or_out_of_range_values():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    with pytest.raises(ValidationError):
        MeasurementCreate(measured_at=future, weight_kg=70)
    with pytest.raises(ValidationError):
        CheckInCreateRequest(
            checked_at=datetime.now(timezone.utc),
            energy_level=6,
        )
