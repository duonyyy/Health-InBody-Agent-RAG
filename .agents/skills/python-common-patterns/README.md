# python-common-patterns — Agent Skill tiếng Việt (v1.0.0)

Bộ skill **tự biên soạn** theo đặc tả Agent Skills; tham khảo tài liệu chính thức Python, FastAPI, SQLAlchemy và các dự án cộng đồng ở `references/sources.md`. Không phải bản sao hay bản phát hành chính thức của wshobson/ECC/Cosmic Python.

## Cài đặt

Đặt nguyên folder `python-common-patterns/` (thư mục chứa `SKILL.md`) vào đường dẫn agent của bạn, ví dụ:

```bash
# Từ nơi đã giải nén, chạy trong repo Python của bạn:
mkdir -p .agents/skills
cp -R python-common-patterns .agents/skills/
# Đối với Claude Code, bạn cũng có thể đặt tại .claude/skills/python-common-patterns/
```

Trên Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Copy-Item -Recurse python-common-patterns .agents/skills/
```

Đường dẫn và cách kích hoạt có thể khác theo coding agent; kiểm tra tài liệu agent đang sử dụng. Cấu trúc gốc bên trong ZIP là `python-common-patterns/SKILL.md`.

## Dùng ngay

Prompt ngắn:

> Đọc `.agents/skills/python-common-patterns/SKILL.md`. Hãy inspect codebase Python/FastAPI của tôi, xác định problems có bằng chứng, chỉ chọn các common patterns cần thiết, implement theo từng bước nhỏ, chạy tests, và báo cáo theo output format trong skill. Không over-engineer.

Prompt audit không thay đổi code:

> Áp dụng `python-common-patterns` ở chế độ AUDIT ONLY. Đọc code liên quan, lập bảng current patterns, confirmed issues, optional improvements, chống phát sinh P0 không có bằng chứng. Không sửa file.

Prompt chỉ triển khai một module:

> Áp dụng `python-common-patterns` cho module `identity` hiện có; chỉ sửa phạm vi module, giữ API contract, ưu tiên DI + transaction ownership; repository/UoW chỉ khi cần. Viết tests và kết luận READY/BLOCKED có evidence.

## Cấu trúc

```text
python-common-patterns/
├── SKILL.md
├── README.md
├── references/          # 14 hướng dẫn ngắn, mỗi cái tập trung một việc
├── examples/
│   ├── fastapi-service/ # FastAPI + SQLAlchemy2 + pytest
│   ├── background-worker/# Python stdlib sqlite3, idempotent consumer demo
│   └── snippets/        # Ví dụ Strategy / Retry
├── scripts/             # Kiểm tra cấu trúc, metadata, Python syntax
└── evals/               # Tình huống đánh giá hành vi coding agent
```

## Chạy ví dụ FastAPI

Yêu cầu Python >=3.11. Thử nghiệm bằng môi trường ảo riêng:

```bash
cd python-common-patterns/examples/fastapi-service
python -m venv .venv
# Kích hoạt venv phù hợp hệ điều hành
python -m pip install -e '.[test]'
python -m pytest -q
python -m uvicorn app.main:app --reload
```

API docs ở `/docs`; mặc định dùng file SQLite `tasks.db` **chỉ để demo**. Với PostgreSQL thật: thêm driver, migrations (Alembic), config qua environment, readiness/health phù hợp; không dùng `create_all` như cơ chế migration production.

## Chạy ví dụ Worker và kiểm tra skill

```bash
cd python-common-patterns
python -m unittest discover -s examples/background-worker -p 'test_*.py' -v
python scripts/validate_skill.py
```

Script kiểm tra metadata, file references, compile syntax. Nó **không chứng minh** logic của từng pattern đúng production. Để kiểm tra đầy đủ, chạy các tests trong examples.

## Giới hạn chủ ý

- Không bao gồm full production queue worker, broker, durable outbox relay, distributed lock hoặc hệ thống Saga. Các chủ đề đó có thiết kế/checklist, không phải giải pháp copy-paste production.
- Các pattern là tùy chọn dựa trên nghiệp vụ, không phải checklist bắt buộc.
- Không tự động cài library vào repo thật.
- License MIT áp dụng cho **nội dung nguyên bản** trong bộ đóng gói này. Các nguồn bên ngoài giữ nguyên giấy phép của họ và chỉ được trích link.
