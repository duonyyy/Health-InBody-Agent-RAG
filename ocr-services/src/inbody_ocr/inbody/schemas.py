"""Extraction contract. OCR values remain unconfirmed until a user reviews them."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    value: float
    raw_text: str = Field(min_length=1, max_length=80)
    page_number: int = Field(ge=1)
    # No calibrated confidence model exists yet. Never invent a probability.
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class InBodyResponse(BaseModel):
    document_type: Literal["inbody_result"] = "inbody_result"
    parser_version: Literal["inbody-v1"] = "inbody-v1"
    status: Literal["needs_confirmation"] = "needs_confirmation"
    extracted_fields: dict[str, ExtractedField] = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
