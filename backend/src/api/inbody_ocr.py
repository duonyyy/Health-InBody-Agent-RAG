"""Authenticated gateway for private InBody extraction; it does not save OCR output."""

import os

import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from auth.context import CurrentUser, get_current_user

router = APIRouter(prefix="/me", tags=["inbody-ocr"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class OcrField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float
    raw_text: str = Field(max_length=80)
    page_number: int = Field(ge=1)
    confidence: float | None = None


class OcrResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: str
    parser_version: str
    status: str
    extracted_fields: dict[str, OcrField]
    unresolved_fields: list[str]
    warnings: list[str]


def _has_health_consent(subject: str) -> bool:
    # Import at request time so the OCR contract can be tested without a database driver.
    from api.personalization import _execute
    from persistence.personalization_service import get_profile

    profile = _execute(get_profile, subject)
    return bool(profile.get("consent_flags", {}).get("health_data_processing", False))


@router.post("/inbody-ocr", response_model=OcrResult)
def extract_inbody(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> OcrResult:
    if os.getenv("FEATURE_OCR_UPLOAD", "false").lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=404, detail="Not found")
    if not _has_health_consent(current_user.subject):
        raise HTTPException(status_code=409, detail="Cần đồng ý xử lý dữ liệu sức khỏe trước khi OCR.")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File rỗng hoặc quá lớn.")
    url = os.getenv("OCR_SERVICE_URL", "http://ocr-api:18100").rstrip("/")
    try:
        with requests.Session() as session:
            # Ignore host proxy settings for private health files on the Docker network.
            session.trust_env = False
            response = session.post(
                f"{url}/ocr/inbody",
                files={"file": (file.filename or "report", content, file.content_type or "application/octet-stream")},
                timeout=100,
            )
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="OCR quá thời gian chờ.") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Dịch vụ OCR tạm thời không khả dụng.") from exc
    if response.status_code >= 400:
        if response.status_code in {400, 413, 422}:
            raise HTTPException(status_code=response.status_code, detail="Không đọc được file InBody.")
        if response.status_code in {503, 504}:
            raise HTTPException(status_code=response.status_code, detail="Dịch vụ OCR tạm thời không khả dụng.")
        raise HTTPException(status_code=502, detail="Dịch vụ OCR tạm thời không khả dụng.")
    try:
        result = OcrResult.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail="Dịch vụ OCR trả dữ liệu không hợp lệ.") from exc
    if result.document_type != "inbody_result" or result.status != "needs_confirmation":
        raise HTTPException(status_code=502, detail="Dịch vụ OCR trả dữ liệu không hợp lệ.")
    return result
