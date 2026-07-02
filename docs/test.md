# Health/InBody Multi-Agent RAG MVP - Test Queries

## Tổng quan

File này chứa các câu test dùng để demo và kiểm tra hệ thống Health/InBody Multi-Agent RAG MVP.

Mục tiêu test:

- Kiểm tra `SupervisorAgent` chọn đúng một hoặc nhiều agent.
- Kiểm tra `agent_trace` có thể chứng minh flow multi-agent.
- Kiểm tra các agent chính: `InBodyAgent`, `RAGAgent`, `NutritionAgent`, `TrainingAgent`, `SafetyAgent`, `ResponseComposerAgent`.
- Kiểm tra câu hỏi phức hợp gọi nhiều agent cùng lúc.

## 1. InBodyAgent

```json
[
  {
    "query": "Tôi nặng 72kg cao 170cm, tính BMI giúp tôi",
    "expected_agents": ["SupervisorAgent", "InBodyAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["calculate_bmi"],
    "description": "Tính BMI từ cân nặng và chiều cao"
  },
  {
    "query": "PBF của tôi 28%, nam, chỉ số này có cao không?",
    "expected_agents": ["SupervisorAgent", "InBodyAgent", "RAGAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["evaluate_body_fat_percentage"],
    "description": "Đánh giá phần trăm mỡ cơ thể"
  },
  {
    "query": "Mỡ nội tạng level 12 có đáng lo không?",
    "expected_agents": ["SupervisorAgent", "InBodyAgent", "RAGAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["evaluate_visceral_fat"],
    "description": "Đánh giá mỡ nội tạng từ level InBody"
  }
]
```

## 2. NutritionAgent và TrainingAgent

```json
[
  {
    "query": "Tôi 72kg, muốn giảm mỡ thì nên ăn bao nhiêu protein mỗi ngày?",
    "expected_agents": ["SupervisorAgent", "NutritionAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["suggest_nutrition_goal"],
    "description": "Gợi ý protein và chiến lược calo"
  },
  {
    "query": "Gợi ý lịch tập 3 buổi/tuần để giảm mỡ",
    "expected_agents": ["SupervisorAgent", "TrainingAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["suggest_training_plan"],
    "description": "Gợi ý lịch tập theo tuần"
  },
  {
    "query": "Tôi muốn tăng cơ, 65kg, nên ăn và tập thế nào 4 buổi/tuần?",
    "expected_agents": ["SupervisorAgent", "NutritionAgent", "TrainingAgent", "RAGAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_tools": ["suggest_nutrition_goal", "suggest_training_plan"],
    "description": "Câu hỏi phức hợp gọi nutrition, training và RAG"
  }
]
```

## 3. Multi-Agent Demo Query

Câu này dùng tốt nhất khi demo trước hội đồng vì nó buộc hệ thống gọi nhiều agent:

```json
{
  "query": "Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng level 12. Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi/tuần?",
  "expected_agents": [
    "QuestionNormalizerAgent",
    "SupervisorAgent",
    "InBodyAgent",
    "NutritionAgent",
    "TrainingAgent",
    "RAGAgent",
    "SafetyAgent",
    "ResponseComposerAgent"
  ],
  "expected_trace_min_length": 6,
  "description": "Demo đầy đủ Multi-Agent RAG MVP"
}
```

Expected behavior:

1. `SupervisorAgent` chọn nhiều agent, không chỉ một route.
2. `InBodyAgent` tính BMI, đánh giá PBF và mỡ nội tạng.
3. `NutritionAgent` đưa protein/calorie strategy.
4. `TrainingAgent` đưa lịch tập 3 buổi/tuần.
5. `RAGAgent` truy xuất tài liệu Health/InBody liên quan.
6. `SafetyAgent` thêm guardrail y tế.
7. `ResponseComposerAgent` tổng hợp câu trả lời cuối.

## 4. SafetyAgent

```json
[
  {
    "query": "Tôi bị đau ngực khi tập cardio, có nên tiếp tục tập không?",
    "expected_agents": ["SupervisorAgent", "TrainingAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_safety_risk": "urgent",
    "description": "Triệu chứng nguy hiểm cần khuyến nghị gặp cơ sở y tế"
  },
  {
    "query": "Tôi bị tiểu đường, muốn giảm mỡ nhanh thì có nên nhịn ăn không?",
    "expected_agents": ["SupervisorAgent", "NutritionAgent", "RAGAgent", "SafetyAgent", "ResponseComposerAgent"],
    "expected_safety_risk": "medical_caution",
    "description": "Có bệnh nền, phải trả lời thận trọng"
  }
]
```

## 5. RAGAgent

```json
[
  {
    "query": "BMI và PBF khác nhau như thế nào?",
    "expected_agents": ["SupervisorAgent", "InBodyAgent", "RAGAgent", "SafetyAgent", "ResponseComposerAgent"],
    "description": "Truy xuất kiến thức giải thích chỉ số"
  },
  {
    "query": "SMM thấp thì nên ưu tiên tập luyện kiểu gì?",
    "expected_agents": ["SupervisorAgent", "InBodyAgent", "RAGAgent", "TrainingAgent", "SafetyAgent", "ResponseComposerAgent"],
    "description": "Kết hợp kiến thức InBody và training"
  }
]
```

## 6. API Smoke Test

```bash
curl -X POST http://localhost:8000/chat/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "user_message": "Tôi nam, 72kg, cao 170cm, PBF 28%, mỡ nội tạng level 12. Tôi nên giảm mỡ hay tăng cơ trước và tập thế nào 3 buổi/tuần?",
    "sync_request": true
  }'
```

Response cần có:

```json
{
  "response": {
    "role": "assistant",
    "content": "...",
    "agent_trace": [
      {
        "agent": "SupervisorAgent",
        "action": "select_agents",
        "status": "success",
        "summary": "Selected agents: InBodyAgent, NutritionAgent, TrainingAgent, RAGAgent"
      }
    ]
  }
}
```

## 7. Acceptance Criteria

- `/chat/complete` trả `response.content` không rỗng.
- `/chat/complete` trả `response.agent_trace` là list.
- Câu hỏi phức hợp phải có ít nhất `SupervisorAgent`, một domain agent, `SafetyAgent`, `ResponseComposerAgent`.
- Người dùng không cần chọn tool thủ công trong frontend chat.
- Các endpoint `/tools/...` vẫn hoạt động để dev/debug nhưng không phải flow chính của người dùng.
