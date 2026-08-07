# P0 — Tin cậy câu trả lời, Retrieval và Safety

**Mức cấp thiết:** khẩn cấp  
**Mục tiêu:** người dùng biết câu trả lời dựa vào đâu; hệ thống không tự tin khi thiếu nguồn; luồng rủi ro trả lời an toàn và nhanh.

## 0. Phụ thuộc và giới hạn

- Không phụ thuộc OCR/PDF upload.
- Có thể dùng data pipeline/Qdrant hiện tại, nhưng phải gắn metadata nguồn đầy đủ.
- Không đưa clinical diagnosis, medication dosage hay treatment plan vào corpus/output.
- Nếu corpus chưa đủ nguồn đáng tin, ưu tiên giảm phạm vi câu trả lời thay vì mở rộng scrape web vô kiểm soát.

---

## 1. Evidence contract cho API chat

### Vấn đề

`response_composer_agent` có context từ `retrieved_docs`, nhưng câu trả lời hiện không có liên kết máy đọc được giữa claim và nguồn. `agent_trace` chỉ chứng minh luồng kỹ thuật đã chạy, không chứng minh nội dung y khoa đúng.

### Thay đổi cần làm

1. Mở rộng `AgentState` với `evidence`, `evidence_status`, `limitations`.
2. Sau rerank, tạo danh sách evidence có ID cố định. ID này phải do backend gán, không do LLM tạo.
3. Sửa prompt composer:
   - Chỉ được dùng citation `[n]` có trong danh sách evidence.
   - Mọi claim sức khỏe/dinh dưỡng/tập luyện không thuần phép tính phải có citation.
   - Nếu evidence không hỗ trợ trực tiếp, nói `Không đủ bằng chứng trong kho tri thức hiện có`.
   - Không tạo URL, tác giả, số liệu hay citation mới.
4. Trả evidence trong `POST /agent/answer`.
5. Frontend render phần **Nguồn tham khảo**, mặc định thu gọn.

### Contract đề xuất

```json
{
  "answer": "PBF 28% là mức cao theo ngưỡng tham khảo cho nam [1].",
  "evidence_status": "supported",
  "citations": [
    {
      "id": 1,
      "document_id": "inbody-pbf-001",
      "title": "Hướng dẫn diễn giải PBF",
      "source_url": "https://example.org/source",
      "publisher": "...",
      "source_tier": "guideline",
      "published_at": "2025-01-15",
      "excerpt": "Đoạn văn trực tiếp hỗ trợ claim...",
      "retrieval_score": 0.82,
      "rerank_score": 0.91,
      "content_type": "inbody_metric"
    }
  ],
  "limitations": [
    "Chưa có tuổi, mức vận động và bệnh nền.",
    "Thông tin chỉ mang tính tham khảo, không phải chẩn đoán."
  ]
}
```

### Trạng thái evidence

| Giá trị | Khi dùng | Hành vi UI |
|---|---|---|
| `supported` | Có tài liệu trực tiếp hỗ trợ claim | Hiển thị citation. |
| `partial` | Chỉ hỗ trợ một phần hoặc nguồn cũ | Hiển thị giới hạn rõ ràng. |
| `insufficient` | Không đủ tài liệu liên quan/chất lượng | Không đưa khuyến nghị cụ thể; yêu cầu thêm dữ liệu hoặc khuyên gặp chuyên gia. |
| `not_required` | BMI/tool tính toán, lời chào, luồng cấp cứu định sẵn | Nêu rõ là kết quả tool/khuyến cáo an toàn, không giả citation. |

### Tiêu chí nghiệm thu

- 100% câu trả lời RAG trả `evidence_status`.
- `supported`/`partial` phải có ít nhất một citation hợp lệ.
- Không có citation trỏ tới document không nằm trong kết quả rerank.
- UI hiển thị title, domain, ngày và excerpt, không chỉ tên file nội bộ.

---

## 2. Curation và metadata nguồn tri thức

### Metadata bắt buộc

```json
{
  "document_id": "stable-id",
  "title": "...",
  "source_url": "...",
  "publisher": "...",
  "source_tier": "guideline",
  "published_at": "2025-01-15",
  "reviewed_at": "2026-07-30",
  "language": "vi",
  "country_scope": "global",
  "audience": "general_adult",
  "content_type": "nutrition",
  "section": "Protein intake",
  "medical_review_status": "approved"
}
```

### Thang chất lượng nguồn

1. `guideline`: cơ quan y tế/hiệp hội chuyên môn, hướng dẫn lâm sàng.
2. `government`: cơ quan nhà nước/y tế công.
3. `peer_reviewed`: bài báo khoa học đã phản biện.
4. `professional_org`: tổ chức chuyên môn có uy tín.
5. `clinic_education`: nội dung giáo dục y tế, phải được review.
6. `commercial` hoặc `unknown`: không dùng cho claim y khoa chính.

### Quy tắc ingestion

- Duy trì whitelist domain và nguồn đã được duyệt.
- Lưu URL gốc, ngày xuất bản/cập nhật và license khi có.
- Không index PDF scan/OCR chưa được xác thực như nguồn kiến thức.
- Tách chunk theo heading/bảng/chủ đề; không tách bằng số ký tự đơn thuần.
- Không đưa dữ liệu người dùng, chat log hoặc file InBody cá nhân vào collection kiến thức chung.

### Lý do

WikiChat cho thấy retrieval tốt cần pipeline dữ liệu, multilingual embeddings, rerank và citation; không chỉ là gọi vector DB. [WikiChat](https://github.com/stanford-oval/WikiChat) OpenAI Knowledge Retrieval cũng tách rõ config, ingestion, chiến lược chunking và evaluation. [Nguồn](https://github.com/openai/openai-knowledge-retrieval)

---

## 3. Sửa hybrid retrieval và routing

### Việc cần làm

1. Thay `initialize_from_vector_store(limit=1000)` bằng scroll có pagination tới hết collection.
2. Lưu `index_version`, `qdrant_points`, `bm25_documents`, `embedding_model` trong health/status endpoint.
3. Rebuild BM25 sau batch ingest thành công; không rebuild theo request.
4. Filter retrieval theo intent/content type trước rerank.
5. Chuẩn hóa tiếng Việt không dấu, dấu câu, typo thường gặp trước router và retrieval.
6. Lưu retrieval diagnostics cho mỗi request: query rewrite, filters, top-k, score, rerank order, latency.

### Routing matrix

| Intent | Retrieval | Tool/agent ưu tiên | Không làm |
|---|---|---|---|
| BMI, PBF, mỡ nội tạng đơn lẻ | Không bắt buộc | InBody deterministic tool | LLM/rewrite nếu chỉ là tính toán. |
| Ăn uống/macro | `nutrition` | Nutrition tool + RAG | Claim không nguồn. |
| Lịch tập cơ bản | `exercise` | Training tool + RAG khi có bằng chứng | Kế hoạch cực đoan. |
| Câu hỏi tổng hợp | Nhiều filter | InBody + Nutrition + Training + RAG | Chạy agent không liên quan. |
| Dấu hiệu khẩn cấp | Không | Safety fast-path | Gọi LLM, web, RAG trước. |

### Health endpoint đề xuất

```json
{
  "status": "ready",
  "qdrant_points": 23608,
  "bm25_documents": 23608,
  "index_version": "2026-07-30T16:00:00Z",
  "embedding_model": "bge-m3",
  "reranker": "...",
  "last_successful_ingest": "..."
}
```

Không được dùng con số ví dụ ở trên như số production thật; endpoint phải trả số runtime thực tế.

---

## 4. Safety workflow

### Mức rủi ro

| Mức | Ví dụ | Hành vi |
|---|---|---|
| `low` | Tính BMI, giải thích PBF | Trả lời trong phạm vi tham khảo. |
| `medical_caution` | bệnh nền, đau kéo dài, đang dùng thuốc, chấn thương | Hạn chế plan; hỏi thêm hoặc khuyên gặp chuyên gia. |
| `urgent` | đau ngực, khó thở, ngất, dấu hiệu đột quỵ | Trả cảnh báo quyết định; dừng agent/RAG/LLM/web. |

### Yêu cầu kỹ thuật

- Precheck safety trước query rewrite và trước graph.
- Urgent response là template đã review, không sinh bởi LLM.
- Log `fast_path=urgent_safety`, latency và rule match; không log toàn bộ dữ liệu nhạy cảm.
- Viết regression test để đảm bảo urgent path không gọi `openai_chat_complete`, vector search hoặc Tavily.
- Caution response không được kê đơn, suy luận bệnh hoặc tạo workout plan khi triệu chứng/chấn thương chưa rõ.

### Cảnh báo về “confidence score”

Không gắn nhãn `82% chính xác` cho câu trả lời. Score retrieval/rerank chỉ giúp kiểm soát hệ thống. MedIntel có confidence thresholds là ý tưởng tham khảo tốt, nhưng score đó không phải xác suất y khoa. [MedIntel](https://github.com/Gaggs-daggs/medintel-rag-chatbot)

## Deliverables P0

- [ ] API evidence contract và UI nguồn tham khảo.
- [ ] Metadata schema + validation ingestion.
- [ ] BM25 đủ corpus, index status/version.
- [ ] Intent filters và normalization tiếng Việt.
- [ ] Safety precheck/fast-path được test.
- [ ] Bộ benchmark và báo cáo P0 theo tài liệu evaluation.
