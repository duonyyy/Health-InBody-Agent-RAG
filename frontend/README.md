# Frontend - Health/InBody Agent RAG

Frontend Streamlit cho backend FastAPI Health/InBody Agent RAG. Flow chính là multi-agent chat qua `/chat/complete`: người dùng hỏi tự nhiên, backend tự định tuyến và tự gọi tool phù hợp.

## Tính năng chính

- Chat tiếng Việt qua `POST /chat/complete` với `sync_request=true`.
- Gửi `history` hội thoại để backend định tuyến follow-up tốt hơn.
- Tab `Dev tool test` chỉ để kiểm thử trực tiếp các endpoint tool khi debug backend.
- Search tab gọi `POST /search` để kiểm tra corpus Health/InBody đã index.
- System tab hiển thị `/health` và thông tin phiên.

## Lưu ý contract backend

Backend hiện tại chưa có endpoint upload/parse ảnh hoặc PDF InBody. Vì vậy frontend không hiển thị upload giả. Người dùng nhập chỉ số InBody bằng văn bản trong chat; agent backend sẽ tự quyết định khi nào cần gọi tool BMI, PBF, mỡ nội tạng, dinh dưỡng, lịch tập hoặc safety.

Endpoint chính:

| Chức năng | Endpoint |
| --- | --- |
| Chat | `POST /chat/complete` |
| Health check | `GET /health` |
| Agent tools | `GET /agent/tools` |
| Search | `POST /search` |
| Dev test BMI | `POST /tools/bmi` |
| Dev test PBF | `POST /tools/pbf` |
| Dev test mỡ nội tạng | `POST /tools/visceral-fat` |
| Dev test dinh dưỡng | `POST /tools/nutrition` |
| Dev test lịch tập | `POST /tools/training` |
| Dev test safety | `POST /tools/safety` |

## Cài đặt và chạy local

```bash
pip install -r requirements.txt
set API_BASE_URL=http://localhost:8000
streamlit run chat_interface_new.py --server.port 8051
```

PowerShell:

```powershell
$env:API_BASE_URL = "http://localhost:8000"
streamlit run chat_interface_new.py --server.port 8051
```

## Chạy Docker

Frontend mặc định gọi backend trong Docker network tại:

```env
API_BASE_URL=http://chatbot-api:8000
```

Chạy từ thư mục `frontend/`:

```bash
docker compose up --build
```

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `API_BASE_URL` | `http://chatbot-api:8000` | URL backend FastAPI |
| `BOT_ID` | `health-inbody-agent` | Bot id gửi tới backend |
| `USER_ID` | `demo-user` | User id mặc định |
| `REQUEST_TIMEOUT` | `120` | Timeout request chat/tool |

## Files

- `chat_interface_new.py`: giao diện chính đã cập nhật theo backend Health/InBody.
- `chat_interface.py`: giao diện legacy tối giản, chỉ giữ để tương thích cũ.
- `config.toml`: cấu hình Streamlit.
- `entrypoint.sh`: entrypoint Docker chạy `chat_interface_new.py`.
