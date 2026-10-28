# LLM Serving — Health/InBody Agent RAG

Hạ tầng phục vụ mô hình ngôn ngữ lớn (LLM) hỗ trợ các cấu hình sau:

## 1. Phương án 1: Ollama cục bộ trên máy Host (Mặc định)

Chạy ứng dụng Ollama trực tiếp trên máy host Windows/Linux.
Cấu hình trong `backend/.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_THINK=false
```

## 2. Phương án 2: Ollama Container hóa (Docker)

Khởi động Ollama bằng Docker:
```powershell
docker compose -f infra/llm/docker-compose.ollama.yml up -d
```
Tải model vào container:
```powershell
docker exec -it ollama-service ollama pull qwen2.5:3b
```
Cấu hình trong `backend/.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama-service:11434
OLLAMA_MODEL=qwen2.5:3b
```

## 3. Phương án 3: Remote LLM Server (Kaggle GPU / Cloud GPU qua Cloudflare Tunnel)

Khi máy local chỉ có 4GB VRAM (không đủ chạy mượt Qwen 8B song song với hệ thống), có thể chạy notebook:
`infra/llm/remote-llm-server-using-kaggle-gpu-ollama.ipynb`

* **Nguyên lý:** Kaggle cấp 2x Tesla T4 (16GB VRAM) miễn phí. Notebook cài đặt Ollama, pull model `qwen3:8b` (hoặc `qwen2.5:8b`), và expose endpoint ra ngoài qua Cloudflare Quick Tunnel (`trycloudflare.com`).
* **Kết nối:** Điền URL sinh ra từ tunnel vào `backend/.env`:
  ```env
  LLM_PROVIDER=ollama
  OLLAMA_BASE_URL=https://<your-subdomain>.trycloudflare.com
  OLLAMA_MODEL=qwen3:8b
  ```
* **Lưu ý an toàn:** Quick tunnel có tính chất tạm thời (ephemeral), tự động đổi URL sau mỗi session khởi động lại của Kaggle. Không dùng cho môi trường production lâu dài.
