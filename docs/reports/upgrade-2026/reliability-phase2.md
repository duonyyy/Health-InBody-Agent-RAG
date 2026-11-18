# Độ tin cậy evidence và claim — đợt 2

Ngày 19/11/2026. **Source/test trong process; chưa deploy**. Phạm vi gồm hai lỗ hổng theo WP 4A/4B, không khẳng định Mốc 4 hoàn tất hay đánh giá y khoa. Không sửa registry thật, corpus, model, DB, collection hoặc runtime.

## Reproduction và kết quả

Test mới dùng dữ liệu tổng hợp; [reproduction trước sửa](reliability-phase2-evidence/regression-before.log) exit 1, 4 failed/1 passed:

| Trường hợp | Trước | Sau |
|---|---|---|
| Registry rỗng, payload tự khai verified/approved | Admit sai | Từ chối, không evidence/link |
| SMM 30/BFM 20, claim đổi 20/30 | Supported sai | Không supported, không link |
| PBF nam 20/nữ 30, claim đổi 30/20 | Supported sai | Không supported, không link |
| BMI: quote định nghĩa | Supported | Supported |
| BMI: đảo định nghĩa thành “được viết tắt là” | Inconclusive | Supported trong mẫu paraphrase hẹp |

Positive review dùng registry synthetic truyền tường minh, nội dung đầy đủ và document version khớp; nội dung được xác minh trước khi cắt context, evidence chỉ chứa phần thực sự gửi composer. Kiểm tra thêm id/reviewer giả, reviewer không active/không được phép, từ chối/thu hồi/hết hạn, sai scope/hash/version, thiếu version/nội dung, metadata mâu thuẫn, privacy-only, registry lỗi và chunk không chứng minh được binding. Registry thật kiểm tra chỉ đọc: không có reviewer hay review; không suy ra corpus đã được review.

## Nguyên nhân và thay đổi

- `rag/provenance.py`: bỏ đường tắt tin stamp trong payload, phân giải qua registry do backend quản lý, hash **nội dung gốc đầy đủ** chứ không tin document hash tự khai. Kiểm tra document/review/reviewer, scope, decision, version, trạng thái reviewer, expiry/revocation và các claim mâu thuẫn. Registry lỗi hạ trạng thái và có reason. `is_verified_medical_review` chỉ nhận kết quả resolution nội bộ, không nhận dict tự khai. Policy provenance tăng version.
- `harness/layers/citation_checker.py`: xác minh trước sanitization/truncation rồi chuyển kết quả resolution nội bộ sang evidence; excerpt vẫn chỉ là context đã admit. Không có binding authoritative giữa một chunk bất kỳ và toàn văn: chunk khác toàn văn đã review bị từ chối cấp verified. Đây là fail-closed, có thể làm giảm câu trả lời medical caution đến khi có cơ chế binding đáng tin cậy.
- `harness/guards.py`: ràng buộc các số trong mệnh đề ghép với thực thể/nhóm cục bộ, đơn vị, comparator, khoảng và phủ định; trường hợp không phân tích được trả inconclusive. Kiểm tra thêm điều kiện được thêm/bớt; hỗ trợ đúng một mẫu đảo định nghĩa viết tắt. Tool BMI chỉ nhận giá trị từ trường `bmi`, không miễn kiểm tra vì một số xuất hiện ở trường khác. Policy claim tăng version; key cache hiện có dùng cả hai policy.
- Composer vẫn dùng admission thật trước provider/cache và kiểm claim trên output provider hoặc cache hit. Test stub provider, không mock guard; sai thì xóa link, trả thiếu bằng chứng và không ghi cache, cache hit sai bị loại. Test caution giả chứng minh không gọi provider và vẫn giữ safety action. Không flush cache thật.
- `test_reliability_phase2.py` bổ sung regression; `test_phase02_claim_and_provenance.py`, `test_import_data.py`, `test_greeting_safety_regression.py` cập nhật fixture version/review tổng hợp để giữ kiểm tra nhánh cũ mà không dựa stamp tự khai; integration API bổ sung urgent có dấu/không dấu với dependency bị chặn.

## Kiểm chứng và giới hạn

- Host Python 3.13.2, pytest 9.1.1, qdrant-client 1.19.1, FastAPI 0.140.0; image theo Dockerfile là Python 3.10 và requirements pin qdrant-client 1.10.1/FastAPI 0.112.2. Image và runtime Python 3.10 **NOT_RUN**. `py_compile` source sửa trên host và parse với grammar 3.10 đạt; hai kiểm tra này không thay thế chạy bằng Python 3.10.
- SQLite process-only (`DATABASE_URL=sqlite://`), guard socket của đợt 1, provider/retrieval giả ở boundary. Đây không phải PostgreSQL, Qdrant HTTP, LLM/provider thật hay browser/HTTP runtime.
- Collection toàn phạm vi exit 0: **401 collected**, 2 warnings; [log](reliability-phase2-evidence/collection-current.log). Nhóm test liên quan exit 0: **122 passed**, [log](reliability-phase2-evidence/related-current.log); API TestClient exit 0: **4 passed**, 2 warnings, [log](reliability-phase2-evidence/api-verified.log).
- Lượt unit trước khi cập nhật fixture: 380 passed/3 failed do hai fixture tự khai review và một fixture thiếu document version, không bỏ assertion. Lượt cuối sau các thay đổi: exit 0, **396 passed, 0 failed/errors/skipped/xfailed**, 2 warnings, 36,88 giây wall; [log](reliability-phase2-evidence/unit-final-current.log).
- Test fast-path public và API mock các boundary LLM, rewrite, retrieval, Qdrant, rerank, web và registry/evidence thành hàm lỗi, có ca context cá nhân. BMI/greeting regression được giữ. TestClient là in-process.
- Các trường hợp phủ định, comparator, khoảng, đổi nhóm tuổi/giới, citation sai, parent/child và truncation được kiểm tra bằng bộ synthetic; không có bộ adversarial đã được chuyên gia review. Rule-based validator **không phải semantic entailment tổng quát**: vẫn có thể false refusal hoặc bỏ sót quan hệ ngoài mẫu đã kiểm. Cần đánh giá độc lập trước khi coi WP 4B đạt gate.
- Hai tài liệu bắt buộc `docs/P0_TRUST_RAG_SAFETY_REPORT_2026-08-14.md` và `docs/P1_PERSONALIZATION_REPORT.md` không tồn tại tại đường dẫn quy định. `git diff --check` toàn worktree vẫn báo `README.md:255` dòng trắng cuối, đã có từ trước; diff các file tracked của đợt này không báo whitespace mới.

**NOT_RUN:** provider thật, corpus/review y khoa thật, DB/Qdrant HTTP, backend image, deploy và browser. Unit test không chứng minh accuracy, beta hay production readiness.
