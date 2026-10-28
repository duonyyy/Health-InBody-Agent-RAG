# InBody OCR Service - PaddleOCR + Text LLM

Dịch vụ trích xuất chỉ số phiếu InBody theo kiến trúc **Two-Stage**:
1. **PaddleOCR** (chạy trên CPU, tối ưu VRAM): nhận diện toàn bộ vùng chữ số và bounding box từ ảnh phiếu InBody.
2. **Spatial Layout Formatter**: gom cụm theo dòng và sắp xếp không gian (top-to-bottom, left-to-right) để bảo toàn cấu trúc bảng biểu.
3. **Text-only LLM (qua Ollama)**: hiểu ngữ cảnh và bóc tách các chỉ số đo thực tế thành JSON object (không cần model thị giác VLM).
4. **Deterministic Validation**: đối chiếu từng số (`value`) với chuỗi ký tự nhìn thấy (`raw_text`), giới hạn dải đo y tế, phát hiện xung đột đa trang và trả về trạng thái `needs_confirmation`.

API contract giữ nguyên hoàn toàn tương thích với backend gateway (`/me/inbody-ocr`).

## Endpoints

- `GET /health`: Trạng thái kết nối LLM và engine PaddleOCR.
- `POST /ocr/inbody`: Nhận file JPG/PNG/WebP/PDF (tối đa 10 MiB, mặc định tối đa 2 trang PDF). Trả về:
  ```json
  {
    "document_type": "inbody_result",
    "parser_version": "inbody-paddle-v1",
    "status": "needs_confirmation",
    "extracted_fields": { ... },
    "unresolved_fields": [ ... ],
    "warnings": [ ... ]
  }
  ```

## Chạy thử nghiệm độc lập

```powershell
python -m pip install -e ".[test]"
python -B -m pytest -q -p no:cacheprovider
python -m uvicorn inbody_ocr.main:app --host 127.0.0.1 --port 18100
```
