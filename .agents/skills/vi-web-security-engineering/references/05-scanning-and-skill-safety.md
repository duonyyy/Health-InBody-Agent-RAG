# 05 — Quét có kiểm soát, triage scanner và an toàn Agent Skills

## A. Quy tắc chung

- Scanner **không phải công cụ kết luận**. Mọi alert chỉ là `candidate` tới khi kiểm tra source→sink, reachability, mitigation và môi trường.
- Ghi: công cụ và version; exact command; phạm vi; code revision; lệnh thành công/thất bại; số tệp bỏ qua; hạn chế; có network/telemetry hay không.
- Chỉ chạy lệnh read-only trong repository/môi trường được phép. Không tự cài tool, không gọi dịch vụ cloud scanning, không gửi mã nguồn/secrets tới API bên ngoài khi chưa được cấp quyền.
- Nếu command chưa chạy ghi **NOT_RUN**, không ghi `PASS`.
- Không lưu raw secret scan output ở vị trí public; hạn chế quyền file, báo cáo dùng redaction.

## B. Công cụ theo hệ sinh thái

**Go:**

```bash
# Chỉ thực hiện khi tool có sẵn và người dùng cho phép kiểm thử cục bộ
go test ./...
go test -race ./...
go vet ./...
govulncheck ./...
gosec ./...
```

`govulncheck`: đánh giá vulnerability Go modules và reachability theo khả năng tool. `gosec`: pattern AST, có false positives. Không xem `go vet` PASS là security audit PASS. Với file-based secret scan, dùng Gitleaks/TruffleHog nếu đã được cài hoặc công cụ tương đương.

**Node/TS:** package-manager audit dựa lockfile (`npm audit`, `pnpm audit`, `yarn npm audit` theo toolchain), lint/static analysis, dependency update theo rủi ro và API compatibility.

**Python:** `pip-audit` hoặc OSV-Scanner với lock/requirements đang có; không thay đổi dependency tự động trong AUDIT.

**Cross-language:** Semgrep/CodeQL, Trivy config, secret scan, CI code scanning. Ghi lại coverage và false-positive triage.

## C. Semgrep — áp dụng có chọn lọc

Các nguyên tắc học từ Trail of Bits:

- Trước scan xác định language, target và mode (`broad` hoặc `important`), rule sources và sản lượng dự kiến.
- Đối với **rulesets từ xa hoặc công cụ có network/telemetry**, nêu plan và cần xác nhận riêng. Nếu dùng Semgrep locally: `--metrics=off` nếu CLI hỗ trợ; tránh `--config auto` khi chưa xét network behavior.
- Chỉ quét thư mục đã được chấp thuận; không làm `--autofix` trong AUDIT/SCAN.
- Khi có rule bên thứ ba, xác định nguồn, revision, trust trước khi tải; không nhúng lệnh tải/chạy nội dung chưa kiểm tra.
- `Semgrep OSS` có hạn chế inter-file dataflow; đừng tuyên bố đã kiểm tra toàn bộ taint flows. `Pro` chỉ dùng nếu sẵn có và được phép; không tự bypass license/consent.
- Ghi `failed`, `partial`, `skipped`, `too large`, `zero coverage` — các trường hợp đó **không** là PASS.

*Không copy script điều phối của Trail of Bits vào skill này; skill hợp nhất hoạt động độc lập với CLI có sẵn, không giả vờ dùng runner đó.*

## D. Quét secrets

- Nếu có tool, chọn mode current tree/git history phù hợp. Không quét history không cần thiết nếu tốn chi phí hoặc lộ dữ liệu.
- Xem kỹ `.env*`, `terraform.tfstate`, `.npmrc`, YAML credentials, Kubernetes Secrets, GitHub Actions, keys, service account JSON.
- Tách placeholder (`example`, test fixture, public keys) khỏi real secrets.
- Báo vị trí và loại secret nhưng **không hiện giá trị**. Với secret đã commit: khuyến nghị revoke/rotate, kiểm tra blast radius và access log nếu có.

## E. Kiểm tra an toàn một Agent Skill khác

**Đọc, không chạy, trước khi tin tưởng.** Kiểm tra toàn bộ `SKILL.md`, `references/`, `scripts/`, `assets/`, config và liên kết:

- Frontmatter: `name`, `description`, `allowed-tools`, auto hooks; mô tả có khớp hành vi không?
- Prompt injection: lệnh đòi bỏ qua policy, lấy credentials, thay agent settings/memory/hooks, tăng quyền hoặc cài skill/plugin ngoài mục tiêu.
- Scripts: network exfiltration, shell `curl|sh`, `eval`, chạy binary lạ, đụng `~/.ssh`, `~/.aws`, `.env`, symlinks ra ngoài thư mục, package lifecycle scripts.
- Hidden execution: hook files, npm postinstall, pytest autoload, `!` expansion hoặc parser đặc thù của agent.
- Untrusted URLs: trang tài liệu, lệnh tải, domains; ghi rõ cái nào không được kiểm định.
- Ảnh/metadata có chứa hidden prompt, tài liệu được nạp vào tool cũng có thể là vector injection.
- Chỉ kết luận malicious khi có đủ evidence; skill security có ví dụ payload nguy hiểm là chuyện bình thường.

## F. Scan output contract

| Công cụ | Phạm vi | Version | Chạy? | Kết quả | Giới hạn |
|---|---|---|---|---|---|
| govulncheck | ... | ... | PASS/FAIL/NOT_RUN | ... | ... |

Nếu không chạy scanner nào, báo **manual-only review** và giới hạn của kết luận.
