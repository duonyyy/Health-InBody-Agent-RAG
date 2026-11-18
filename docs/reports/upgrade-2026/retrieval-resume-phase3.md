# Retrieval và resume — đợt 3 (19/11/2026)

**Trạng thái: source-ready trong phạm vi đợt 3, chưa deploy.** Toàn suite cô lập cuối đạt 478/478, không fail/skip; xem `retrieval-resume-phase3-evidence/acceptance-final.log`. Không gọi dịch vụ/corpus thật, đổi alias, restart, stage, commit hoặc push. Baseline: main, HEAD 03dd08302060146172cfe4567d82fba6be59bbc3; worktree sạch ở đầu đợt 3, lượt tiếp tục giữ toàn bộ diff trước đó. Hai báo cáo P0/P1 trong AGENTS.md không tồn tại tại đường dẫn chỉ định.

## Source và contract

1. **Query gốc:** `agents/nodes/rag.py` thực thi search gốc trước rewrite. `rag/search.py` bỏ expansion ngầm ở dense và BM25, giữ prefix query/passage của adapter. max_queries=1 không rewrite; rewrite rỗng hoặc trùng không tạo search trùng. Composer reserve, cancellation/deadline và call budget hiện có vẫn áp dụng. Celery task `bot_rag_answer_message` dùng graph hiện có, giữ return type chuỗi, thay cho pipeline rewrite trước search và thiếu safety/budget. Helper multi-query Celery dùng chung release context và canonical dedup.
2. **Empty/error:** `_get_embedding`, `vector_search_fallback` và strict `search_vector` phân biệt lỗi với zero hit bằng `RetrievalDependencyError` hoặc `BudgetExhaustedError`. Vector thiếu, sai shape/chiều, NaN/Inf bị chặn. Production dùng dimension cấu hình, client Qdrant local tường minh dùng dimension collection local. `search_vector` giữ mặc định compatibility cho caller ngoài đường strict. Đường hybrid dùng strict; không tự fallback BM25 khi dense lỗi. Chính sách từ chối cả lượt tránh coi một nhánh lỗi + nhánh rỗng là healthy empty.
3. **Consumer:** node ghi `retrieval_status` và errors; graph/API agent giữ degraded. Composer phân biệt không tìm thấy với chưa thể tìm do lỗi. `/search` trả 503 cho dependency, 504 cho budget/timeout và 503 cho release mismatch; empty thành công trả 200/results=[]. Fallback release theo cấu hình cũ có mode single-branch và node đánh dấu degraded; không gọi là hybrid. Error/log mới không chứa raw query hoặc provider detail.
4. **Dedup/provenance:** dùng khóa canonical document/chunk ở fusion, node và Celery helper; fallback theo content hash, không title. Cùng identity nhưng khác hash/release bị từ chối. Node/Celery sao chép object trước khi gắn retrieval_query. Parent được scope theo document + parent ID, có matched_children và child_chunk_id/child_content; hash parent tính từ parent text, không giữ hash child cho parent. Citation checker hiện có vẫn cấp parent_section, không chuyển citation sang sibling chưa admit.
5. **Release giữa subquery:** mutable request_context chỉ sống trong một request, ghi tuple physical collection/release/corpus version/chunk-set fingerprint/nhánh được phép, kể cả zero hit. Query sau kiểm lại sync; nếu tuple đổi, từ chối trước retrieval, giữ kết quả trước cùng lỗi degraded. Node và helper Celery dùng chung context. Không tự tiếp tục trên release mới. Physical pin trong từng subquery giữ cơ chế cũ.
6. **Resume:** kiểm đủ identity/content_hash/corpus_version/embedding_fingerprint ở hai phía; fingerprint/hash phải đúng dạng SHA256. Reader Qdrant không tự điền document/chunk identity bị thiếu. Checkpoint cần resume_signature đầy đủ, đúng schema và khớp collection/source SHA/chunking/embedding/splitter. Không legacy fallback. Import thật từ start_line>1 bị chặn vì line checkpoint hiện không chứng minh không có dòng/chunk bị bỏ sót; resume bằng quét từ dòng 1 + skip_existing_points. Dry-run start_line giữ compatibility. Không thêm force/ignore flag, không migration manifest cũ bằng cấu hình hiện tại.

Không đổi model/provider/dimension/ranking weights, bật reranker hoặc phục hồi script bị xóa.

## Bằng chứng trước và sau

| Ca | Trước sửa | Sau sửa / bằng chứng |
|---|---|---|
| Thiếu metadata/signature | 9 fail/2 pass ở regression đầu | từ chối missing/blank ở hai phía; thêm malformed hash/fingerprint/version |
| Search gốc trước rewrite và raw boundary | 2 fail | spy search(raw) → rewrite(raw) → search bổ sung; không expansion ngầm |
| Chunk ID cục bộ trùng ở hai document, cùng identity khác nội dung | 2 fail | giữ chunk khác nhau và từ chối conflict |
| Pin xuyên query, kể cả raw empty | không có request context; test đỏ TypeError | alias đổi v1→v2 bị chặn, spy chỉ ghi retrieval v1 |
| Vector sai chiều | bị báo qdrant_unavailable | invalid_embedding trước Qdrant |
| API empty/embedding/dimension/timeout/Qdrant | chưa có matrix HTTP cô lập | lần lượt 200/503/503/504/503, không lộ detail giả lập |
| Resume giống input/config | lifecycle test hiện hữu | 0 embed/upsert mới |
| Xóa một point local rồi resume | chưa có test importer local | embed=1/upsert=1, skip=1 |
| Point thiếu fingerprint ngay đầu input | từng bị match | conflict, embed=0/upsert=0/committed=0 |
| Thiếu/đổi 8 trường signature | thiếu một số trường vẫn qua | 16 ca importer thật chặn trước embed/upsert |
| Batch thứ hai lỗi | cần kiểm chứng receipt | committed=1/failed=1/partial=true/checkpoint=1; chạy resume tiếp được chứng minh lease đã được release |
| Conflict sau batch đã commit | chưa có matrix local | committed=1/conflict=1/partial=true/checkpoint=1; không tuyên bố transaction toàn job |
| Parent cùng ID ở hai document | có thể gộp | hai parent riêng, giữ danh sách child khớp và object gốc |
| Urgent ở Celery task cũ | pipeline riêng | task dùng graph; dependency được mock thành hàm gây lỗi nhưng urgent vẫn trả đúng |

Các test mới tại `backend/tests/unit/test_phase3_*`, `backend/tests/integration/test_phase3_resume_matrix.py`, `test_phase3_search_api.py` và bổ sung lifecycle local. Không mock importer/search/endpoint chính trong matrix integration; chỉ stub embedding, transport, auth/rate-limit và fault injection. TestClient là HTTP trong process, không phải HTTP runtime deployment.

## Lệnh và kết quả

Host: Python 3.13.2 tại C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe, pytest 9.1.1, qdrant-client 1.19.1, httpx 0.28.1. Backend image khai báo Python 3.10 và qdrant-client 1.10.1: chưa thực thi image.

Thiết lập: PYTHONPATH=backend/src; PYTHONDONTWRITEBYTECODE=1; DATABASE_URL=sqlite://. Chạy `isolated_pytest.py` với socket connect bị chặn; socketpair loopback do wrapper tự tạo riêng cho event loop Windows. Mọi pytest basetemp trong workspace; Qdrant `:memory:` và dữ liệu tổng hợp trong tmp_path.

- `backend/tests/unit backend/tests/integration --collect-only -q -p no:cacheprovider`: 478 collected, exit 0; `acceptance-collection.log`.
- Toàn unit + integration cuối: **478 passed, 0 failed, 0 skipped, exit 0**, 39.39 giây; `acceptance-final.log`.
- Toàn unit + integration trước bổ sung regression blank/duplicate cuối: 452 passed, exit 0; `acceptance-all.log`.
- Regression missing/blank + query/parent/legacy task: 49 passed, exit 0; `acceptance-regression.log` (trước 3 ca malformed cuối).
- Matrix import + API đầu: 15 passed, exit 0; `matrix-followup.log` (sau đó mở rộng checkpoint changed và partial conflict).
- 17 file Python thay đổi: compile + ast.parse(feature_version=(3,10)) đạt. Đây là syntax, không phải chạy Python 3.10. `git diff --check` đạt.

Logs trong `retrieval-resume-phase3-evidence/`. Giữ các log wrapper/fixture lỗi: ban đầu wrapper thiếu root sys.path, rồi chặn cả socketpair Windows; fixture matrix ban đầu thiếu domain. Các lỗi này đã được sửa, không phải lỗi sản phẩm. Lệnh cuối chạy toàn bộ suite với `-q -p no:cacheprovider --basetemp .phase3-matrix-tmp`, không skip/ignore test để báo pass.

## Giới hạn

NOT_RUN: Python 3.10/image, runtime HTTP, service thật, corpus thật, benchmark và đánh giá y khoa. Không suy accuracy/relevance từ regression pass. Regression xác minh các kịch bản tổng hợp nêu trên, không phải chứng minh mọi concurrency schedule hoặc entailment/citation y khoa. Các gate triển khai và chất lượng corpus trong kế hoạch vẫn mở.

Các thư mục tạm pytest trong workspace còn được giữ: lần dọn trước bị hệ thống kiểm duyệt tự động chặn với lý do `blocked by policy`; không thử xóa bằng đường khác.

Log pytest được chuẩn hóa khoảng trắng cuối dòng trước khi đưa vào Git; giữ nguyên kết quả và exit code.
