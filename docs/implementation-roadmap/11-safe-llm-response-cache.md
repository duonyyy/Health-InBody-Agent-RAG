# Cache câu trả lời RAG an toàn

**Ngày:** 2026-10-01  
**Trạng thái:** source-ready; chưa deploy và chưa xác nhận Redis/API runtime.  
**Cơ sở tham khảo:** VinAI Track 3 Day25 Reliability Agent, được điều chỉnh cho Health/InBody.

## Phạm vi đã nối

Composer có thể tái sử dụng câu trả lời của đúng một loại request: câu hỏi định nghĩa tổng quát về BMI/PBF/SMM/BFM/InBody, không có user ID, lịch sử, bộ nhớ, hồ sơ cá nhân, kết quả tool/web, lỗi, dữ liệu số hoặc dấu hiệu tự thuật/y tế; safety phải ở mức low. Cần có corpus_version để bật lookup. Các request khác tiếp tục gọi LLM theo luồng hiện tại. Chỉ bật cache với OpenAI hoặc Ollama khi model xác định được; cache tắt với custom/disabled provider và Ollama có OpenAI fallback vì adapter hiện không báo provider/model thực sự đã trả lời.

Cache là exact-match theo toàn bộ messages Composer. Không dùng semantic similarity để tránh gộp hai câu hỏi y tế chỉ vì câu chữ gần nhau. Cache key là SHA-256 trên prompt, model/provider/generation settings và fingerprint corpus; key không chứa prompt thô. Endpoint Ollama được đưa vào fingerprint dưới dạng hash. TTL mặc định 300 giây.

Cache hit vẫn đi qua output injection guard, claim/evidence checker và citation hậu kiểm. Citation links được tạo lại từ evidence của request hiện tại. Nếu cached answer không qua guard/evidence, key bị xóa. Cache miss chỉ ghi câu trả lời sau khi output guard thành công và evidence có trạng thái supported.

Cache RAM dự phòng có giới hạn 256 key theo LRU; Valkey được thử kết nối lại sau 5 giây nếu lần kết nối trước thất bại. /health chỉ xuất aggregate hit/miss/write/invalidation/error counts, không ghi câu hỏi hay hồ sơ sức khỏe.

## Cấu hình

LLM_RESPONSE_CACHE_ENABLED=true  
LLM_RESPONSE_CACHE_TTL_SECONDS=300  
CACHE_MEMORY_MAX_ENTRIES=256  
CACHE_REDIS_RETRY_SECONDS=5

Có thể tắt toàn bộ cache bằng LLM_RESPONSE_CACHE_ENABLED=false. Key có schema version health-inbody-rag-response-v1; cần nâng version khi đổi hợp đồng serialization/policy. Thay đổi prompt sẽ tự tạo key khác vì toàn bộ messages được băm.

## Kiểm thử và giới hạn bằng chứng

- Regression tests kiểm tra opaque/versioned keys, chặn request cá nhân hoặc risk, tránh cache khi provider fallback mơ hồ, tái sử dụng exact response, bypass cho personalization và xóa cached answer không có evidence hỗ trợ.
- Fast-path urgent/tool-only không đi qua RAG Composer cache; unit tests hiện có tiếp tục kiểm tra hợp đồng fast-path.
- Test cache riêng đạt **7 passed**. Unit suite hiện đạt **130 passed, 5 deselected** khi loại test BM25 snapshot vướng quyền `tmp_path` trên Windows và module OCR gateway mới có dependency `psycopg2` chưa cài trong host. Một lượt chạy không loại OCR đã dừng ở collection vì thiếu `psycopg2`; một lượt trước đó dừng test BM25 do Windows từ chối truy cập thư mục pytest temporary. Vì vậy suite đầy đủ chưa được ghi nhận là xanh hoàn toàn.
- Chưa chạy Docker/HTTP; chưa chứng minh Valkey shared hit giữa nhiều process; chưa đo hit rate, P50/P95, chi phí hay độ chính xác trên traffic/eval set thật.

## Điều chưa nên suy ra từ Day25

Day25 dùng fake provider và workload mô phỏng; kết quả 62% hit rate, latency và cost trong report không phải kết quả của dự án này. Bộ lọc privacy bằng từ khóa, n-gram similarity, cache scan Redis và cost hard-code ở bài lab không được mang sang nguyên trạng. Cache của dự án hiện exact-match và giới hạn scope, nhưng vẫn cần đo trên eval set trước khi bật trong deployment thật.

## Gate trước khi bật runtime

1. Chạy lại toàn bộ unit suite trên môi trường có pytest temp directory truy cập được.
2. Xác minh health báo Redis/Valkey và metrics hit/miss sau request HTTP lặp lại cùng corpus/model.
3. Kiểm tra Redis key không chứa query/prompt thô và TTL đúng 300 giây.
4. Chứng minh cache bypass cho user đã xác thực, history/profile/memory, số đo, safety caution/urgent, web/tool và prompt injection.
5. Đo cache on/off trên cùng eval cases và cùng model/corpus; so sánh citation precision, unsupported claims, latency và provider calls.
6. Chỉ cập nhật trạng thái deploy sau restart có kiểm soát và HTTP verification.
