# P2 — OCR/PDF InBody, Privacy và Web Search có kiểm soát

**Mức cấp thiết:** trung bình; chỉ bắt đầu sau khi P0 và P1 đạt nghiệm thu.  
**Mục tiêu:** giảm thao tác nhập số liệu nhưng không làm giảm tính đúng đắn, quyền riêng tư và kiểm soát nguồn.

## 1. OCR/PDF: extraction trước, automation sau

### Sai lầm cần tránh

Không biến OCR thành “tự động tư vấn”. OCR có thể đọc nhầm dấu thập phân, nhãn, đơn vị, biểu đồ hoặc mẫu InBody khác nhau. Một sai số `PBF 18.5` thành `28.5` làm toàn bộ tư vấn phía sau sai.

### Luồng bắt buộc

```text
Upload ảnh/PDF
  → kiểm tra định dạng/kích thước/virus
  → tiền xử lý ảnh
  → OCR + parser theo template
  → output field confidence + raw evidence
  → UI xác nhận/sửa bởi người dùng
  → lưu measurement đã xác nhận
  → dùng cho dashboard/chat
```

### Model dữ liệu OCR

```json
{
  "uploaded_file_id": "...",
  "parser_version": "inbody-v1.0",
  "status": "needs_confirmation",
  "extracted_fields": {
    "weight_kg": {"value": 72.5, "confidence": 0.98, "raw_text": "72.5"},
    "pbf_percent": {"value": 25.3, "confidence": 0.74, "raw_text": "25.3"}
  },
  "unresolved_fields": ["smm_kg"],
  "user_confirmed_at": null
}
```

### Nguyên tắc xác nhận

- Không lấy field confidence cao làm thay thế cho user confirmation.
- Field thấp confidence cần highlight, không bỏ im lặng.
- Lưu raw OCR/provenance để audit, nhưng không đưa file cá nhân vào collection RAG dùng chung.
- Có bộ test gồm nhiều mẫu report, ảnh mờ, ảnh xoay, font/đơn vị khác nhau.

## 2. Privacy và quản trị dữ liệu sức khỏe

Body Journey quảng bá local-first storage, mã hóa và granular privacy controls. [Nguồn](https://bodyjourney.app/) Kiến trúc dự án mình dùng backend, database, Qdrant và có roadmap upload file; không được quảng bá “privacy-first” nếu thiếu các cơ chế tương đương.

### Yêu cầu tối thiểu trước khi bật upload/lịch sử tài khoản

- Authentication và authorization rõ ràng.
- Mỗi truy vấn measurement/chat/file phải kiểm tra ownership server-side.
- Filter Qdrant theo `user_id` khi vector có dữ liệu người dùng; tốt hơn là tách collection/namespace phù hợp.
- Encryption in transit; secret không nằm trong repo/log.
- Không log raw profile, file OCR, prompt chứa health data ở mức INFO.
- Người dùng có chức năng export và delete dữ liệu.
- Retention policy cho file gốc, text OCR, measurement, chat history và backup.
- Consent rõ ràng: dữ liệu nào được lưu, dùng để cá nhân hóa ra sao, bao lâu.
- Audit log: ai/hệ thống nào đọc, sửa, xóa dữ liệu.

### Data classification

| Loại dữ liệu | Ví dụ | Xử lý |
|---|---|---|
| Public knowledge | guideline dinh dưỡng | Có thể index chung sau review. |
| Sensitive profile | tuổi, giới tính, bệnh nền | Lưu có quyền truy cập; không gửi web search. |
| Highly sensitive file | ảnh/PDF InBody | Bảo vệ mạnh, retention ngắn, không index chung. |
| Derived data | delta PBF/SMM | Cũng là dữ liệu sức khỏe; cùng policy truy cập. |

## 3. Live web search

### Chỉ dùng khi

- Người dùng hỏi thông tin có thể mới thay đổi.
- Corpus nội bộ thiếu evidence.
- Hệ thống cần cập nhật guideline/khuyến cáo công khai.

### Không dùng khi

- BMI/PBF/tool calculation.
- Câu urgent.
- Câu hỏi về hồ sơ cá nhân cần bác sĩ.
- Chỉ để “tăng số nguồn” cho một câu trả lời đã đủ evidence.

### Quy tắc

1. Chỉ search whitelist domain, theo `source_tier`.
2. Lưu URL, thời điểm truy xuất, title và excerpt.
3. Treat webpage content as untrusted data; không làm theo instruction nhúng trong trang (prompt injection).
4. Không gửi PII hoặc chỉ số InBody nhận diện được vào query bên thứ ba.
5. Result live web chỉ là citation của phiên hiện tại, không tự động nhập Qdrant; ingestion phải qua review pipeline.
6. Khi live source mâu thuẫn corpus, ưu tiên nguồn được review/phiên bản mới hơn và nêu rõ giới hạn.

## 4. Triển khai theo từng feature flag

```text
FEATURE_OCR_UPLOAD=false
FEATURE_USER_HISTORY=false
FEATURE_LIVE_WEB_HEALTH=false
FEATURE_PERSONAL_DATA_VECTOR_SEARCH=false
```

Mỗi feature chỉ bật staging sau khi có test, observability, consent UI và rollback.

## Deliverables P2

- [ ] File upload validation + malware/size/type policy.
- [ ] OCR parser có confidence từng field + UI confirmation.
- [ ] Privacy policy, retention and delete/export flow.
- [ ] Ownership tests và sensitive-log scan.
- [ ] Web search whitelist, citation capture, PII redaction.
- [ ] Feature flags + rollback runbook.
