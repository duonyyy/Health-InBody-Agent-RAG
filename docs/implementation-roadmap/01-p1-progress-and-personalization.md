# P1 — Theo dõi tiến độ và cá nhân hóa có kiểm soát

**Mức cấp thiết:** cao, thực hiện sau P0  
**Mục tiêu:** biến dữ liệu InBody thành hành trình có thể theo dõi; chatbot giải thích trên dữ liệu rõ ràng thay vì tạo lời khuyên chung chung.

## 1. Nguyên tắc sản phẩm

InBody App tập trung vào dữ liệu thành phần cơ thể, insight và lịch sử kết quả. [Nguồn](https://inbodyusa.com/inbody-app/) Body Journey kết hợp progress tracking, analytics, workout và nutrition; Gymia đặt mục tiêu, theo dõi log và coach trong một chu kỳ. [Body Journey](https://bodyjourney.app/) [Gymia](https://gymia.fit/)

Điểm học được không phải là sao chép toàn bộ app fitness. MVP chỉ cần vòng lặp rõ ràng:

```text
Lần đo đã xác nhận
  → so sánh với baseline/lần trước
  → xác định một mục tiêu tham khảo
  → kế hoạch tuần có giới hạn
  → check-in
  → lần đo tiếp theo
```

## 2. Dashboard và measurement comparison

### API đề xuất

```text
GET  /users/{user_id}/measurements
POST /users/{user_id}/measurements
GET  /users/{user_id}/measurements/compare?baseline_id=...&current_id=...
GET  /users/{user_id}/progress-summary
```

### Nội dung progress summary

```json
{
  "current_measurement": {"date": "2026-07-30", "weight_kg": 70.8, "pbf_percent": 25.4},
  "comparison_period": {"baseline_date": "2026-06-30", "days": 30},
  "changes": {
    "weight_kg": -1.2,
    "smm_kg": 0.3,
    "bfm_kg": -1.1,
    "pbf_percent": -1.1,
    "visceral_fat_level": -1
  },
  "trend_labels": ["weight_down", "fat_down", "muscle_stable"],
  "data_quality_notes": [
    "Nên đo cùng thiết bị và trong điều kiện tương tự.",
    "Không kết luận tăng cơ chỉ từ biến động nhỏ ở hai lần đo."
  ]
}
```

### UI tối thiểu

1. **Thẻ lần đo gần nhất:** ngày đo, cân nặng, BMI, PBF, SMM, mỡ nội tạng.
2. **So sánh:** delta và chiều thay đổi, không chỉ giá trị mới.
3. **Biểu đồ:** chọn một chỉ số/lần; không nhồi quá nhiều line chart vào một màn hình.
4. **Data quality note:** cùng thiết bị, tình trạng đo, khoảng cách hai lần đo.
5. **CTA:** “Hỏi Health Agent về thay đổi này”. Prompt được tạo sẵn có dữ liệu đo + delta.

### Không được suy diễn

- `SMM +0.2 kg` không đồng nghĩa chắc chắn tăng cơ.
- Cân nặng giảm không đồng nghĩa cải thiện sức khỏe trong mọi ngữ cảnh.
- Mục tiêu giảm mỡ không cho phép đưa calorie deficit cực đoan.

## 3. Profile completeness và provenance

### Lý do

Personalization hữu ích chỉ khi người dùng biết hệ thống đã sử dụng gì. MedRaga minh họa cách ghép profile vào RAG, nhưng phạm vi diagnosis/treatment của repo đó không phù hợp với app đại chúng. [MedRaga](https://github.com/mdimado/MedRaga)

### Contract

```json
{
  "profile_completeness": 65,
  "used_fields": ["sex", "height_cm", "weight_kg", "pbf_percent", "goal"],
  "missing_fields": ["birth_year", "activity_level", "medical_conditions", "injury_constraints"],
  "measurement_source": "manual_confirmed",
  "measurement_date": "2026-07-30"
}
```

### Quy tắc

- Không suy ra giới tính, tuổi, hoạt động hay bệnh nền từ văn phong người dùng.
- Thông tin cũ phải có ngày; UI cần cho phép người dùng sửa/xóa.
- Medical conditions chỉ dùng để tăng mức an toàn, không để LLM kết luận bệnh.
- Tách `manual_confirmed`, `ocr_unconfirmed`, `device_imported`; chỉ dữ liệu đã xác nhận được dùng để cá nhân hóa mạnh.

## 4. Kế hoạch tuần có output cấu trúc

Không lưu một đoạn chat tự do làm “kế hoạch”. Lưu một object versioned để người dùng và hệ thống đều biết plan nào đang hiệu lực.

```json
{
  "plan_id": "...",
  "version": 1,
  "status": "draft|active|superseded|completed",
  "goal": "fat_loss",
  "input_snapshot": {
    "measurement_id": "...",
    "profile_fields_used": ["..."],
    "constraints": ["beginner", "3_sessions_per_week"]
  },
  "nutrition": {
    "energy_strategy": "moderate_deficit",
    "protein_range_g_per_day": [112, 154],
    "notes": ["..."]
  },
  "training": {
    "sessions_per_week": 3,
    "sessions": [{"day": "...", "focus": "...", "safety_notes": ["..."]}]
  },
  "evidence_ids": [1, 2],
  "review_due_date": "2026-08-06"
}
```

### Logic điều chỉnh

- Không tự thay plan chỉ vì một lần log thiếu.
- Khi có triệu chứng/chấn thương: pause plan, chuyển safety/caution.
- Khi có lần đo mới: tạo plan draft mới và giải thích dữ liệu nào thay đổi.
- Người dùng luôn có quyền chỉnh mục tiêu, số buổi/tuần, thiết bị và hạn chế.

## 5. Check-in tuần

Check-in không cần gamification phức tạp. Bản MVP chỉ cần 4 câu:

1. Bạn hoàn thành bao nhiêu buổi tập?
2. Mức năng lượng/giấc ngủ tuần này thế nào?
3. Có đau, chấn thương hoặc triệu chứng bất thường không?
4. Bạn thấy khó nhất ở dinh dưỡng hay tập luyện?

Nếu câu 3 có tín hiệu risk, không hiển thị lời khuyên “cố gắng tập tiếp”; chuyển safety flow.

## Deliverables P1

- [ ] Measurement list, compare, progress-summary API.
- [ ] Dashboard latest measurement + trend chart + data-quality note.
- [ ] Profile completeness/provenance trả về trong chat.
- [ ] Versioned weekly plan schema và UI draft/active.
- [ ] Weekly check-in với route safety.
- [ ] Test permission: chỉ chủ sở hữu xem/sửa lịch sử đo của mình.
