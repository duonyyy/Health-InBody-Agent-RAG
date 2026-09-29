# Đợt 2 — Tiến độ gia cố harness (2026-09-27)

**Trạng thái: source-ready, chưa deploy; chưa qua gate runtime/clinical.** Không restart container, không import/chạm Qdrant, không commit/stage/push. Các thay đổi P1 có sẵn trong `graph.py` và `app.py` được giữ nguyên.

## Đã triển khai

1. Tạo `backend/src/harness/` với `guards.py` (lọc chỉ thị trong Qdrant/web, kiểm tra claim–evidence–chunk) và `budget.py` (phân loại lỗi retry tạm thời). `graph.py` giữ orchestration.
2. `_set_evidence_state` chỉ cấp ID cho tối đa `RAG_COMPOSER_MAX_DOCS` chunk hợp lệ mà composer thật sự nhận. Nội dung prompt được cắt đúng bằng `excerpt` trong evidence API; chunk nghi injection/thiếu ID/nội dung bị loại. `retrieved_docs` API không còn trả payload bị loại. Citation ID là dãy liên tục; link trả `claim_id → evidence_id → document_id/chunk_id` qua `/agent/answer`.
3. Không tự thêm “Nguồn tham khảo” vào answer thiếu citation. Mỗi câu có claim từ RAG phải dẫn ID trong context và được guard kiểm tra mức hỗ trợ bảo thủ: token overlap cho diễn giải gần nghĩa, số phải trùng, phủ định/chẩn đoán không được tự thêm. Nếu không đủ rõ, trả câu `insufficient` quyết định và không cấp citation. Đây **không phải** phép kiểm chứng entailment/y khoa hoàn chỉnh; có thể từ chối cả diễn giải đúng hoặc bỏ sót biến thể ngữ nghĩa khó.
4. Nguồn cùng chủ đề có trị số mâu thuẫn (hoặc cờ conflict rõ ràng) dẫn đến `insufficient` trước LLM. `medical_caution` được kiểm tra sau composer: nếu thiếu hành động an toàn hoặc chứa gợi ý thay đổi thuốc/tập quá mức, output bị thay bằng cảnh báo quyết định. Urgent vẫn đi deterministic fast path trước graph.
5. Context Qdrant/web được coi là dữ liệu không đáng tin: các ca giả vai system, ép bỏ cảnh báo, yêu cầu tiết lộ dữ liệu bị loại trước prompt; output guard chặn câu trả lời lặp chỉ thị. Đây là lớp lọc pattern bảo thủ, **không** là bảo đảm chống mọi prompt injection.
6. Route có call cap: retrieval tối đa 2 (env có thể chỉnh 1–3), web 1, rewrite 1, composer tối đa 2. Chỉ retry lỗi timeout/kết nối/429/502/503/504 hoặc kết quả bị cắt, trong deadline hiện có. Trace ghi action, trạng thái, mã lỗi loại exception, latency, source version nếu document mang metadata; không ghi câu hỏi/hồ sơ nguyên văn trong các event mới.

## Kiểm chứng

- Regression mới trong `backend/tests/unit/test_agent_harness_guards.py`: prompt/API context khớp, claim được/không được hỗ trợ, citation/link, số liệu sai, nguồn xung đột, injection document/web/output, medical caution, retry transient/non-transient và kết quả retrieval bị cắt.
- `backend/tests/unit` cùng `backend/tests/integration/test_api_fast_paths.py`: **76 passed, 2 deprecation warnings**. Fast-path tests mock LLM/RAG/web thành hàm gây lỗi, xác nhận urgent và BMI/tool-only không gọi chúng trong process.
- AST syntax và `git diff --check` trên file đã sửa đạt; chỉ có cảnh báo LF→CRLF của Git trên Windows.
- Chạy lại eval development 13 ca vào `backend/evals/phase1/baseline_after_phase2_development.json`: routing vẫn lỗi 2 ca và BM25 filtered vẫn 4/4 trên nhãn provisional. Đây không phải answer-level acceptance; holdout không dùng.

## Chưa đủ để qua đợt

- API HTTP runtime không kết nối tại thời điểm thực hiện; chưa deploy, chưa đo P95/call trace qua HTTP thật. Không restart khi chưa kiểm tra job import, point count, collection status và manifest.
- Claim guard hiện là heuristic fail-closed, chưa được hiệu chỉnh trên gold set có chuyên gia y khoa và chưa đo false acceptance/false rejection. Bằng chứng nguồn thiếu metadata và corpus rất mất cân đối; không tuyên bố citation precision hay clinical accuracy.
- Injection pattern không phủ mọi cách diễn đạt/encoding; cần corpus tấn công cô lập và kiểm thử red-team đa dạng hơn. `source_version` trong trace là `null` nếu document không cung cấp version; không bịa version từ cấu hình.
- Chưa có soak/load hoặc model-config-pinned end-to-end benchmark. Gate Đợt 2 chỉ được xác nhận sau các phép đo này.
