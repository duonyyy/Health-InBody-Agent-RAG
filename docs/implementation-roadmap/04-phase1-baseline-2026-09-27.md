# Benchmark Report — Phase 1 / 2026-09-27

## Phạm vi và cách chạy

- Commit/version: working tree đang có thay đổi của người dùng; evaluator suite `1.0.0`. Không commit, deploy hoặc restart.
- Corpus/index version: snapshot BM25 `2026-07-30-v2`, collection `nmk_chatbot_active`, 23.608 dòng; SHA-256 ghi trong `backend/evals/phase1/baseline_development_v1.json`.
- Embedding/reranker/LLM config: **không dùng** trong phép đo này. `current_bm25_filtered` là hàm `rag.search.bm25_search` hiện tại, không phải toàn bộ hybrid/Agent đang phục vụ.
- Hardware/load condition: Windows local, một process Python, snapshot offline, không tải đồng thời. `http://localhost:8000/health` không kết nối được tại thời điểm đo.
- Fixture: `backend/evals/phase1/cases_v1.jsonl`; mặc định chỉ chạy `development`. `holdout` 7 ca chưa chạy/chưa dùng để chỉnh.
- Lệnh lặp lại: `python -B backend/scripts/evaluate_phase1.py --output backend/evals/phase1/baseline_development_v1.json`.
- Hai lần chạy độc lập cho cùng SHA-256 output `370E2381BF6BF519F1E53E9ADB2D8598EDC5867E0CBE1288916EF8A23E0A7550`. Script ghi SHA của fixture, snapshot và ba module code vào JSON để phát hiện drift.
- Kiểm thử source: `python -B -m pytest backend/tests/unit -q -p no:cacheprovider` đạt **59 passed** khi chạy với quyền truy cập thư mục tạm pytest trên Windows. Lượt sandbox đầu vấp `WinError 5` ở `tmp_path`, không phải assertion fail. Thư mục tạm tạo trong workspace đã dọn.

## Kết quả theo nhóm — development 13 ca

| Nhóm | Số ca | Đã đo | Kết quả / lỗi |
|---|---:|---:|---|
| Routing | 3 | 3 | 1/3 đúng tập agent; 2 ca lịch tập kháng lực chọn thừa `NutritionAgent`. |
| Retrieval | 4 | 4 | BM25 có filter: 4/4 đạt tiêu chí tạm thời; Recall@5=1, MRR=0,875, precision trên ID duy nhất=0,2125. Top-k không filter: 1/4, 7 tài liệu sai content type. |
| Safety | 2 | 2 phần | Risk classifier 2/2 khớp nhãn dự kiến; chưa đo fast-path, lời đáp, số call hoặc P95. |
| Claim/citation | 1 | 0 | Chưa có answer runtime và claim-level review. |
| Prompt injection | 1 | 0 | Chưa có corpus độc hại cô lập và LLM runtime. |
| Thiếu/mâu thuẫn bằng chứng | 1 | 0 | Chưa có cặp nguồn xung đột được duyệt. |
| Lỗi tool | 1 | 0 | Chưa chạy fault injection end-to-end. |

`blind_retrieval_dump` nối nguyên nội dung top-k không filter làm câu trả lời tham chiếu, chỉ lưu SHA-256 và độ dài để không log toàn văn: cùng hit retrieval 1/4 và 7 sai loại như top-k. **Không có điểm claim support**: việc in lại tài liệu/citation ID không chứng minh câu trả lời đúng, hữu ích hoặc an toàn. `Precision@k` ở đây chỉ đếm một ID relevant được ghi trong fixture, không phải precision lâm sàng trên toàn bộ kết quả.

## Phát hiện về dữ liệu và nhãn

- Snapshot có 5.345 `doc_id` duy nhất trên 23.608 dòng: 18.263 dòng lặp ID (4.834 giá trị ID bị lặp). Metric deduplicate ID trong top-k và ghi số dòng lặp; không coi chúng là bằng chứng độc lập. Chưa xác định các ID lặp là bản sao hoàn toàn hay các chunk khác nhau, nên **không xóa**.
- Phân bố: nutrition 22.354, exercise 1.234, inbody_metric 15, medical_safety 4, general_health 1. Corpus rất mất cân đối; 4 ca retrieval là ví dụ seed nhỏ, không thể suy ra Recall@5 tổng quát.
- Nhãn retrieval hiện chỉ được đối chiếu bằng ID/tiêu đề seed trong snapshot; tất cả đang `provisional`. 9/13 ca development cần chuyên gia y khoa rà soát theo metadata. Không tuyên bố gold lâm sàng.
- Routing sai do match chuỗi con `ăn` nằm trong `kháng`; đây là kết quả baseline, chưa sửa runtime trong đợt đo.

## Latency, regressions và quyết định

- Latency P50/P95 by route: **chưa đo**, vì không có HTTP runtime. Không dùng thời gian script offline để thay thế.
- Regression mới: 2 ca route kháng lực; nguy cơ sai content type khi bỏ filter; ID lặp gây nguy cơ citation/precision đánh lừa.
- Known limitations: chưa đo graph end-to-end/hybrid/Qdrant/reranker/LLM, citation entailment, injection, mâu thuẫn nguồn, lỗi tool và phản hồi y khoa; holdout chưa chạy; nhãn chưa được chuyên gia duyệt. Bài smoke 6/6 lịch sử không có giá trị suy rộng.
- Go/no-go: **NO-GO cho gate hoàn tất Đợt 1 và mọi tuyên bố chất lượng Agent RAG**. Có thể dùng suite/script này làm khung đo offline development; để qua gate cần mở runtime có kiểm soát, duyệt nhãn lâm sàng, bổ sung ca đa dạng, chạy answer-level/fault-injection và đo lại cùng corpus/model config.
