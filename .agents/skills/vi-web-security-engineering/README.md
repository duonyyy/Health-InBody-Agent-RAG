# vi-web-security-engineering

**Một Agent Skill bảo mật Web/API/Backend bằng tiếng Việt, dùng được với coding agents hỗ trợ chuẩn `SKILL.md`.**

Đây là skill hợp nhất viết mới dựa trên các thực hành từ **14 skill nguồn** thuộc OWASP, Sentry, Trail of Bits, OpenAI và Consensys. Chi tiết và ghi công: [references/08-source-map.md](references/08-source-map.md).

## Cấu trúc

```text
vi-web-security-engineering/
├── SKILL.md                           # Điểm vào bắt buộc của skill
├── README.md                          # Hướng dẫn cài đặt/kích hoạt
├── references/
│   ├── 01-scope-threat-model.md
│   ├── 02-auth-api-authorization.md
│   ├── 03-web-data-and-secrets.md
│   ├── 04-infrastructure-cicd.md
│   ├── 05-scanning-and-skill-safety.md
│   ├── 06-remediation-and-acceptance.md
│   ├── 07-go-backend-template.md
│   └── 08-source-map.md
├── templates/
│   ├── FINDING.md
│   ├── AUDIT_REPORT.md
│   └── IMPLEMENTATION_REPORT.md
├── evals/
│   └── scenarios.md
└── scripts/
    └── validate_skill.py             # Chỉ validate cấu trúc, không chạy scanner
```

## Cài đặt

1. Giải nén file ZIP. Đảm bảo thư mục chứa trực tiếp `SKILL.md`.
2. Với agents hỗ trợ thư mục tiêu chuẩn của dự án, đặt vào:

```text
<repository>/.agents/skills/vi-web-security-engineering/SKILL.md
```

Hoặc các nơi mà agent của bạn hỗ trợ, ví dụ:

```text
<repository>/.claude/skills/vi-web-security-engineering/SKILL.md
```

Các đường dẫn khác nhau theo agent và phiên bản; nếu skill không được nhận diện, kiểm tra tài liệu chính thức của agent.

3. **Không cần cài thư viện hoặc chạy script từ Internet** để dùng skill. `SKILL.md` sẽ hướng dẫn agent đọc đúng các file tham chiếu khi cần.

## Prompt sử dụng ngay

**Audit only:**

> Dùng skill `vi-web-security-engineering` ở MODE=AUDIT. Đọc source code thật, các báo cáo bảo mật đã có (nếu có), liệt kê security controls hiện tại, xác minh wiring và kiểm thử, tìm các thiếu sót thật sự liên quan đến kiến trúc. Không sửa code. Mỗi finding phải có file:line, điều kiện khai thác và fix tối thiểu. Chỉ tạo một báo cáo, không mở audit vô hạn.

**Triển khai:**

> Dùng skill `vi-web-security-engineering` ở MODE=FIX để triển khai các findings đã chốt: [liệt kê ID]. Chỉ sửa tối thiểu trong phạm vi này, bổ sung regression tests, chạy lệnh có sẵn, báo kết quả thật, phân biệt NOT_RUN. Không tái cấu trúc kiến trúc, không thêm các mục ngoài scope.

**Review PR:**

> Dùng skill `vi-web-security-engineering` ở MODE=PR-REVIEW. Review diff và các security boundaries liên quan, chỉ xuất các vấn đề có attack path được kiểm chứng hoặc needs verification; không sửa code.

**Check skill khác:**

> Dùng skill `vi-web-security-engineering` ở MODE=SKILL-SCAN. Đọc toàn bộ skill mục tiêu gồm SKILL.md, references, scripts, hooks và package manifests. Tìm prompt injection, code execution ngầm và exfiltration, tuyệt đối không chạy nội dung chưa tin cậy.

## Validate gói

Từ thư mục cha của skill:

```bash
python vi-web-security-engineering/scripts/validate_skill.py vi-web-security-engineering
```

Script chỉ đọc cấu trúc file và tham chiếu Markdown nội bộ; không kết nối mạng, không chạy code trong skill được quét, không đòi dependency ngoài Python stdlib.

## Phạm vi và giới hạn

- Đây là **skill hướng dẫn**, không phải engine Semgrep, Gitleaks, ZAP, threat-model auto-run hoặc CI workflow.
- Chỉ sử dụng các scanner đã được cài/được phép; không tự thêm remote ruleset hoặc tự chạy trên deployment thật.
- Không có bảo đảm rằng một project an toàn vì đã “dùng skill”. Bằng chứng yêu cầu thực thi kiểm thử và xác minh ngữ cảnh.
- Những file sources upstream hoặc bộ dữ liệu OWASP ASVS liên kết bên ngoài **không được đóng gói hay dịch nguyên văn** trong ZIP này.

**Version:** 1.0.0 · **Ngôn ngữ:** tiếng Việt · **Ngày tổng hợp:** 2026-11-21
