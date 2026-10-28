"""Authenticated `/me` API for P1 personalization data."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from auth.context import CurrentUser, get_current_user, personalization_debug_enabled
try:
    from memory import sync as memory_sync
except ImportError:
    memory_sync = None
from persistence import personalization_service as service
from persistence.schemas import (
    CheckInCreateRequest,
    GoalCurrentRequest,
    MeasurementCreate,
    MeasurementPatch,
    PlanArchiveRequest,
    PlanCreateRequest,
    ProfileUpdate,
    model_to_dict,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/me", tags=["personalization"])


class MemoryConsentRequest(BaseModel):
    acknowledged_external_processing: bool


def _require_trusted_memory_identity(current_user: CurrentUser) -> None:
    if current_user.auth_source == "server_context":
        return
    if (current_user.auth_source == "development_header"
            and os.getenv("ZEP_ALLOW_DEV_IDENTITY", "false").lower() in {"1", "true", "yes", "on"}):
        return
    raise HTTPException(status_code=403, detail="Trusted authentication is required for external memory")


@router.put("/memory-consent")
def enable_memory(data: MemoryConsentRequest, current_user: CurrentUser = Depends(get_current_user)):
    _require_trusted_memory_identity(current_user)
    if data.acknowledged_external_processing is not True:
        raise HTTPException(status_code=422, detail="Explicit acknowledgement of external processing is required")
    return _execute(service.grant_external_memory_consent, current_user.subject)


@router.delete("/memory", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(current_user: CurrentUser = Depends(get_current_user)):
    _require_trusted_memory_identity(current_user)
    result = _execute(service.revoke_external_memory_consent, current_user.subject)
    if result["deletion_pending"]:
        try:
            memory_sync.finish_deletion(current_user.subject)
        except Exception as exc:
            logger.warning("External memory deletion failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="External-memory deletion is pending; retry later") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _execute(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except service.PersonalizationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
    except Exception as exc:
        logger.warning("Personalization operation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Personalization storage is temporarily unavailable",
        ) from exc


@router.get("/profile")
def profile(current_user: CurrentUser = Depends(get_current_user)):
    return _execute(service.get_profile, current_user.subject)


@router.put("/profile")
def replace_profile(data: ProfileUpdate, current_user: CurrentUser = Depends(get_current_user)):
    return _execute(
        service.update_profile,
        current_user.subject,
        model_to_dict(data),
        replace=True,
    )


@router.patch("/profile")
def patch_profile(data: ProfileUpdate, current_user: CurrentUser = Depends(get_current_user)):
    values = model_to_dict(data)
    if not values:
        raise HTTPException(status_code=422, detail="At least one profile field is required")
    return _execute(
        service.update_profile,
        current_user.subject,
        values,
        replace=False,
    )


@router.get("/goals/current")
def current_goal(current_user: CurrentUser = Depends(get_current_user)):
    return {"goal": _execute(service.get_current_goal, current_user.subject)}


@router.put("/goals/current")
def update_current_goal(
    data: GoalCurrentRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.set_current_goal, current_user.subject, model_to_dict(data))


@router.get("/goals/history")
def goal_history(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": _execute(service.list_goal_history, current_user.subject, limit)}


@router.get("/measurements")
def measurements(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None, max_length=1000),
    confirmed_only: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(
        service.list_measurements,
        current_user.subject,
        limit=limit,
        cursor=cursor,
        confirmed_only=confirmed_only,
    )


@router.post("/measurements", status_code=status.HTTP_201_CREATED)
def add_measurement(
    data: MeasurementCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.create_measurement, current_user.subject, model_to_dict(data))


@router.get("/measurements/{measurement_id}")
def measurement(
    measurement_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.get_measurement, current_user.subject, measurement_id)


@router.patch("/measurements/{measurement_id}")
def update_measurement(
    measurement_id: str,
    data: MeasurementPatch,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(
        service.patch_measurement,
        current_user.subject,
        measurement_id,
        model_to_dict(data),
    )


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_measurement(
    measurement_id: str,
    reason: Optional[str] = Query(default=None, max_length=240),
    current_user: CurrentUser = Depends(get_current_user),
):
    _execute(service.delete_measurement, current_user.subject, measurement_id, reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/progress")
@router.get("/progress/summary")
def progress_summary(current_user: CurrentUser = Depends(get_current_user)):
    result = _execute(service.get_progress, current_user.subject, 2)
    result.pop("timeline", None)
    return result


@router.get("/progress/timeline")
def progress_timeline(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.get_progress, current_user.subject, limit)


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def add_plan(
    data: PlanCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.create_plan, current_user.subject, model_to_dict(data))


@router.get("/plans/current")
def current_plan(current_user: CurrentUser = Depends(get_current_user)):
    return {"plan": _execute(service.get_current_plan, current_user.subject)}


@router.get("/plans")
def plans(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": _execute(service.list_plans, current_user.subject, limit)}


@router.post("/plans/{plan_id}/archive")
def archive_plan(
    plan_id: str,
    data: PlanArchiveRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(
        service.archive_plan,
        current_user.subject,
        plan_id,
        data.reason,
    )


@router.post("/check-ins", status_code=status.HTTP_201_CREATED)
def add_checkin(
    data: CheckInCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return _execute(service.create_checkin, current_user.subject, model_to_dict(data))


@router.get("/check-ins")
def checkins(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": _execute(service.list_checkins, current_user.subject, limit)}


@router.get("/personalization-context")
def personalization_context(current_user: CurrentUser = Depends(get_current_user)):
    if not personalization_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    return _execute(service.redacted_context, current_user.subject)
