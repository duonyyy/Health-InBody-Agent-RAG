# FIX-01 — Validation số đo trước fallback và side effect

Ngày: 2026-11-17. Base revision: `a024500` + patch working tree, chưa commit.

**SOURCE_READY, VERIFIED_TEST; VERIFIED_RUNTIME chỉ trên HTTP test biệt lập. Chưa deploy container sản phẩm.**

## Thay đổi

- `backend/src/health/validation.py` (mới) sở hữu parsing/validation xác định, không import agents/FastAPI/DB; `agents/parsing.py` giữ export cũ và delegate vào owner này.
- Giữ dấu âm ASCII/Unicode minus và đơn vị, đọc đúng 1m70; không đổi 2cm thành 2m.
- Không lấy lượng tăng/giảm, mục tiêu hoặc lịch sử có từ khóa nhận diện làm số đo hiện tại. Số đo mâu thuẫn/khoảng không rõ được yêu cầu xác nhận, không chọn tùy tiện. Đây là parser theo mẫu ngôn ngữ, không phải bộ hiểu mọi câu tiếng Việt.
- Miền hợp lệ: 0 < kg <= 500; 30 <= cm <= 300; 0 <= PBF <= 100; 0 <= visceral level <= 100. Zero PBF/visceral vẫn hợp lệ theo schema.
- `agents/graph.py` kiểm tra sau urgent nhưng trước greeting/tools/fallback; `memory/chat.py` kiểm tra trước DB cho cả HTTP và worker.
- `api/app.py` kiểm tra chat async trước create_task/apply_async, trả 422 với code=invalid_health_input và detail tiếng Việt an toàn. `api/personalization.py` và sync catch cho exception đi qua, không biến thành 500/503.
- Không log/nhắc lại raw số đo sai trong exception. Auth/user_id check vẫn đứng trước validation. Urgent đứng trước validation/DB/queue/provider.

## Bằng chứng test

- RED trước sửa: `--maxfail=3` cho thấy -72kg/−72kg thành +72kg và -170cm thành +170cm.
- Sau bản sửa cuối: **217 unit + 3 integration = 220 passed**, 2 cảnh báo FastAPI on_event deprecated cũ, 11.89s. Python host 3.13, SQLite, LLM none, embedding tắt.
- `backend/tests/unit/test_health_input_validation.py` mới có 59 ca: 12 input invalid x 3 mode chat, signed parsing, delta/target/history, ambiguity, zero, thiếu dữ liệu, không fallback sang số đo cũ, worker trước DB và urgent bypass. Test mock gây lỗi ở DB/queue/provider xác nhận thứ tự.

```powershell
$env:PYTHONPATH=(Resolve-Path backend/src).Path
$env:DATABASE_URL='sqlite://'
$env:LLM_PROVIDER='none'
$env:CUSTOM_EMBEDDING_ENABLED='false'
python -B -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider
```

- AST feature_version Python 3.10 và whitespace của 7 file Python sửa/thêm đạt; không thay cho interpreter/image Python 3.10.
- `git diff --check -- backend` đạt. README.md sửa sẵn được giữ nguyên.

## HTTP thật biệt lập

Uvicorn process mới trên 127.0.0.1/cổng động, SQLite in-memory, development identity tổng hợp, BM25 autoload/embedding/Zep tắt, LLM none. Không đụng container/collection/volume. Process terminate + wait trong finally sau test.

| Yêu cầu | HTTP | Kiểm thêm |
|---|---|---|
| /agent/answer BMI -72kg/170cm | 422 | invalid_health_input, detail chuỗi |
| /chat/complete sync cùng input | 422 | Cùng contract lỗi |
| /chat/complete async cùng input | 422 | Chặn trước queue |
| /agent/answer -1m70/72kg | 422 | Không mất dấu âm |
| /agent/answer PBF 101% | 422 | Không chạy inference |
| /agent/answer đau ngực + khó thở + -72kg | 200 | urgent_safety |
| /agent/answer BMI 72kg/170cm | 200 | inbody_tools, BMI 24.91 |
| /agent/answer invalid không auth | 401 | Auth vẫn ưu tiên |

**8/8 HTTP checks đạt, server thử nghiệm đã dừng.** Không suy ra product container đã nhận patch.

## Giới hạn và rollback

- Docker ps lần kiểm tra cuối báo Internal Server Error từ docker_engine API. Chưa kiểm image Python 3.10, PostgreSQL/Celery broker thật hoặc rollout sản phẩm.
- F2 lời chào/medical caution, dependency Next.js, frontend/CORS và hạ tầng thuộc FIX-02–05; chưa sửa trong đợt này.
- Không chạy provider có phí/benchmark corpus thật, không commit/push/migrate/restart container.
- Rollback chỉ patch FIX-01 và các dòng tiến độ liên quan; không có schema/data migration. Không reset working tree hoặc xóa thay đổi khác.
