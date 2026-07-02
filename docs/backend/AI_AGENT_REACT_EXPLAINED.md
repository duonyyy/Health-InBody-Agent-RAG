# Giải Thích Health/InBody Agent

Tài liệu này mô tả phần agent trong backend hiện tại của dự án Health/InBody Agent RAG. Vai trò chính của agent là điều phối giữa hỏi đáp RAG, health tools, web search và hội thoại thông thường.

## 1. File Liên Quan

- `backend/src/agent.py`: hàm agent trả lời trực tiếp và tóm tắt danh sách công cụ.
- `backend/src/tasks.py`: route câu hỏi, gọi RAG, gọi health tools hoặc web search.
- `backend/src/brain.py`: phát hiện intent, phát hiện route, build prompt trả lời.
- `backend/src/health_tools.py`: các công cụ tính toán sức khỏe.
- `backend/src/tavily_tool.py`: tìm kiếm web cho câu hỏi cần dữ liệu mới.

## 2. Các Route Chính

Backend phân loại câu hỏi vào 4 route:

| Route | Khi dùng | Xử lý |
| --- | --- | --- |
| `health_rag` | Hỏi kiến thức InBody, BMI, PBF, SMM, BFM, dinh dưỡng, tập luyện | Rewrite query, hybrid search, rerank, LLM trả lời |
| `agent_tools` | Cần tính toán hoặc đánh giá chỉ số cụ thể | Gọi tool BMI, PBF, mỡ nội tạng, protein, lịch tập, safety |
| `web_search` | Cần thông tin mới, nghiên cứu/tin tức gần đây | Gọi Tavily rồi LLM tổng hợp |
| `general_chat` | Chào hỏi, cảm ơn, câu hỏi ngoài phạm vi | Trả lời hội thoại an toàn |

## 3. Health Tools

Các tool hiện có:

- `calculate_bmi(weight_kg, height_cm)`: tính BMI và phân loại cơ bản.
- `evaluate_body_fat_percentage(pbf_percent, sex)`: đánh giá phần trăm mỡ cơ thể.
- `evaluate_visceral_fat(visceral_fat_level)`: đánh giá mỡ nội tạng.
- `suggest_nutrition_goal(goal, weight_kg, activity_level)`: gợi ý dinh dưỡng tham khảo.
- `suggest_training_plan(goal, fitness_level, days_per_week)`: gợi ý lịch tập.
- `check_medical_safety(question, conditions)`: phát hiện tình huống cần khuyến nghị gặp bác sĩ.

Các tool này phục vụ tư vấn tham khảo, không thay thế chuyên gia y tế.

## 4. Luồng `ai_agent_handle`

Luồng xử lý đơn giản:

1. Nhận câu hỏi và lịch sử hội thoại.
2. Chuẩn hóa hoặc viết lại câu hỏi follow-up nếu cần.
3. Phân loại route.
4. Nếu là câu hỏi tính toán, gọi health tools.
5. Nếu là câu hỏi kiến thức, gọi RAG pipeline.
6. Nếu cần dữ liệu mới, gọi web search.
7. Trả về câu trả lời tiếng Việt có cảnh báo an toàn phù hợp.

## 5. Ví Dụ

### Câu hỏi dùng RAG

```text
PBF cao có nguy hiểm không?
```

Luồng:

```text
detect_route -> health_rag
rewrite_query -> hybrid_search -> rerank -> generate_health_answer
```

### Câu hỏi dùng tool

```text
Tôi nặng 70kg cao 170cm thì BMI bao nhiêu?
```

Luồng:

```text
detect_route -> agent_tools -> calculate_bmi
```

### Câu hỏi cần web search

```text
Có nghiên cứu mới nhất nào về mỡ nội tạng không?
```

Luồng:

```text
detect_route -> web_search -> tavily_search_health -> LLM summary
```

## 6. Guardrail Y Tế

Agent cần tuân thủ các nguyên tắc:

- Không chẩn đoán bệnh.
- Không kê đơn thuốc hoặc liều thuốc.
- Không thay thế bác sĩ, chuyên gia dinh dưỡng hoặc huấn luyện viên.
- Khi có dấu hiệu nguy hiểm như đau ngực, khó thở, ngất, triệu chứng bất thường, bệnh nền phức tạp hoặc đang dùng thuốc, cần khuyên người dùng gặp chuyên gia y tế.
- Khi thiếu dữ liệu cá nhân, trả lời ở mức tham khảo và nói rõ giới hạn.
