# 03 — Bảo mật Web, dữ liệu, file và secrets

## A. Đầu vào và injection

- Kiểm tra source của mọi dữ liệu (query/path/header/body, cookie, webhook, message queue, file, third-party response).
- SQL/NoSQL: prepared/parameterized queries; `ORDER BY`/table name chỉ lấy từ allowlist khi cần động; không đưa input vào SQL string interpolation.
- OS command: không chạy shell khi không cần, dùng argv tách bạch, tránh input trộn với command template.
- HTML/XSS: nhận biết framework autoescaping (React text JSX, Go `html/template`), chỉ báo lỗi nếu unsanitized user-controlled content đi vào DOM/HTML/JS nguy hiểm; xử lý rich HTML bằng sanitizer chuyên dụng.
- Header/redirect/CSV/template/log injection: escape/validate theo sink; không thay thế bằng “sanitize mọi string” chung chung.
- Parser: giới hạn độ dài/số mục/độ sâu/decompression ratio; kiểm tra type và content; không deserialise untrusted object bằng trình thực thi mã.

## B. HTTP Security

- Request body limit phải được **wire vào ingress và handler thực sự đọc body**; `MaxHeaderBytes` không giới hạn body. `http.MaxBytesReader` thường phù hợp; kiểm tra response 413 theo handler/framework.
- CORS quyết định browser có thể đọc phản hồi cross-origin, **không** thay cho authentication/authorization. Kiểm tra Origin allowlist và credentials policy theo use case; không áp CORS cho server-to-server một cách máy móc.
- CSRF cần khi cookie/ambient credentials và state-changing endpoint thực sự dễ bị browser cross-site request; đánh giá token / Origin / Fetch Metadata và SameSite. Bearer header tự đặt từ JS thông thường không yêu cầu anti-CSRF token cùng cách.
- CSP có ý nghĩa chủ yếu với HTML/browser content; pure JSON API không nên bị đánh giá P0 vì CSP rỗng. Khi có frontend, xem xét `default-src`, `script-src`, nonce/hash, `frame-ancestors`, report-only rollout.
- HSTS phải đặt tại lớp trả lời HTTPS mà browser thấy (proxy/edge hoặc app sau verified TLS), không bật bừa trong dev HTTP.
- Cookies: Secure, HttpOnly, SameSite, host-only/domain/path, expiration đúng chức năng.
- Error responses: trả mã/chuỗi an toàn; giữ chi tiết server-side log đã redacted; không công khai DSN, IP nội bộ, stack, secret.

## C. Files & storage

- Validate file size theo stream, header thật, MIME theo nội dung khi cần; reject zip-slip/tar traversal và symlink escape; chống zip bomb khi giải nén.
- Giới hạn concurrency và temp disk staging, cleanup trong cancel/failure.
- Storage local: path canonicalization/secure open APIs, không tin path input.
- S3/MinIO: tenant bucket/key scoping, signed URL TTL, không public objects theo mặc định, hạn chế content-type và metadata injection.
- Download: kiểm tra quyền đối tượng, không lộ internal filesystem path, Content-Disposition an toàn, đúng content type.

## D. SSRF đúng ngữ cảnh

Trước khi báo SSRF, xác minh cả **nguồn URL** và **đường gọi thực tế**:

- URL hardcode/config do operator kiểm soát: thường không phải user-controlled SSRF.
- URL từ input/webhook/database mà người dùng sửa được: kiểm tra `http/https` allowlist, host allowlist khi khả thi, DNS resolution và địa chỉ thực kết nối, redirect chain, private/loopback/link-local/cloud metadata, IPv6, proxy config, DNS rebinding.
- Không đưa blacklist IP toàn cục vào shared HTTP client nếu client còn cần gọi các internal services hợp pháp. Nên tách client dành cho URL không tin cậy hoặc chính sách theo use case.
- Không chạy thử SSRF vào cloud metadata hoặc host ngoài nếu chưa có quyền và môi trường kiểm thử phù hợp.

## E. Secrets, mã hóa, dữ liệu

- Scan `.env`, YAML, TF state, code, scripts, CI, history nếu có và được phép. Phân biệt placeholder/test key và secret thật; không in secret dù đã bị rò rỉ.
- Khuyến cáo rotate/revoke với secret thực đã commit; xóa git history đơn thuần không đủ.
- Dùng crypto libraries được bảo trì, CSPRNG (`crypto/rand` trong Go), không dùng tự chế encryption/hashing cho password.
- TLS certificate verification, trusted CA, no `InsecureSkipVerify`/disable verify ở production; exception yêu cầu risk acceptance rõ.
- Xem xét logging/redaction tại API, trace attributes, metrics labels, DLQ payload, audit events; hidden raw headers và error strings là nguồn rò rỉ.
- Encryption at rest, KMS và data retention tùy độ nhạy dữ liệu và môi trường, không coi absent config là lỗ hổng đã xác nhận khi storage provider bảo đảm ở tầng ngoài.

## F. Bằng chứng tốt

Với finding: đoạn code đúng `file:line`, nguồn dữ liệu thực, các guard trên đường đi, hậu quả, test chứng minh. Với gap: điều kiện áp dụng, vì sao cần, acceptance test. Với giới hạn: nêu đã kiểm tra những file/cấu hình nào và điều gì chưa kiểm tra.
