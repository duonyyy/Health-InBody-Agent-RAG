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

### API đã triển khai

```text
GET    /me/measurements?limit=...&cursor=...&confirmed_only=...
POST   /me/measurements
GET    /me/measurements/{measurement_id}
PATCH  /me/measurements/{measurement_id}
DELETE /me/measurements/{measurement_id}
GET    /me/progress/summary
GET    /me/progress/timeline
```

### Nội dung progress summary

```json
{
  "basis": "confirmed_non_deleted_measurements_only",
  "current": {"measured_at": "...", "weight_kg": 70.8, "pbf_percent": 25.4},
  "previous": {"measured_at": "...", "weight_kg": 72.0, "pbf_percent": 26.5},
  "days_between": 30,
  "delta": {
    "weight_kg": -1.2,
    "smm_kg": 0.3,
    "bfm_kg": -1.1,
    "pbf_percent": -1.1,
    "visceral_fat_level": -1
  },
  "data_quality": {
    "missing_current_metrics": [],
    "limitations": ["Delta mô tả số đo, không chứng minh cải thiện hay quan hệ nhân quả."]
  }
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

### Contract Agent response

```json
{
  "personalization_used": {
    "available": true,
    "reason": null,
    "provenance": [
      {"type": "profile", "confirmed_at": "..."},
      {"type": "measurement", "id": "...", "confirmed_at": "..."},
      {"type": "goal", "id": "...", "version": 2}
    ]
  }
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

## Deliverables P1 backend — trạng thái 2026-08-15

- [x] `/me/profile` GET/PUT/PATCH với field allowlist, sanitation và consent.
- [x] Goal current/history có version, bảo toàn history và chặn target cực đoan.
- [x] Measurement cursor CRUD, validation, provenance và soft delete.
- [x] Progress summary/timeline chỉ dùng record đã xác nhận, có delta và data-quality limits.
- [x] Versioned plan có input snapshot, goal version, confirmed measurement IDs, evidence/citations và safety result.
- [x] Check-in create/list; symptom urgent chạy safety route.
- [x] Agent chỉ dùng context consented + confirmed và trả provenance đã redacted.
- [x] Ownership HTTP: B không GET/PATCH/DELETE measurement A và không archive plan A.
- [x] Migration PostgreSQL `up/down`, ledger và rollback rehearsal.
- [x] Dashboard/profile/measurement/check-in UI đã được tích hợp hoàn chỉnh vào Streamlit frontend (`chat_interface_new.py`).

Báo cáo nghiệm thu và giới hạn production nằm tại `docs/P1_PERSONALIZATION_REPORT.md`.

### Tiến độ bộ nhớ — 2026-09-29

- Đã thêm history owner-scoped, fact cần xác nhận, event context, Zep confirmed-only và admission guard corpus.
- Có UI/API/migration/retention job và regression tests; **source-ready, chưa deploy**.
- Bằng chứng và gate còn mở: [báo cáo Day17](09-day17-memory-completion-2026-09-29.md).
