# Qdrant Vector Database — Health/InBody Agent RAG

Qdrant là cơ sở dữ liệu vector lưu trữ embeddings (1024 chiều từ mô hình BGE-M3) và payload metadata cho hệ thống RAG.

## Thông tin kết nối mặc định

- **HTTP API:** `http://localhost:6333` (hoặc `http://qdrant-db:6333` trong Docker network)
- **gRPC API:** `6334`
- **Web UI Dashboard:** `http://localhost:6333/dashboard`
- **Volume lưu trữ:** `qdrant_volume` (mount vào `/qdrant/storage`)

## Cấu hình

Cấu hình mặc định nằm tại `infra/qdrant/production.yaml`.

## Quy tắc vận hành (AGENTS.md)

1. Không xóa hoặc ghi đè collection đang phục vụ (`nmk_chatbot_active`).
2. Migration dữ liệu mới phải tạo collection version mới (ví dụ: `nmk_chatbot_collection_vYYYYMMDD_bge_m3_1024`) và chuyển alias `nmk_chatbot_active` sau khi kiểm thử đạt quality gate.
3. Import dữ liệu phải idempotent, dùng stable ID/content hash và có file manifest.
