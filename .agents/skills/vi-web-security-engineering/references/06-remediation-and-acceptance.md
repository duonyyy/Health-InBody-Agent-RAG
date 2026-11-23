# 06 — Sửa lỗi tối thiểu, regression tests, nghiệm thu hữu hạn

## Trước khi sửa

1. Xác nhận MODE=`FIX` hoặc người dùng đã chỉ định implementation.
2. Đọc finding được giao + source file hiện tại + tests + cách wire/app bootstrap.
3. Xác định phiên bản code để không sửa một bug đã được giải quyết.
4. Chọn **một** phương án fix nhỏ nhất giữ nguyên API khi có thể.
5. Khi fix đụng public behavior, liệt kê rủi ro breaking và test tương ứng.

## Nguyên tắc fix

- Thực hiện control tại điểm **thực thi hiệu lực**, không chỉ khai báo helper.
- Không tháo auth, tắt TLS, tắt tests, bỏ validation, hạ dependency security để qua CI.
- Không tự sinh auth module đầy đủ khi chưa có use case; chỉ xây protected route contract theo phạm vi được giao.
- Không gom unrelated refactor chung security fix. Không lập framework custom crypto/CSRF/JWT/validation.
- Không tự nhận root cause từ scanner pattern; chứng minh và tái test.

## Ví dụ tiêu chí nghiệm thu theo hạng mục

### Health endpoint

- Fake checker fail: error có string `internal-db-password` → response body **không chứa** chuỗi đó.
- Probe vẫn phân biệt 200/503, log chỉ chứa giá trị đã redacted.
- Nếu cần chi tiết health: chỉ trong authenticated/internal scope.

### Body size

- Handler thực sự đọc body. Request trong ngưỡng OK, request vượt ngưỡng phát hiện và trả response phù hợp (thường 413).
- Không buộc đọc cả body vào RAM, không vô tình chặn endpoints upload kích thước hợp lệ.

### Kubernetes probes

- Dùng manifest và router thực, đối chiếu route/method/port.
- Verify path và trạng thái; cập nhật một trong hai bên thay vì đăng ký dư aliases nếu không cần.

### Docker/Compose

- Image build; `id -u` trong API/worker khác 0; service startup OK; quyền ghi temp/storage OK.
- Host port mappings chỉ mở tương ứng nhu cầu, môi trường prod không dùng dev password.

### AuthN/AuthZ

- Anonymous/invalid token bị deny protected route.
- Request đúng actor nhưng khác owner/tenant bị deny tại service/repository thực.
- Admin-only operations yêu cầu quyền và kiểm tra property-level mutation.
- False-positive trường hợp public/health được phép hoạt động bình thường.

### CI

- YAML hợp lệ, workflow không thêm privileged token/trust paths, scanner kết quả được ghi thực.
- `go test`, `go vet`, relevant integration tests, and scanner khi sẵn có.

## Kết quả test — không tự tô xanh

| Test | Command | Exit | Kết luận |
|---|---|---|---|
| Unit | `go test ./...` | 0/1/NOT_RUN | PASS/FAIL/NOT_RUN |
| Integration | exact command | 0/1/NOT_RUN | ... |
| Docker | ... | ... | ... |
| Security scanner | ... | ... | ... |

Không giả mạo output hoặc suy diễn PASS từ mã nguồn. Khi chỉ có unit mocks, ghi runtime/integration unverified. Trường hợp thiếu tooling, chỉ ghi **LIMITED VERIFICATION** với lệnh để người khác chạy sau; không yêu cầu tạo công cụ mới.

## Xử lý lỗi ngoài phạm vi

- Nếu phát hiện ngay một lỗ hổng có tác động nghiêm trọng, ghi bằng chứng ngắn và đề nghị quyết định scope; không mở cuộc audit lần hai.
- Nếu non-blocking, đưa backlog; không trì hoãn nghiệm thu các việc đã chốt.
- Giới hạn 2 vòng sửa/test mỗi finding nếu không xuất hiện dữ kiện mới; sau đó báo `BLOCKED` gồm lý do kỹ thuật.

## Verdict

`ACCEPTED`: tất cả acceptance criteria áp dụng đã được kiểm chứng bằng chứng thật.

`ACCEPTED_WITH_LIMITATIONS`: code hoàn thành, chỉ còn các thử nghiệm cần môi trường không có hoặc một non-blocker đã ghi rõ và được chấp nhận.

`NOT_ACCEPTED`: còn lỗi bắt buộc, test không qua hoặc release blocker có bằng chứng.

**Không suy diễn application production readiness từ acceptance của một security milestone.**
