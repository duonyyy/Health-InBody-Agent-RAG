"""Bounded image/PDF decoding for InBody reports."""

import base64
import io
import warnings
from dataclasses import dataclass

from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
from PIL import Image, ImageOps, UnidentifiedImageError

from inbody_ocr.config import Settings

Image.MAX_IMAGE_PIXELS = 20_000_000


class FileValidationError(ValueError):
    pass


class PdfConversionError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    page_number: int
    image_base64: str


def prepare_upload_images(content: bytes, filename: str | None, settings: Settings) -> list[PreparedImage]:
    suffix = (filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in {"jpg", "jpeg", "png", "webp", "pdf"}:
        raise FileValidationError("Chỉ hỗ trợ JPG, PNG, WebP hoặc PDF.")
    if suffix == "pdf":
        if not content.startswith(b"%PDF-"):
            raise FileValidationError("Nội dung không phải PDF hợp lệ.")
        try:
            count = int(pdfinfo_from_bytes(content)["Pages"])
            if count < 1:
                raise FileValidationError("PDF không có trang nào.")
            if count > settings.max_pdf_pages:
                raise FileValidationError("PDF có quá nhiều trang.")
            pages = convert_from_bytes(content, dpi=settings.pdf_dpi, first_page=1, last_page=count)
        except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError, OSError, KeyError, ValueError) as exc:
            if isinstance(exc, FileValidationError):
                raise
            raise PdfConversionError("Không thể đọc PDF.") from exc
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = Image.open(io.BytesIO(content))
                image.load()
            expected = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[suffix]
            if image.format != expected:
                raise FileValidationError("Định dạng ảnh không khớp phần mở rộng.")
            pages = [image]
        except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
            raise FileValidationError("Không thể đọc ảnh hoặc ảnh quá lớn.") from exc
    prepared = []
    for number, image in enumerate(pages, start=1):
        if image.width * image.height > Image.MAX_IMAGE_PIXELS:
            raise FileValidationError("Ảnh có quá nhiều điểm ảnh.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((settings.max_image_side, settings.max_image_side), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=92)
        prepared.append(PreparedImage(number, base64.b64encode(buffer.getvalue()).decode("ascii")))
    return prepared
