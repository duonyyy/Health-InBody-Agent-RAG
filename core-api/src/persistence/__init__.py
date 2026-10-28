"""Persistence module for core-api."""

from .database import Base, SessionLocal, engine, get_db, init_db, session_scope
from .models import CheckIn, InBodyMeasurement, PersonalizationGoal, User
from .personalization_service import (
    get_profile,
    update_profile,
    create_measurement,
    get_measurement,
    list_measurements,
    get_current_goal,
    list_goal_history,
    get_progress,
    create_checkin,
    list_checkins,
    safe_build_confirmed_context,
)

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "session_scope",
    "init_db",
    "User",
    "InBodyMeasurement",
    "PersonalizationGoal",
    "CheckIn",
    "get_profile",
    "update_profile",
    "create_measurement",
    "get_measurement",
    "list_measurements",
    "get_current_goal",
    "list_goal_history",
    "get_progress",
    "create_checkin",
    "list_checkins",
    "safe_build_confirmed_context",
]
