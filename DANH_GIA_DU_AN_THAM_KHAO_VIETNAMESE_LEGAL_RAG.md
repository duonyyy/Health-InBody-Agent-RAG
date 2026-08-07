# Đánh giá dự án tham khảo Vietnamese Legal Chatbot RAG

**Ngày đánh giá:** 30/07/2026  
**Dự án tham khảo:** `Vietnamese-Legal-Chatbot-RAG-System`  
**Dự án đích:** Health/InBody Agent RAG tại thư mục gốc  
**Phạm vi:** Kiểm tra tĩnh mã nguồn, cấu hình, pipeline dữ liệu, Agent/RAG, fine-tune/serving, test, CI, monitoring và frontend.

## 1. Kết luận

Không nên merge hoặc sao chép nguyên dự án pháp lý vào hệ thống hiện tại.

Dự án tham khảo có cùng nguồn gốc kiến trúc với dự án Health/InBody, nhưng phần lõi của hệ thống hiện tại đã tiến xa hơn:

- Agent hiện tại dùng luồng multi-agent/LangGraph, có safety fast path và công cụ Health/InBody.
- LLM hiện tại đã cấu hình theo provider (`openai`, `ollama`, `custom`, `none`) thay vì khóa cứng một model.
- Import hiện tại có schema validation, dry-run, embedding theo batch, UUID ổn định và metadata Health/InBody.
- Frontend hiện tại có agent trace, health check, công cụ sức khỏe và trang kiểm tra retrieval.

Các phần có giá trị nhất từ dự án tham khảo là:

1. Ý tưởng tạo **bộ kiểm định dữ liệu bằng CLI và artifact JSON**.
2. Ý tưởng tạo **evaluation runner lưu prediction theo từng câu hỏi**.
3. Cấu trúc **pre-commit, pyproject, Makefile và CI**, nhưng phải sửa thành quality gate thật.
4. Bộ khung **Prometheus/Grafana/blackbox**, nhưng phải thiết kế lại cho đúng Docker network, bảo mật và metric ứng dụng.
5. Hợp đồng API kiểu **OpenAI-compatible** cho model tự host; chỉ lấy interface, không lấy implementation hiện tại.

Đánh giá tổng thể: dự án tham khảo hữu ích như một kho ý tưởng và tài liệu, không phải một phiên bản tốt hơn để thay thế dự án hiện tại.

## 2. Giới hạn và độ tin cậy của đánh giá

- Thư mục `.git` bên trong dự án tham khảo rỗng; lệnh Git từ đó trỏ về repository cha. Vì vậy không xác định được commit, branch hay lịch sử chính xác của mã tham khảo.
- Đây là kiểm tra tĩnh. Không chạy training H200, DigitalOcean deployment hoặc monitoring stack.
- Nhiều tuyên bố trong README/test summary không khớp với mã thực tế. Kết luận trong báo cáo ưu tiên mã và cấu hình hơn nội dung quảng bá.
- Dự án có giấy phép MIT. Nếu tái sử dụng phần mã đáng kể, phải giữ thông báo bản quyền và giấy phép theo [LICENSE](./Vietnamese-Legal-Chatbot-RAG-System/LICENSE).

## 3. So sánh nhanh

| Hạng mục | Dự án pháp lý | Health/InBody hiện tại | Kết luận |
|---|---|---|---|
| Agent | ReActAgent, tối đa 10 vòng, OpenAI khóa cứng | Multi-agent/LangGraph, deterministic tools, safety | Giữ kiến trúc hiện tại |
| LLM | `gpt-4o-mini` khóa cứng trong Agent; serving riêng khóa Llama | Provider cấu hình qua môi trường | Hiện tại tốt hơn |
| Retrieval | Hybrid BM25 + vector + rerank | Cùng nền tảng, đã điều chỉnh cho Health | Không có nâng cấp trực tiếp |
| Import Qdrant | ID theo `idx * 1000`, validation yếu | UUID ổn định, dry-run, schema và batch embedding | Hiện tại tốt hơn |
| Data QA | Có script thống kê JSONL cơ bản | Có validation lúc import, thiếu report QA độc lập đầy đủ | Nên bổ sung |
| Evaluation | Có runner sinh prediction/summary cho LLM | Có unit/integration test nhưng thiếu golden RAG benchmark | Nên bổ sung |
| Test | Nhiều test giả lập, ít gọi code thật | Ít test hơn nhưng đang kiểm tra code thật | Không chép test; mở rộng theo cách hiện tại |
| CI | Có workflow nhưng lỗi thường bị bỏ qua | Chưa có quality gate chuẩn | Lấy cấu trúc, viết lại |
| Monitoring | Có Prometheus/Grafana/blackbox cơ bản | Chưa có observability đầy đủ | Lấy ý tưởng, viết lại |
| Frontend | UI pháp lý, “streaming” giả lập | UI Health có trace, tools và retrieval view | Giữ frontend hiện tại |
| Fine-tune | Llama 3.1 8B tối ưu H200 141 GB | Máy đích GTX 3050, cần model-agnostic | Không áp dụng lúc này |

## 4. Những phần nên áp dụng

### 4.1. Data audit CLI và báo cáo dữ liệu

File tham khảo [analyze_data.py](./Vietnamese-Legal-Chatbot-RAG-System/llm_finetuning_serving/data_processing/analyze_data.py) có cách làm tốt ở mức nền tảng:

- Đọc JSONL theo dòng.
- Đếm JSON lỗi và field thiếu.
- Thống kê min/max/trung bình độ dài.
- Lưu kết quả thành artifact JSON có thể so sánh giữa các lần chạy.

Không nên chép nguyên file vì schema đang là `instruction/input/output`. Nên viết phiên bản Health/InBody cho `doc_id`, `title`, `content`, `content_type`, `source`, `language` và metadata.

Phiên bản của chúng ta cần bổ sung:

- Trùng lặp chính xác và gần trùng lặp.
- Phân phối theo nguồn, loại nội dung và ngôn ngữ.
- Tỷ lệ nội dung quá ngắn/quá dài.
- Kiểm tra PII và dữ liệu y tế nhạy cảm.
- Kiểm tra đơn vị, giá trị sinh lý bất hợp lý và mâu thuẫn.
- Hash/manifest của corpus, embedding model, chunking config và thời gian import.
- Báo lỗi đủ để sửa dữ liệu, không chỉ đếm lỗi.

**Mức ưu tiên:** P0/P1, nên làm ngay sau khi đợt import Qdrant hiện tại kết thúc và được xác minh.

### 4.2. Evaluation runner có artifact theo từng mẫu

File [evaluate_model.py](./Vietnamese-Legal-Chatbot-RAG-System/llm_finetuning_serving/evaluation/evaluate_model.py) có một ý tưởng tốt: mỗi lần đánh giá lưu cả `prediction`, `reference` và `summary`. Cách này giúp truy ngược lỗi thay vì chỉ nhìn một điểm trung bình.

Không nên dùng các metric hiện tại làm thước đo chính:

- Token overlap, BLEU và ROUGE đo giống câu chữ, không chứng minh câu trả lời đúng.
- Không đo retrieval recall, groundedness, citation, hallucination hay medical safety.
- Prompt khóa cứng template Llama và vai trò chuyên gia pháp luật.

Nên xây bộ benchmark Health/InBody gồm:

- `route_accuracy`: Agent chọn đúng nhánh.
- `tool_selection_accuracy`: gọi đúng tool và đúng tham số.
- `retrieval_recall@k`, `MRR`, `nDCG`.
- `context_precision`: bao nhiêu chunk lấy về thực sự liên quan.
- `answer_correctness`: đối chiếu đáp án chuẩn/rubric.
- `faithfulness/groundedness`: phát biểu có được nguồn hỗ trợ hay không.
- `citation_accuracy`: nguồn có thật và có hỗ trợ kết luận hay không.
- `safety_recall`: phát hiện đúng ca cấp cứu/chống chỉ định.
- `p50/p95 latency`, time-to-first-token và số lần gọi LLM.
- Chi phí hoặc số token theo từng provider/model.

Artifact mỗi lần chạy nên chứa:

- Phiên bản dataset, Git commit và cấu hình runtime.
- Provider/model thực tế, embedding model và reranker.
- Trace Agent, tài liệu retrieval, câu trả lời và lỗi.
- Kết quả theo từng nhóm `inbody_metric`, `nutrition`, `exercise`, `medical_safety`, `general_health`.

**Mức ưu tiên:** P0. Đây là phần có giá trị nhất để chứng minh dự án “đạt chuẩn Agent RAG”.

### 4.3. Quality tooling: pyproject và pre-commit

[pyproject.toml](./Vietnamese-Legal-Chatbot-RAG-System/pyproject.toml) và [.pre-commit-config.yaml](./Vietnamese-Legal-Chatbot-RAG-System/.pre-commit-config.yaml) cung cấp cấu trúc hợp lý:

- Black/isort cho định dạng.
- Flake8 cho lint.
- Mypy cho type check.
- Bandit cho kiểm tra bảo mật.
- Hook kiểm tra YAML, JSON, merge conflict, file quá lớn và debug statement.

Nên áp dụng cấu trúc này nhưng cần:

- Chọn một nguồn cấu hình duy nhất, tránh tách cấu hình trùng nhau.
- Không bỏ qua toàn bộ import thiếu trong mypy nếu module là phần lõi.
- Chỉ chạy Bandit trên file thay đổi hoặc cấu hình hook đúng cách; không ghi đè một report chung ở mỗi file.
- Thêm Ruff nếu muốn thay thế Flake8/isort bằng công cụ nhanh hơn.
- Không tự động sửa các file đang liên quan tới import Qdrant đang chạy.

**Mức ưu tiên:** P1.

### 4.4. Monitoring và dashboard

Thư mục [monitoring](./Vietnamese-Legal-Chatbot-RAG-System/monitoring) là bộ khung tham khảo tốt về mặt thành phần:

- Prometheus.
- Grafana provisioning.
- Node Exporter/cAdvisor.
- Blackbox exporter.
- Alert rules.

Tuy nhiên không được chạy nguyên cấu hình vì:

- Mật khẩu Grafana `admin123` bị khóa cứng trong [docker-compose.yml](./Vietnamese-Legal-Chatbot-RAG-System/monitoring/docker-compose.yml).
- Target dùng IP `172.17.0.1`, phụ thuộc môi trường Linux và không ổn định trên Docker Desktop/Windows.
- Alert blackbox kiểm tra `up` thay vì `probe_success`; Prometheus vẫn có thể scrape exporter thành công khi backend đích đã chết.
- Dashboard chủ yếu đo hạ tầng, chưa có metric của pipeline Agent/RAG.
- cAdvisor mount các đường dẫn root của Linux, không phù hợp trực tiếp với máy Windows hiện tại.

Monitoring của hệ thống Health/InBody nên có metric ứng dụng:

- Tổng request, error rate và latency theo endpoint.
- Latency theo từng Agent node.
- Số lần gọi LLM, timeout, fallback và provider/model.
- Latency embedding, Qdrant search, BM25 và rerank.
- Số chunk trả về, score distribution và empty-retrieval rate.
- Safety escalation count.
- Celery queue depth và thời gian xử lý task.
- Qdrant point count, collection state và chênh lệch với manifest import.
- GPU VRAM/utilization của embedding hoặc LLM service.

**Mức ưu tiên:** P1/P2.

### 4.5. Hợp đồng API cho model tự host

[serve_model.py](./Vietnamese-Legal-Chatbot-RAG-System/llm_finetuning_serving/serving/serve_model.py) có ý tưởng hữu ích là cung cấp:

- `/health`
- `/v1/chat/completions`
- danh sách model
- cấu trúc request/response gần OpenAI API

Hợp đồng API chuẩn giúp backend thay model mà không thay Agent/RAG. Đây phù hợp yêu cầu không hard-code LLM.

Chỉ nên lấy **interface**, không lấy implementation:

- Model ID `vietnamese-legal-llama` bị khóa cứng.
- Prompt khóa cứng Llama/pháp luật.
- Endpoint “stream” đợi `model.generate()` chạy xong rồi mới chia câu trả lời thành từng từ; đây không phải streaming thật và không cải thiện time-to-first-token.
- Inference đồng bộ nằm trong route async, có thể chặn event loop.

Backend hiện tại đã có lớp chọn provider trong [brain.py](./backend/src/brain.py). Bước tiếp theo đúng là chuẩn hóa một adapter chung, ví dụ:

```text
LLMProvider.chat(messages, model, temperature, max_tokens, timeout)
LLMProvider.stream(...)
LLMProvider.health()
LLMProvider.describe()
```

Model phải là cấu hình runtime và được ghi vào trace/metrics, không nằm cố định trong Agent.

**Mức ưu tiên:** P1/P2.

## 5. Những phần không nên áp dụng trực tiếp

### 5.1. ReAct Agent pháp lý

[agent.py](./Vietnamese-Legal-Chatbot-RAG-System/backend/src/agent.py) dùng `ReActAgent`, OpenAI `gpt-4o-mini` khóa cứng và cho phép tối đa 10 vòng.

Điểm yếu:

- Không model-agnostic.
- Độ trễ và chi phí khó dự đoán.
- Tool web search trong miền sức khỏe làm tăng rủi ro nguồn không kiểm soát.
- Không có state/trace/safety flow rõ như LangGraph hiện tại.
- Các tool pháp lý không có giá trị cho Health/InBody.

Chỉ giữ nguyên lý “dùng deterministic tool cho phép tính”, vì dự án hiện tại đã triển khai nguyên lý đó tốt hơn.

### 5.2. Import Qdrant cũ

[import_data.py](./Vietnamese-Legal-Chatbot-RAG-System/backend/src/import_data.py) tạo point ID bằng `idx * 1000 + chunk_idx`, metadata ít và validation yếu.

Không nên thay importer hiện tại bằng file này. Importer Health/InBody hiện tại đã có:

- Dry-run.
- Validate schema.
- Embedding theo batch.
- UUID ổn định theo document/chunk.
- Payload giàu metadata.
- Báo cáo processed/skipped/error.

Cả hai phiên bản vẫn thiếu checkpoint/resume và chiến lược collection version/alias hoàn chỉnh. Đây là phần cần xây mới, không có sẵn trong dự án tham khảo.

### 5.3. Bộ test và CI “xanh giả”

[ci.yml](./Vietnamese-Legal-Chatbot-RAG-System/.github/workflows/ci.yml) dùng `|| echo` sau Black, Flake8, pytest và Bandit, nên lỗi không làm job thất bại. CI chỉ chạy `test_basic.py`, trong đó có các assert như `1 + 1 == 2`, không kiểm tra hệ thống RAG.

[run_working_tests.sh](./Vietnamese-Legal-Chatbot-RAG-System/scripts/run_working_tests.sh) còn đo coverage của thư mục `tests`, trái với `pytest.ini` yêu cầu coverage `backend/src`. Nhiều test tự định nghĩa logic giả lập bên trong test thay vì import logic thật của dự án.

Vì vậy:

- Có thể lấy tên job và bố cục workflow.
- Không lấy nguyên test hay điều kiện bỏ qua lỗi.
- CI mới phải thất bại khi unit/integration test, lint hoặc security gate thất bại.
- Coverage chỉ có ý nghĩa khi đo mã production.

### 5.4. Fine-tune Llama 3.1 8B trên H200

Pipeline [llm_finetuning_serving](./Vietnamese-Legal-Chatbot-RAG-System/llm_finetuning_serving) khóa vào Llama 3.1 8B, Unsloth, DigitalOcean Spaces và H200 141 GB. Cấu hình còn dự kiến dùng khoảng 80–120 GB VRAM.

Máy GTX 3050 của dự án không thể chạy cấu hình này. Việc fine-tune lúc này cũng chưa giải quyết các vấn đề quan trọng hơn:

- Corpus có đủ sạch và không trùng lặp hay chưa.
- Retrieval có lấy đúng nguồn không.
- Answer có grounded và an toàn không.
- Agent có route đúng và gọi đúng tool không.

Chỉ cân nhắc fine-tune sau khi benchmark chứng minh lỗi nằm ở khả năng của model, không phải dữ liệu/retrieval/prompt/tool. Nếu cần thử nghiệm trên GTX 3050, nên dùng model nhỏ hơn và QLoRA/4-bit với context/batch thấp, nhưng đây là nhánh nghiên cứu riêng, không phải bước nâng cấp RAG trước mắt.

### 5.5. Chia dữ liệu ngẫu nhiên

[split_data.py](./Vietnamese-Legal-Chatbot-RAG-System/llm_finetuning_serving/data_processing/split_data.py) có seed cố định, nhưng chỉ shuffle từng record rồi chia 80/10/10.

Với dữ liệu tổng hợp hoặc dữ liệu có nhiều đoạn từ cùng tài liệu, cách này gây rò rỉ near-duplicate giữa train/validation/test và làm điểm đánh giá cao giả tạo. Nên group split theo `source_document_id`, nguồn hoặc content hash; test set phải được đóng băng và không đi qua pipeline sinh dữ liệu huấn luyện.

### 5.6. Frontend và “streaming” giả

Frontend tham khảo có lịch sử, export và nhóm câu hỏi mẫu, nhưng frontend hiện tại đã có các chức năng tương đương cùng agent trace, Health tools và retrieval view.

Serving tham khảo chỉ chia câu trả lời hoàn chỉnh thành các từ sau khi generation đã xong. Không nên dùng cách này để báo rằng hệ thống có streaming.

## 6. Khoảng trống dự án tham khảo không giải quyết

Đây là những sự thật dễ bị bỏ sót nếu chỉ đọc README:

- Nhiều file và tài liệu không đồng nghĩa với độ chính xác cao.
- Có Prometheus/Grafana không đồng nghĩa với có observability Agent/RAG.
- Có nhiều test không đồng nghĩa với test code production.
- Có endpoint tên “stream” không đồng nghĩa với streaming thật.
- Fine-tune model không sửa được retrieval sai hoặc dữ liệu bẩn.
- Một Agent có nhiều tool không tự động trở thành Agent RAG tốt.
- Dữ liệu pháp lý và y tế có rủi ro khác nhau; prompt, metric và safety policy không thể đổi tên rồi tái sử dụng.

Dự án tham khảo không cung cấp sẵn:

- Golden dataset Health/InBody.
- Đánh giá retrieval end-to-end.
- Citation/groundedness verification.
- Medical safety benchmark.
- Qdrant collection versioning, alias swap và rollback.
- Import checkpoint/resume đáng tin cậy.
- Model registry/provider adapter hoàn chỉnh.
- Production-grade real streaming và concurrency control.

## 7. Kế hoạch áp dụng đề xuất

### Giai đoạn 0 — Bảo vệ trạng thái hiện tại

Không thay đổi embedding model, vector dimension, chunking hoặc collection khi import hiện tại còn chạy.

Hoàn tất:

- Chờ import kết thúc.
- So sánh point count Qdrant với `total_chunks`.
- Lưu collection info, vector size, distance metric và payload sample.
- Chạy một tập truy vấn smoke test.
- Ghi manifest import để làm baseline.

**Tiêu chí hoàn thành:** có thể chứng minh collection chứa đúng corpus và truy vấn được trước khi nâng cấp tiếp.

### Giai đoạn 1 — Golden benchmark Agent RAG

Tạo bộ câu hỏi có nhãn cho từng nhóm:

- InBody calculation.
- Nutrition.
- Exercise.
- Medical safety/urgent.
- General health.
- Multi-turn và câu hỏi thiếu dữ kiện.
- Câu hỏi ngoài phạm vi.

Viết evaluation runner độc lập với model, lưu JSON/JSONL artifact và tính route/tool/retrieval/answer/safety/latency.

**Tiêu chí hoàn thành:** mọi thay đổi về model, prompt, retrieval hoặc Agent đều có thể so sánh với baseline.

### Giai đoạn 2 — Data quality và versioning

Viết `data audit` CLI dựa trên ý tưởng của `analyze_data.py`, thêm dedup, provenance, PII, thống kê domain và manifest.

Thiết kế collection theo phiên bản:

```text
nmk_chatbot_collection_vYYYYMMDD_hash
                   |
                   +-- alias: nmk_chatbot_collection
```

Import vào collection mới, kiểm tra, sau đó mới đổi alias. Giữ collection cũ trong thời gian rollback.

**Tiêu chí hoàn thành:** import lặp lại cho cùng point ID, có resume/checkpoint, có manifest và rollback.

### Giai đoạn 3 — Observability

Thêm `/metrics`, request ID và trace ID xuyên suốt API → Agent → retrieval → LLM. Sau đó mới dựng Prometheus/Grafana đã sửa.

**Tiêu chí hoàn thành:** dashboard trả lời được request chậm ở Agent node nào, provider/model nào, retrieval hay LLM.

### Giai đoạn 4 — Quality gates

Thêm pyproject/pre-commit và CI:

- Unit test thật.
- Integration test với dependency giả hoặc test container.
- Golden RAG evaluation ở tập smoke nhỏ.
- Lint/type/security gate không nuốt lỗi.
- Docker build.

**Tiêu chí hoàn thành:** PR không thể merge khi gate bắt buộc thất bại; coverage đo `backend/src`.

### Giai đoạn 5 — Chuẩn hóa LLM provider và streaming

Tách interface provider khỏi Agent, model chọn bằng config/runtime. Bổ sung health/model metadata và streaming thật nếu UX cần.

**Tiêu chí hoàn thành:** đổi Ollama/OpenAI/custom server mà không sửa graph, prompt domain hoặc tool logic; trace luôn ghi provider/model thực tế.

### Giai đoạn 6 — Chỉ cân nhắc fine-tune khi có bằng chứng

So sánh ít nhất:

- Model hiện tại + RAG.
- Model khác + cùng RAG.
- Prompt cải tiến + cùng model.
- Fine-tuned model + cùng benchmark.

Chỉ triển khai fine-tune nếu cải thiện correctness/safety có ý nghĩa và không làm latency/tài nguyên vượt ngân sách.

## 8. Thứ tự ưu tiên cuối cùng

| Ưu tiên | Hạng mục | Hành động |
|---|---|---|
| 1 | Golden Agent/RAG benchmark | Xây mới, lấy ý tưởng artifact từ evaluation runner |
| 2 | Data audit + corpus manifest | Chuyển thể `analyze_data.py` cho Health/InBody |
| 3 | Qdrant version/alias/resume | Xây mới; dự án tham khảo không có |
| 4 | App metrics + tracing | Xây trước, rồi mới áp dụng Prometheus/Grafana |
| 5 | CI/pre-commit thật | Lấy cấu trúc, bỏ toàn bộ cơ chế nuốt lỗi |
| 6 | LLM provider contract | Mở rộng `brain.py`, không khóa model |
| 7 | Real streaming | Chỉ làm nếu benchmark UX cho thấy cần |
| 8 | Fine-tune | Hoãn đến khi benchmark chứng minh cần |

## 9. Quyết định đề xuất

Nên áp dụng có chọn lọc bốn nhóm ý tưởng:

1. Data audit có artifact.
2. Evaluation có prediction-level artifact.
3. Tooling/CI theo quality gate thật.
4. Monitoring theo metric Agent/RAG và provider/model.

Không nên áp dụng trực tiếp:

1. ReAct Agent pháp lý.
2. Importer Qdrant cũ.
3. Bộ test/CI hiện tại của dự án tham khảo.
4. Fine-tune Llama/H200.
5. Frontend pháp lý.
6. “Streaming” mô phỏng.

Bước triển khai hợp lý nhất tiếp theo là hoàn tất và xác minh import Qdrant đang chạy, sau đó xây **golden benchmark + data audit**. Hai phần này tạo bằng chứng để quyết định mọi thay đổi tiếp theo, bao gồm đổi LLM, tuning retrieval hay fine-tune.
