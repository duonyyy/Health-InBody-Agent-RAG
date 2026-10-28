# Agentic AI Platform Service (`agent-service`)

Dịch vụ Tác tử Thông minh & Tìm kiếm Lai RAG (Stateless Agent Reasoning & Hybrid RAG Platform) cho nền tảng Health/InBody Agent RAG.

## Trách nhiệm chính:
1. **Tiền kiểm An toàn Y tế (Deterministic Safety Pre-check):** Xử lý ngắt khẩn cấp cho các ca cấp cứu (đau ngực, khó thở, ngất xỉu) với độ trễ P95 < 500ms, không gọi LLM hay truy vấn vector.
2. **Đồ thị Tác tử LangGraph:** Điều phối luồng xử lý chuyên môn (`supervisor`, `inbody`, `nutrition`, `training`, `rag`, `web_search`, `composer`).
3. **Tìm kiếm lai RAG (Hybrid Search):** Tích hợp Qdrant Vector Collection (BGE-M3 Dense) kết hợp BM25 sparse snapshot và Cross-encoder reranker.
4. **Công cụ Sinh trắc học (Health Tools):** Đánh giá BMI, phần trăm mỡ cơ thể (PBF), mỡ nội tạng (Visceral Fat), và tính toán nhu cầu calo/lịch tập.
5. **Ranh giới Tác tử (Agent Boundary):** Hoàn toàn không kết nối trực tiếp PostgreSQL. Nhận ngữ cảnh người dùng thông qua `AgentChatRequest` từ `core-api`.

## Cổng dịch vụ (Port):
* **HTTP Port:** 8001
