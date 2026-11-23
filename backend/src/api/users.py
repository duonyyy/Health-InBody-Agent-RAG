"""Legacy user profile and measurement endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.common import _health_probe_timeout_seconds, _raise_lane_http_error
from api.schemas import InBodyMeasurementRequest, UserProfileRequest
from auth.context import CurrentUser, get_current_user, require_legacy_user_match
from core.execution import CapacityExceededError, QueueTimeoutError, get_lane
from harness.budget import BudgetExhaustedError, RequestBudget
from persistence.personalization import (
    add_inbody_measurement,
    get_user_profile,
    list_inbody_measurements,
    upsert_user_profile,
)
from persistence.personalization_service import redacted_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/profile")
async def user_profile(user_id: str, current_user: CurrentUser = Depends(get_current_user)):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            get_user_profile, user_id, auto_create=True, budget=budget, pass_cancel_event=False
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Get user profile failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to load user profile")


@router.put("/{user_id}/profile")
async def update_user_profile(
    user_id: str,
    data: UserProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            upsert_user_profile,
            user_id,
            data.dict(exclude_unset=True),
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Update user profile failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to update user profile")


@router.get("/{user_id}/measurements")
async def user_measurements(
    user_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        items = await get_lane("probe").run(
            list_inbody_measurements, user_id, limit=limit, budget=budget, pass_cancel_event=False
        )
        return {"measurements": items}
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("List user measurements failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to list user measurements")


@router.post("/{user_id}/measurements")
async def create_user_measurement(
    user_id: str,
    data: InBodyMeasurementRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            add_inbody_measurement,
            user_id,
            data.dict(exclude_unset=True),
            budget=budget,
            pass_cancel_event=False,
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
    except Exception as e:
        logger.error("Create user measurement failed: %s", e)
        raise HTTPException(status_code=500, detail="Unable to create user measurement")


@router.get("/{user_id}/personalization-context")
async def user_personalization_context(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    require_legacy_user_match(user_id, current_user)
    budget = RequestBudget.start(_health_probe_timeout_seconds(), max_timeout_seconds=10.0)
    try:
        return await get_lane("probe").run(
            redacted_context, current_user.subject, budget=budget, pass_cancel_event=False
        )
    except (CapacityExceededError, QueueTimeoutError, BudgetExhaustedError) as exc:
        _raise_lane_http_error(exc)
