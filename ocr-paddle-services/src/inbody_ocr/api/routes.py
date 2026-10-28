"""FastAPI HTTP routes for InBody OCR Paddle Service."""

import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from inbody_ocr.api.dependencies import get_inbody_service, get_ollama_client, get_paddle_reader
from inbody_ocr.clients.ollama import OllamaError, OllamaModelNotFoundError, OllamaTimeoutError
from inbody_ocr.clients.paddle import PaddleOcrError
from inbody_ocr.config import get_settings
from inbody_ocr.imaging.preprocess import FileValidationError, PdfConversionError, prepare_upload_images
from inbody_ocr.inbody.schemas import InBodyResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="InBody OCR Paddle Service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    reachable, available, _ = get_ollama_client().health()
    paddle_ok = get_paddle_reader().is_available()
    ok = reachable and available and paddle_ok
    return {
        "status": "ok" if ok else "degraded",
        "model_available": available,
        "paddle_ready": paddle_ok,
    }


@app.post("/ocr/inbody", response_model=InBodyResponse)
async def ocr_inbody(file: UploadFile = File(...)) -> InBodyResponse:
    settings = get_settings()
    try:
        content = await file.read(settings.max_upload_bytes + 1)
        if not content or len(content) > settings.max_upload_bytes:
            raise FileValidationError("File rỗng hoặc vượt giới hạn dung lượng.")
        images = await run_in_threadpool(prepare_upload_images, content, file.filename, settings)
        if not settings.ollama_model:
            raise OllamaModelNotFoundError("Chưa cấu hình model LLM bóc tách văn bản.")
        return await run_in_threadpool(get_inbody_service().extract, images)
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PdfConversionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OllamaModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail="OCR quá thời gian chờ.") from exc
    except (OllamaError, PaddleOcrError) as exc:
        logger.warning("OCR processing error: %s", exc)
        raise HTTPException(status_code=502, detail="Dịch vụ OCR tạm thời không khả dụng.") from exc
    finally:
        await file.close()
