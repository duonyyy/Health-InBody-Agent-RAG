# Lộ trình triển khai Health/InBody Agent RAG

**Trạng thái:** kế hoạch triển khai; chưa phải xác nhận tính năng đã hoàn tất.  
**Cập nhật:** 2026-07-30  
**Phạm vi:** đưa MVP Health/InBody RAG từ demo kỹ thuật thành sản phẩm có bằng chứng, an toàn, đo lường được và có giá trị theo dõi tiến bộ.

## Mục tiêu sản phẩm

Sản phẩm không nên được định nghĩa là “một chatbot có nhiều agent”. Giá trị chính cần là:

1. Giúp người dùng hiểu dữ liệu InBody đã nhập/xác nhận.
2. Cho thấy xu hướng giữa các lần đo và dữ liệu nào làm cơ sở cho nhận định.
3. Đề xuất ăn uống/tập luyện tham khảo, có giới hạn an toàn.
4. Trả lời câu hỏi dựa trên nguồn truy xuất được, hoặc nói rõ khi thiếu bằng chứng.

## Thứ tự thực hiện bắt buộc

| Pha | Tài liệu | Mức cấp thiết | Lý do |
|---|---|---:|---|
| P0 | [00-p0-trust-rag-safety.md](00-p0-trust-rag-safety.md) | Khẩn cấp | Nếu nguồn, retrieval và safety chưa đáng tin, mở rộng chức năng sẽ làm tăng rủi ro. |
| P0 | [03-evaluation-and-acceptance.md](03-evaluation-and-acceptance.md) | Khẩn cấp | Không có benchmark thì không thể chứng minh các sửa đổi thực sự tốt hơn. |
| P1 | [01-p1-progress-and-personalization.md](01-p1-progress-and-personalization.md) | Cao | Đây là phần tạo giá trị khác biệt trực tiếp từ dữ liệu InBody. |
| P2 | [02-p2-ocr-privacy-and-live-web.md](02-p2-ocr-privacy-and-live-web.md) | Trung bình | OCR, dữ liệu nhạy cảm và web sống chỉ nên mở sau khi P0/P1 ổn định. |

## Quy tắc ra quyết định

- Không thêm agent mới nếu chưa có tác vụ, input, output và metric riêng của agent đó.
- Không gọi một kết quả là “đáng tin” chỉ vì vector similarity cao. Similarity chỉ là tín hiệu liên quan tài liệu, không phải xác suất đúng y khoa.
- Không chẩn đoán, kê đơn, đưa liều thuốc, hoặc thay thế bác sĩ.
- Câu có dấu hiệu cấp cứu phải đi bằng fast-path quyết định, không phụ thuộc LLM, RAG hay web search.
- Chỉ đưa một phase sang triển khai khi tiêu chí nghiệm thu của phase trước đã đạt.

## Tài liệu tham khảo đã khảo sát

- [InBody App](https://inbodyusa.com/inbody-app/): lịch sử đo, insight và theo dõi tiến độ.
- [Body Journey](https://bodyjourney.app/): progress tracking, kế hoạch tập/dinh dưỡng và hướng privacy-first.
- [Gymia](https://gymia.fit/): goal onboarding, workout/nutrition check-in và AI coach.
- [MedIntel RAG Chatbot](https://github.com/Gaggs-daggs/medintel-rag-chatbot): citation, uncertainty, RAGAS và cấu trúc RAG y tế.
- [WikiChat](https://github.com/stanford-oval/WikiChat): multilingual retrieval, BGE-M3, Qdrant, rerank, citation.
- [OpenAI Knowledge Retrieval](https://github.com/openai/openai-knowledge-retrieval): cấu hình retrieval, ingestion, chunking và evaluation.

## Hiện trạng cần lưu ý

Repo đã có FastAPI, LangGraph, Qdrant, BM25, safety tool, agent trace, `InBodyMeasurement` và test fast-path. Đây là nền tảng tốt. Tuy vậy trước khi mở rộng cần xác thực lại runtime sau các thay đổi hiện có:

- `POST /agent/answer` chưa trả `retrieved_docs` cho UI, dù state nội bộ có dữ liệu này.
- Composer nhận tài liệu RAG nhưng chưa có hợp đồng buộc citation theo từng nhận định.
- `initialize_from_vector_store(limit=1000)` cần được thay bằng scroll phân trang đủ corpus trước khi tuyên bố hybrid retrieval hoạt động đầy đủ.
- Báo cáo kiểm thử 2026-07-30 phản ánh một giai đoạn corpus đang ingest và latency cao; phải chạy lại benchmark sau khi chốt fast-path/index.

Các nhận định trên là các hạng mục kiểm tra/triển khai, không được đưa vào tài liệu marketing như thể đã hoàn thành.
