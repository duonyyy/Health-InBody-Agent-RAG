# Engineering Acceptance & Review Checklist

## Quy tắc phân loại

- **P0 confirmed**: Có reproduction hoặc reasoning chain kiểm chứng cho lỗi nghiêm trọng ngăn hoàn thành acceptance criteria; mô tả file/line, trigger, impact, minimal fix.
- **P1 confirmed**: Hành vi sai có bằng chứng nhưng không chặn triển khai trong phạm vi đã chốt; sửa theo ưu tiên.
- **Risk**: Có khả năng nhưng chưa tái hiện; không nâng thành bug confirmed.
- **Optional**: Cải tiến maintainability/performance/observability ngoài acceptance criteria; không chặn merge.
- **Preference**: Cá nhân thích cấu trúc khác, không tính lỗi.

## Checklist khi review một module

- [ ] Đọc code thật, tests và config; dẫn bằng chứng.
- [ ] Có yêu cầu / invariant / threat model được xác định.
- [ ] Chỉ pattern cần thiết; pattern không áp dụng có lý do.
- [ ] Data/resource lifetime đúng: session/connection/client/task.
- [ ] Transaction owner, commit/rollback rõ; outbox nếu có làm cùng transaction.
- [ ] Retry chỉ lỗi transient, bounded, không sinh duplicate side effect.
- [ ] Không `AsyncSession` share across concurrent tasks.
- [ ] Boundary HTTP/domain/infra không leak error/secret.
- [ ] Tests liên quan chạy, có output; thiếu tests được nêu rõ.
- [ ] Không thay public API, DB schema, deployment ngoài scope nếu chưa yêu cầu.

## Mẫu kết luận

```text
SUMMARY
- Scope: ...
- Verified findings: P0=0, P1=1 (...)
- Risks not proven: ...
- Tests: pytest -q → 28 passed / NOT RUN (environment missing)
- Changes: ...
- Decision: READY FOR IMPLEMENTATION (hoặc BLOCKED với P0 có evidence)
```

**Stop rule**: Không có P0 đã chứng minh trong phạm vi => dừng vòng review, bắt đầu/tiếp tục code theo kế hoạch. Không tiếp tục tìm ý kiến review vô hạn chỉ để đạt "10/10".
