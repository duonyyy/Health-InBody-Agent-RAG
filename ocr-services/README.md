# InBody OCR (source-ready)

Dịch vụ này chỉ hỗ trợ trích xuất chỉ số từ ảnh/PDF phiếu InBody. Nó không chẩn đoán, tư vấn hoặc tự lưu kết quả đo. Model thị giác được cấu hình bằng `OCR_OLLAMA_MODEL` trong Docker Compose; không giả định model cụ thể hay độ chính xác đã được chứng minh.

## API và luồng dữ liệu

- `GET /health`: trạng thái kết nối tới Ollama/model.
- `POST /ocr/inbody`: một file JPG/PNG/WebP/PDF, tối đa 10 MiB và 2 trang PDF mặc định. Trả `status=needs_confirmation`, `extracted_fields`, `unresolved_fields`, `warnings`.
- Mỗi trường đã đọc có `value`, `raw_text`, `page_number`, `confidence=null`. Chưa có mô hình confidence được hiệu chuẩn; không diễn giải `null` là độ tin cậy cao.
- Trường ngoài giới hạn API measurement, thiếu raw evidence hoặc mâu thuẫn giữa hai trang được giữ lại để nhập tay.
- Backend chính cung cấp gateway có xác thực `/me/inbody-ocr`, yêu cầu consent xử lý dữ liệu sức khỏe và bật bằng `FEATURE_OCR_UPLOAD=true`. Frontend hiển thị bản nháp để người dùng đối chiếu từng số trước khi lưu `/me/measurements` với `source_type=ocr_confirmed`.
- Service không lưu file lâu dài. Thư viện chuyển PDF có thể tạo file tạm trong lúc xử lý; cần kiểm chứng nơi lưu và cơ chế xóa trước khi xử lý dữ liệu thật. Dịch vụ gửi ảnh tới Ollama theo `OCR_OLLAMA_URL`; cả frontend, gateway và Ollama client bỏ qua proxy môi trường cho đường truyền này. Chỉ dùng hạ tầng xử lý dữ liệu sức khỏe đã được chấp thuận.

## Cấu trúc

- `src/inbody_ocr/api/`: HTTP contract và dependency.
- `src/inbody_ocr/clients/`: kết nối Ollama.
- `src/inbody_ocr/imaging/`: kiểm tra và chuyển ảnh/PDF.
- `src/inbody_ocr/inbody/`: prompt, schema và trích xuất chỉ số.
- `src/inbody_ocr/common/`: đọc JSON đầu ra.
- `tests/unit/`, `tests/api/`: kiểm tra logic và API trong process.

Dependency và cấu hình test nằm trong `pyproject.toml`. ASGI entrypoint là `inbody_ocr.main:app`.

## Chạy và kiểm tra

Trong thư mục `ocr-services`, tạo `.env` từ `.env.example` và đặt `OCR_OLLAMA_MODEL` thành model thị giác đã có. Khi chạy Python trực tiếp trên host, đặt `OCR_OLLAMA_URL=http://127.0.0.1:11434`; khi chạy trong container, mặc định là `http://host.docker.internal:11434`.

```powershell
python -m pip install -e ".[test]"
python -B -m pytest -q -p no:cacheprovider
python -m uvicorn inbody_ocr.main:app --host 127.0.0.1 --port 18100
```

Để chạy container sau khi Docker network `internal-network` đã tồn tại:

```powershell
docker compose -f ocr-services/compose.yaml config
docker compose -f ocr-services/compose.yaml up --build -d
```

Compose giữ service name `ocr-api` và chỉ `expose` cổng 18100 trong mạng nội bộ. Backend gọi `http://ocr-api:18100/ocr/inbody`. `FEATURE_OCR_UPLOAD` ở backend/frontend vẫn mặc định tắt; chỉ bật sau khi các gate về độ đúng OCR, quyền riêng tư và runtime được kiểm chứng.

## Giới hạn nghiệm thu

Test in-process dùng model giả để kiểm tra contract và xử lý lỗi. Chưa có bộ phiếu InBody được gán nhãn để đo độ đúng từng trường, chưa xác minh runtime HTTP/Docker và chưa có vòng đời lưu/xóa provenance file. Do đó chưa bật cho người dùng thật hoặc dùng kết quả chưa xác nhận để cá nhân hóa.

Trước khi phân phối hoặc dùng mã từ nguồn bên ngoài, cần xác minh quyền sử dụng và giữ thông tin ghi công/giấy phép tương ứng. Việc đổi cấu trúc không thay đổi nguồn gốc mã.

Source, UI và test cho các loại giấy tờ khác đã được xóa theo phạm vi InBody.
