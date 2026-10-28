"""Uniform API Envelope specification for all REST & internal service responses."""

from datetime import datetime, timezone
from typing import Any, Dict, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIError(BaseModel):
    code: str = Field(..., description="Machine-readable error code, e.g., VALIDATION_ERROR, NOT_FOUND")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed validation errors or context")


class UniformEnvelope(BaseModel, Generic[T]):
    """
    Standard enterprise envelope matching RetailMind AI and MWG platform standard:
    {
      "success": true,
      "data": { ... },
      "error": null,
      "meta": { "request_id": "...", "timestamp": "...", "latency_ms": 12.3 }
    }
    """
    success: bool
    data: Optional[T] = None
    error: Optional[APIError] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: T, meta: Optional[Dict[str, Any]] = None) -> "UniformEnvelope[T]":
        current_meta = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            current_meta.update(meta)
        return cls(success=True, data=data, error=None, meta=current_meta)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "UniformEnvelope[None]":
        current_meta = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            current_meta.update(meta)
        return cls(
            success=False,
            data=None,
            error=APIError(code=code, message=message, details=details),
            meta=current_meta,
        )
