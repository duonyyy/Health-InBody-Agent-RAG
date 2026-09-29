# Agent harness

Đã chuyển các **ý tưởng**, không chép nguyên bài thi, từ
`VinAI/Track_Shared_Competitions/Day16-AgentArena-Student-main/harness`:

| Lớp | Vai trò trong dự án |
|---|---|
| `layers/injection_guard.py` | Gỡ khối chỉ thị giả có đánh dấu; bỏ chunk còn chỉ thị nguy hiểm; bảo toàn đoạn y khoa lành tính. |
| `layers/citation_checker.py` | Cấp ID chỉ sau khi chunk được làm sạch và đưa vào composer; prompt/API cùng một excerpt. |
| `layers/critic.py` | Chặn nguồn mâu thuẫn, claim thiếu hỗ trợ và câu trả lời mất cảnh báo. |
| `layers/retry.py` | Nhận diện kết quả tool bị cắt/nhiễu dù `ok=True`; chỉ retry trong giới hạn. |
| `layers/budget_policy.py` | Giới hạn số lần gọi và chừa thời gian cho composer. |

`guards.py` chứa các phép kiểm tra thuần; `budget.py` phân loại lỗi tạm thời.
`agents/graph.py` gắn các lớp trên vào ranh giới retrieval → composer → output
và giữ deadline/trace. Không mang sang vòng ReAct/submit, scorer, corpus thi đấu,
hay luật citation phải trích nguyên văn một dòng: chúng không phù hợp với RAG y tế.

Heuristic token-overlap trong guard **không phải** xác minh ngữ nghĩa/y khoa.
Claim mơ hồ bị từ chối; trước khi công khai cần đánh giá claim-level với người
có chuyên môn, kể cả các trường hợp diễn giải đúng nhưng dùng từ khác.
