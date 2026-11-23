# [SEC-001] Tên finding

- **Loại:** CONFIRMED_VULNERABILITY / MISSING_REQUIRED / NEEDS_VERIFICATION / OPTIONAL / NON_SECURITY_DEFECT
- **Trạng thái:** OPEN / FIXED / BLOCKED / NOT_APPLICABLE
- **Severity:** Critical / High / Medium / Low / None
- **Remediation priority:** P0 / P1 / P2 / P3 / Backlog
- **Confidence:** HIGH / MEDIUM / LOW
- **Phạm vi & điều kiện:** repo, version, local/staging/prod, URL/route nếu có.
- **Vị trí:** `path/to/file.ext:Lx-Ly` (phải xác minh lại với code).

## Bằng chứng

Đoạn code/cấu hình đã redacted, hoặc lệnh test và kết quả thật. Không hiển thị secret.

## Đường tấn công / Cơ chế lỗi

1. Đối tượng tấn công và quyền thực tế.
2. Entry point và input do ai kiểm soát.
3. Các bước dataflow source→sink và security controls liên quan.
4. Điều kiện cần, điểm bypass, tác động.
5. Giới hạn chưa xác minh, nếu có.

## Vì sao quan trọng

- Asset nào bị ảnh hưởng?
- Khả năng khai thác / blast radius trong môi trường này?
- Có biện pháp giảm thiểu hiện có không?

## Phương án xử lý tối thiểu

Nêu file thay đổi, control hiệu lực, rủi ro hồi quy; không mở rộng kiến trúc.

## Regression test và tiêu chí nghiệm thu

- Test/input cần chạy:
- Expected outcome:
- Actual outcome: PASS / FAIL / NOT_RUN
- Lệnh thực thi, môi trường:

## Phân biệt với sở thích thiết kế

Giải thích vì sao đây là bắt buộc, không chỉ một phương án khác cũng đúng.
