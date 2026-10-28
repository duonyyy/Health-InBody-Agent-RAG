# Monitoring & Observability — Health/InBody Agent RAG

Hệ thống tích hợp giám sát phân tán (distributed tracing), tính toán token và đánh giá chất lượng câu trả lời thông qua **Langfuse**.

Mã nguồn thu thập dữ liệu nằm tại [`backend/src/core/observability.py`](../../backend/src/core/observability.py).

## 1. Tùy chọn 1: Sử dụng Langfuse Cloud (Khuyến nghị cho phát triển nhanh)

1. Đăng ký tài khoản miễn phí tại [cloud.langfuse.com](https://cloud.langfuse.com).
2. Tạo project và lấy API keys (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`).
3. Điền vào `backend/.env`:
   ```env
   LANGFUSE_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=https://cloud.langfuse.com
   LANGFUSE_ENV=development
   LANGFUSE_MASK_HEALTH_PII=true
   ```

## 2. Tùy chọn 2: Chạy Langfuse Self-Hosted cục bộ (Offline / On-premise)

Nếu cần chạy hoàn toàn nội bộ không phụ thuộc Internet:

```powershell
docker compose -f infra/monitoring/docker-compose.monitoring.yml up -d
```

- Bảng điều khiển giao diện: `http://localhost:3000`
- Tạo tài khoản admin lần đầu trên giao diện và tạo project mới để lấy API keys.
- Trong `backend/.env`:
  ```env
  LANGFUSE_ENABLED=true
  LANGFUSE_PUBLIC_KEY=pk-lf-...
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_BASE_URL=http://langfuse-server:3000
  LANGFUSE_ENV=local
  LANGFUSE_MASK_HEALTH_PII=true
  ```

## 3. Quy tắc an toàn dữ liệu sức khỏe (Healthcare PII Protection)

Theo quy định trong `AGENTS.md`:
- `LANGFUSE_MASK_HEALTH_PII=true` luôn được bật mặc định.
- Tên người dùng thật, email, CCCD, số đo InBody nhạy cảm và bệnh lý cụ thể bị ẩn danh hoặc hash bằng SHA-256 (`LANGFUSE_ID_SALT`) trước khi truyền sang hệ thống giám sát.
