# Nguồn tham khảo đã đối chiếu qua web (23/11/2026)

Đây là nội dung nguyên bản tổng hợp, biên soạn bằng tiếng Việt; không sao chép nguyên văn hoặc phân phối lại code của các dự án bên ngoài. Links dưới đây là nguồn tham khảo kiến trúc và API. Khi dùng hãy kiểm tra version đang chạy trong dự án.

## Đặc tả Agent Skills

- Agent Skills Specification (frontmatter, `name`/`description`, progressive disclosure): https://agentskills.io/specification

## Design & kiến trúc

- wshobson — Python Design Patterns skill: https://github.com/wshobson/agents/blob/main/plugins/python-development/skills/python-design-patterns/SKILL.md
- affaan-m/ECC — Python Patterns skill: https://github.com/affaan-m/ECC/blob/main/skills/python-patterns/SKILL.md
- Architecture Patterns with Python (Cosmic Python): https://github.com/cosmicpython/book
- Companion code: https://github.com/cosmicpython/code

## Tài liệu chính thức

- Python asyncio tasks / TaskGroup / cancellation: https://docs.python.org/3.14/library/asyncio-task.html
- FastAPI dependencies with yield: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- FastAPI multi-file applications/APIRouter: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy 2.0 transaction scopes: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- SQLAlchemy session concurrency: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- pytest fixtures: https://docs.pytest.org/en/stable/reference/fixtures.html

## Giới hạn nguồn

Không xem một Agent Skill cộng đồng là bằng chứng về production correctness. Những quyết định liên quan ACID, data consistency, HTTP semantics và async lifecycle phải được đối chiếu với tài liệu framework và tests trên codebase thật.
