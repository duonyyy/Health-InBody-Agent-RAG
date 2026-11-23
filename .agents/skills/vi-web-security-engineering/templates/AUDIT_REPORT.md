# Báo cáo Security Baseline — [Tên repo]

## 1. Phạm vi và điều kiện

- Mode: AUDIT
- Repo/commit/date:
- In-scope/out-of-scope:
- Loại repo: scaffold/library/app deployed:
- Deployment đã xác minh / giả định / không rõ:
- Tools chạy / không chạy:

## 2. Bản đồ boundaries

| Boundary | Entry point | Trusted actor | Asset | Control hiện có | Bằng chứng |
|---|---|---|---|---|---|

## 3. Security controls đang có

| Control | Trigger áp dụng | Status | Enforcement path | Test/run evidence | Tiếp theo |
|---|---|---|---|---|---|

Trạng thái: VERIFIED / IMPLEMENTED_UNVERIFIED / PARTIAL / MISSING_REQUIRED / NOT_APPLICABLE / UNKNOWN.

## 4. Findings (chỉ các phát hiện đủ chứng cứ)

| ID | Loại | Severity | Priority | Confidence | Bằng chứng | Fix tối thiểu |
|---|---|---|---|---|---|---|

Mỗi finding chi tiết theo `templates/FINDING.md`. Tách phần `NEEDS_VERIFICATION`, `OPTIONAL`, `NON_SECURITY_DEFECT`.

## 5. Scanning và giới hạn

| Tool | Command | Scope | Kết quả | NOT_RUN / PARTIAL / FAIL | Giới hạn |
|---|---|---|---|---|---|

## 6. Roadmap hữu hạn

| Task | Độ ưu tiên | Trigger áp dụng | Phụ thuộc | Minimal fix | Acceptance test |
|---|---|---|---|---|---|

## 7. Kết luận

- Lỗi phải xử lý trong phạm vi release đã chốt:
- Những việc chỉ cần khi có feature/triển khai mới:
- Những giả định còn chưa xác minh:
- Điều kiện dừng audit: đã/ chưa thỏa, nêu lý do.

**Không ghi tỷ lệ readiness tự tưởng tượng. Không khẳng định "production ready" nếu không có bằng chứng vận hành.**
