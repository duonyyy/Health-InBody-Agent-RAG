# Checkpoint đọc Day16 AgentArena — 2026-09-27

Nguồn: `C:\Users\Admin\Desktop\KLTN\VinAI\Track_Shared_Competitions\Day16-AgentArena-Student-main`. Đây là tài liệu tham khảo, **không** phải corpus y khoa và không được import vào dữ liệu Health/InBody. Trạng thái bên dưới phân biệt đọc source sâu với quét cấu trúc; không gọi quét AST là đã đọc từng assertion.

## Manifest tests/scripts

| File | Dòng | Test | Trạng thái checkpoint |
|---|---:|---:|---|
| `scripts/verify.py` | 722 | — | Đọc source toàn file; hợp đồng trace, preflight, caps, determinism, no-network. |
| `scripts/selfeval.py` | 1.198 | — | Đọc source toàn file; chẩn đoán claim, nguồn công khai, cảnh báo overfit. |
| `scripts/run_practice.py` | 451 | — | Đã đọc ở lượt nghiên cứu trước; chưa rà lại từng dòng trong lượt này. |
| `scripts/leaderboard.py` | 261 | — | Đã đọc ở lượt nghiên cứu trước; chưa rà lại từng dòng trong lượt này. |
| `tests/__init__.py` | 0 | 0 | Rỗng. |
| `tests/fixtures_briefs.py` | 153 | 0 | Quét AST/cấu trúc, chưa đọc toàn bộ literal. |
| `tests/test_briefs.py` | 373 | 20 | Đọc chọn lọc trước; quét AST toàn file, chưa rà từng assertion. |
| `tests/test_corpus.py` | 261 | 27 | Quét AST toàn file, chưa rà từng assertion. |
| `tests/test_layers_stubs.py` | 256 | 9 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_middleware.py` | 1.064 | 49 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_model.py` | 1.157 | 47 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_no_instructor_leak.py` | 410 | 11 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_runner.py` | 1.509 | 76 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_scorer.py` | 2.291 | 102 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_synthesis.py` | 533 | 32 | Đọc chọn lọc trước; quét AST toàn file. |
| `tests/test_tools.py` | 312 | 22 | Quét AST toàn file, chưa rà từng assertion. |
| `tests/test_trace.py` | 902 | 52 | Đọc chọn lọc trước; quét AST toàn file. |

Tổng: 11.853 dòng test/script, 447 test functions theo AST. Quét cấu trúc không đồng nghĩa 447 test đã được hiểu đầy đủ. **Việc còn lại theo yêu cầu “đọc toàn bộ”: đọc kỹ thân/fixture/assertion của các test chưa ghi “đọc source toàn file”, đặc biệt `test_scorer.py`, `test_runner.py`, `test_trace.py` và hai script thực hành/bảng điểm cần rà lại.** Checkpoint này cố ý không đánh dấu hoàn tất giả.

## Bài học chuyển sang Health/InBody

| Bài học từ Day16 | Chuyển hóa trong Đợt 1 | Giới hạn |
|---|---|---|
| Public practice không dự báo hidden evaluation; `selfeval.guard_public` chỉ cho chẩn đoán bộ công khai. | `development` mặc định; 7 ca `holdout` chưa chạy. | Holdout nằm trong repo, là quy ước chống tuning, không phải nhãn bí mật thật. |
| Trace/provenance phải qua gate trước khi chấm điểm; ID trích dẫn hợp lệ chưa đủ chứng minh claim. | Fixture có nhóm claim/citation; report để `not_measured` thay vì cho điểm ngầm. | Cần claim-level annotated evidence + reviewer y khoa. |
| Blind dump/quote và echo question có thể ăn điểm retrieval nhưng không phải answer quality. | Baseline `blind_retrieval_dump` được tách, `claim_support=not_measured`. | Chưa có LLM runtime để chấm answer. |
| Injection, absent, contradiction, degraded tool cần bẫy riêng, không gộp với happy path. | Fixture có bốn nhóm riêng và expected behavior. | Chưa có sandboxed fault/doc injection execution. |
| Preflight fail loud; budget/call trace không được im lặng khi model/tool lỗi. | Evaluator từ chối sai version/ID/fixture và ghi lý do chưa đo. | Chưa đo fast-path call counts, timeout, P95. |
| Determinism dùng seed/input/hash và kiểm tra hai process; một điểm tổng che lỗi. | Report ghim SHA-256 corpus/fixture/source và xuất theo nhóm; chạy lặp byte-identical. | Chỉ chứng minh phép đo offline deterministic. |

Không chép rubric literal/verbatim của AgentArena cho câu trả lời y khoa: câu diễn giải đúng có thể không nguyên văn một dòng; clinical entailment phải được người có chuyên môn rà soát, và không cho bộ chấm tự động hợp thức hóa lời khuyên lâm sàng.
