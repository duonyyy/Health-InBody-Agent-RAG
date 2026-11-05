# WP-02 backend gộp: HTTP runtime trên stack thử nghiệm

Ngày: 2026-11-05. HEAD: `8d0ae8cc4eff0f65ef770c3abc56063e999d5895` cộng working tree chưa commit. Image kiểm thử: `sha256:8eaf1d7e5def2891e0bf0ddd949a169d303ef498895f3fbf2882aefe2f5fee35`.

## Phạm vi và preflight

- Trước khi chạy: Docker daemon hoạt động nhưng không có container đang chạy; không thấy import process. Các volume cũ (`compose_*`, `wp01_*`) được giữ nguyên. Không restart collection/embedding/backend đang phục vụ và không swap alias.
- Dựng network `wp02-runtime-net` và 5 container `wp02-runtime-*` trên writable layer tạm, không mount các volume dữ liệu cũ. PostgreSQL 16, Qdrant 1.20, Valkey, BGE-M3 CPU và backend một Uvicorn worker. Model embedding báo `cpu`, `float32`, 1024 chiều, batch 8.
- Cấu hình backend: `AUTH_MODE=development`, `LLM_PROVIDER=none`, `BM25_AUTOLOAD=false`, `ZEP_MEMORY_ENABLED=false`, `FEATURE_OCR_UPLOAD=false`. PostgreSQL và Qdrant chỉ chứa fixture tổng hợp. Không dùng API key thật, provider LLM, frontend hoặc corpus sản phẩm.
- Build ban đầu lỗi Debian Bullseye security package 404. Đổi backend Dockerfile sang Python 3.10 slim Bookworm và bỏ bốn dependency `llama-index*` không được backend import. Build lại thành công; schema ORM khởi tạo trên PostgreSQL thử nghiệm.

## Kết quả HTTP từ process client tới Uvicorn trong container

| Ca | Kết quả |
|---|---|
| `GET /health` | 200, `healthy` |
| `POST /search`, query BMI | 200, lấy `wp02-synthetic-1` từ Qdrant qua embedding thật |
| Agent urgent đau ngực + khó thở | 200, `urgent_safety`, không retrieved docs, có request ID |
| Agent BMI 72 kg/170 cm | 200, `inbody_tools` |
| Agent chào hỏi | 200, `general_chat` |
| Agent InBody | 200 `degraded`, 1 retrieved doc; composer thiếu LLM theo cấu hình |
| Agent nutrition và exercise | 200, không retrieved docs trong corpus tổng hợp nhỏ; không dùng để suy ra chất lượng |
| Agent medical caution về thuốc | 200 `degraded`, `RAGAgent`, lấy `wp02-safety-2`; composer thiếu LLM |
| `POST /tools/bmi` với cân nặng âm | 422 |
| Agent không có identity | 401 |
| Profile consent + 2 lượt `/chat/complete` | 200; conversation ID được tái sử dụng, request ID có; PostgreSQL có 1 session/4 messages |
| User B dùng conversation ID của A | 404 |
| Bản đo 72 kg đã xác nhận và OCR 99 kg chưa xác nhận | Provenance Agent khớp duy nhất bản 72 kg đã xác nhận |
| Thu hồi consent rồi hỏi lại | 200, `personalization_used.available=false`, `reason=consent_required` |

Qdrant collection thử nghiệm `wp02_synthetic_corpus` ở trạng thái `green`, 2 point tổng hợp. Kết quả `green`/2 point chỉ chứng minh kiểm thử đường gọi, không chứng minh corpus đầy đủ, RAG relevance hoặc citation quality. Truy vấn safety chung chỉ chứa từ “triệu chứng” được phân loại `low` và chọn `GeneralChatAgent`; ca có “thuốc” kích hoạt `medical_caution` và safety retrieval. Đây là giới hạn từ bộ từ khóa deterministic hiện tại, cần đánh giá ở WP-03/WP-05.

## Kết luận và giới hạn

**VERIFIED_RUNTIME trên stack thử nghiệm biệt lập** cho đường HTTP backend gộp ↔ PostgreSQL, Qdrant và embedding. Đây không phải deployment vào Compose/volume hiện hữu. LLM, auth production, frontend adapter, dữ liệu thật, latency P95, retrieval holdout và dependency-down chưa được nghiệm thu. Các test trong process trước đó là 147/147 backend unit; build image và HTTP ở đây là bằng chứng riêng. Không commit, stage hoặc push.

Sau kiểm thử đã dừng/xóa đúng 5 container `wp02-runtime-*`, network `wp02-runtime-net` và image `wp02-backend-runtime:local`. Không tạo hoặc xóa volume; không đụng container khác.
