# Chuyển cấu hình embedding sang multilingual E5 small — 2026-11-18

## Cập nhật tên collection

Collection staging mới là `health_knowledge_e5_v1`. Do Qdrant không đổi tên physical collection trực tiếp, đã sao chép có lease và write receipt từ `nmk_chatbot_e5small_v20261118`, giữ bản cũ. Đã đối chiếu toàn bộ 3.846 vector (sai lệch tối đa 0), payload giống hệt, số lượng/fingerprint và các payload index đạt. BM25 và release manifest tương ứng nằm trong `backend/artifacts/health_knowledge_e5_v1/`; thử E5 → Qdrant và tải BM25 thành công. Alias phục vụ vẫn trống, collection mới vẫn là staging, chưa deploy ứng dụng hoặc đạt quality gate.

## Cập nhật tiếp theo: đồng bộ BM25 và sửa kiểm tra release

Đã tạo `backend/artifacts/e5small-2026-11-18-v1/bm25_snapshot.json.gz` bằng cách scroll đầy đủ Qdrant staging. Snapshot chứa 3.846 chunk/1.008 tài liệu, fingerprint trùng Qdrant và manifest; SHA-256 đã được ghi trong release manifest. Snapshot đã tải trong process để thử BM25; với filter `medical_safety`, câu đau ngực/khó thở trả các tài liệu an toàn. Đây không phải kiểm thử HTTP của ứng dụng hay benchmark chất lượng.

Đã sửa `verify_runtime_release_sync` để trạng thái `unverified`/`uninitialized` không còn bị xem là đồng bộ, và đối chiếu SHA-256 snapshot khi có release manifest. Chưa deploy; alias vẫn trống. Bộ test đầy đủ còn bị chặn khi thu thập bởi các file đã xóa trong working tree: `core/observability.py`, `pipelines/import_missing_vectors.py`, `pipelines/reuse_qdrant_vectors.py`, `scripts/evaluate_phase1.py` và các fixture eval liên quan. Không tự phục hồi các file đã bị xóa. Chưa có đánh giá đạt quality gate trên corpus E5, chưa có review y khoa xác minh và chưa chạy HTTP ứng dụng với release mới.

## Cập nhật runtime: đã tạo staging corpus E5

Qdrant local hiện có collection `nmk_chatbot_e5small_v20261118`, corpus version `e5small-2026-11-18-v1`, Cosine 384 chiều. Import hoàn tất với 1.008 tài liệu và 3.846 point; lệnh verify độc lập scroll đủ 3.846 point, không trùng chunk ID và xác nhận fingerprint khớp release manifest. Manifest và bản nguồn đã lọc nằm tại `backend/artifacts/e5small-2026-11-18-v1/`. Một slide kết thúc có thông tin liên hệ bị loại khỏi bản nhập; dữ liệu gốc không thay đổi.

Model revision `62ff60abe92eb88c1b297fabaad28f7ac77b5875`, prefix `passage: ` khi import và `query: ` khi thử tìm kiếm. Runtime embedding dùng CPU/float32, encode batch 2, request batch tối đa 8; không sử dụng CUDA nên không có số đo VRAM peak. Môi trường local thiếu `langchain.text_splitter`, nên import dùng fallback splitter; không so sánh benchmark với corpus chunk bằng splitter khác. Job ban đầu bị timeout sau 463 point; đã dừng, khởi động lại service, đối chiếu fingerprint và resume: 463 point cũ cộng 3.383 point mới, receipt committed, 0 lỗi cuối và 0 conflict.

Ba truy vấn trực tiếp E5 → Qdrant trả kết quả: BMI và protein có tài liệu liên quan ở top đầu, nhưng truy vấn đau ngực/khó thở trả ba tài liệu exercise ở top 3 khi tìm dense thuần. Đây chỉ là smoke test, không phải đánh giá chất lượng hoặc thử fast-path an toàn của ứng dụng. Nguồn gồm 952 provisional và 56 unverified legacy; không có tài liệu được registry xác minh medical review.

**Chưa phát hành:** alias vẫn trống, BM25 snapshot phù hợp chưa được tạo và backend chưa chạy retrieval với corpus này. Evaluation bị thiếu `backend/scripts/evaluate_phase1.py` và dữ liệu test tương ứng trong working tree. Không kích hoạt alias chỉ dựa trên trạng thái green và số point; cần hoàn tất đồng bộ BM25 và các quality gate của release.

## Ghi chép trước khi import

Trạng thái: **source-ready một phần, chưa deploy và chưa phát hành corpus**. Model đã tải tại `infra/embed_serving/models/multilingual-e5-small`, revision `62ff60abe92eb88c1b297fabaad28f7ac77b5875`; thử inference CPU float32 với hai câu tổng hợp tạo vector 384 chiều. Đây không phải benchmark chất lượng hoặc E2E. BGE-M3 vẫn còn trên đĩa: lần xóa theo yêu cầu bị hệ thống kiểm duyệt tự động chặn.

Backend dùng `EMBEDDING_QUERY_PREFIX` cho query và `EMBEDDING_PASSAGE_PREFIX` cho document; pipeline dùng passage prefix. Khi prefix được cấu hình, hai giá trị tham gia embedding fingerprint, tránh resume/reuse giữa các cấu hình khác. Khi cả hai để trống giữ fingerprint cũ. Giá trị mẫu trong `backend/.env.example` là model E5, 384 chiều, các prefix tương ứng; template serving và default infra Compose trỏ thư mục model E5. Backend code không hard-code tên model.

Không sửa `.env` riêng hoặc triển khai container; `env_file`/biến môi trường hiện hữu vẫn có thể ghi đè defaults. Không chuyển alias, không ghi corpus cũ. Trước khi dùng retrieval phải tạo collection staging mới 384 chiều, re-embed toàn bộ với `passage: `, dùng `query: ` khi tìm, gắn đúng ID/revision/prefix vào fingerprint, tạo release BM25/manifest đồng bộ và đánh giá cùng corpus. Không tái dùng vector BGE-M3. Chỉ phát hành sau khi xác minh chất lượng và topology; ảnh hưởng corpus không thể đánh giá từ inference hai câu.

Kiểm tra: backend 20 test (input role + deadline) đạt; pipeline 13 test đạt. Bộ phase04 không thu thập được vì `backend/scripts/evaluate_phase1.py` đã bị xóa khỏi working tree trong lúc làm việc; giữ nguyên trạng thái đó. Không kết luận runtime PostgreSQL, Qdrant, model serving HTTP hoặc browser đã dùng model mới.

## Khôi phục embedding serving

Theo yêu cầu, khôi phục `infra/embed_serving/` từ Git, tải lại model E5 và tạo `.env.serving` mới từ template do cấu hình local cũ đã bị xóa cùng thư mục. BGE-M3 không còn ở đường dẫn `infra/embed_serving/models/bge-m3` sau lần xóa thư mục trước đó; không suy ra các bản sao khác đã bị xóa. Template, Dockerfiles và script tải mặc định chọn E5; Compose `config --quiet` đạt. Chạy service Flask cô lập trên CPU: `/health` healthy và `/embed` trả 2 vector 384 chiều; service thử đã dừng. Test deployment và input roles: 14 passed. Chưa deploy container, tạo corpus hoặc nghiệm thu retrieval.
