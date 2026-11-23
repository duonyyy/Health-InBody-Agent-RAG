# 08 — Nguồn tham khảo, phạm vi tổng hợp và quyết định hợp nhất

**Ngày đối chiếu:** 2026-11-21. Các liên kết là repo công khai có thể thay đổi sau ngày đó. Toàn bộ nội dung của skill hợp nhất này là **quy trình mới viết bằng tiếng Việt**, dựa trên các khái niệm/thực hành từ các nguồn đã đối chiếu; **không phải bản dịch đầy đủ, sao chép hay phân phối lại** các tài liệu gốc.

## A. 14 Agent Skills nguồn

| Đơn vị | Skill | Phần được tổng hợp |
|---|---|---|
| OWASP | [web-security-review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/web-security-review/SKILL.md) | Phân loại rủi ro Web Top 10, application mapping |
| OWASP | [api-security-review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/api-security-review/SKILL.md) | API inventory, BOLA, BOPLA, BFLA, rate, SSRF, unsafe API consumption |
| OWASP | [security-guidance](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/security-guidance/SKILL.md) | Secure-by-default theo loại tính năng và ASVS v5 index |
| OWASP | [secrets-scan](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/secrets-scan/SKILL.md) | Secret detection, redaction, rotation, historical exposures |
| OWASP | [iac-security-review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/iac-security-review/SKILL.md) | Kubernetes/IaC/IAM/network/container security |
| OWASP | [code-review-security](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/skills/code-review-security/SKILL.md) | Diff security review, CWE/ASVS mapping |
| Sentry | [security-review](https://github.com/getsentry/skills/blob/main/skills/security-review/SKILL.md) | High-confidence source→sink flow, false-positive discipline |
| Sentry | [gha-security-review](https://github.com/getsentry/skills/blob/main/skills/gha-security-review/SKILL.md) | CI attack chains, trigger/credentials/expression injection |
| Sentry | [skill-scanner](https://github.com/getsentry/skills/blob/main/skills/skill-scanner/SKILL.md) | Scanner chính Agent Skill trước khi dùng, injection/script/hooks |
| Sentry | [security-model](https://github.com/getsentry/skills/blob/main/skills/security-model/SKILL.md) | `SECURITY_MODEL.md`, invariants, reportability, scope |
| Trail of Bits | [semgrep](https://github.com/trailofbits/skills/blob/main/plugins/static-analysis/skills/semgrep/SKILL.md) | Scope, consent, metrics, scan partial/skipped, SARIF triage |
| OpenAI | [security-threat-model](https://github.com/openai/skills/blob/main/skills/.curated/security-threat-model/SKILL.md) | Threat model grounded in repo, assets, trust boundaries, abuse paths |
| OpenAI | [security-best-practices](https://github.com/openai/skills/blob/main/skills/.curated/security-best-practices/SKILL.md) | Detect stack, language/framework guidance, fixes và tests |
| Consensys | [repo-security-review](https://github.com/Consensys/repo-security-review/blob/main/SKILL.md) | Multi-phase repo audit, secret/CVE/OWASP/validation, report |

## B. Tài liệu quy trình OWASP liên kết từ các SKILL.md

- [OWASP Play: Web Top 10 Review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/plays/owasp-top10-web-review.md)
- [OWASP Play: API Security Review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/plays/api-security-review.md)
- [OWASP Play: Code Security Review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/plays/code-review-security.md)
- [OWASP Play: Secrets Scan](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/plays/secrets-scan.md)
- [OWASP Play: IaC Security Review](https://github.com/OWASP/secure-agent-playbook/blob/main/plugins/code-security-skills/plays/iac-security-review.md)

## C. Tiêu chuẩn chính thức

- [Agent Skills format](https://agentskills.io/specification): `SKILL.md`, YAML frontmatter, progressive disclosure.
- [OWASP ASVS 5.0](https://asvs.owasp.org/): các verification requirements có version, kiểm tra theo phạm vi thực tế.
- [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).
- [OWASP Web Top 10 (2021)](https://owasp.org/Top10/).
- [Go vulnerability management](https://go.dev/doc/security/vuln/).

## D. Quyết định có chủ ý của bản hợp nhất

1. **Không sao chép toàn bộ ASVS requirements:** `security-guidance` upstream có index trỏ đến nhiều `data/asvs/*.md`. Đây là nguồn để tham khảo khi cần; package này không tuyên bố đã sao chép/dịch mọi file data/asvs.
2. **Không nhúng runners của các nguồn:** Trail of Bits `run-scans.sh`, Sentry `scan_skill.py`, Consensys `setup.sh` và orchestration dành riêng cho Claude không có trong gói. Tránh auto-install/remote execution, cung cấp chính sách/tool selection và quy trình thủ công tương đương.
3. **Không ép nhiều vòng/subagents:** giữ cơ chế phân loại, bằng chứng, validation; bỏ yêu cầu tạo nhiều agent và scan vô hạn để phù hợp repo nhỏ.
4. **Không chép bản gốc:** tổng hợp ở mức ý tưởng, mẫu đầu ra và thực hành kỹ thuật; thuật ngữ OWASP/CWE là tên chuẩn.
5. **Không khẳng định mọi scanner tìm được mọi lỗi:** codebase/CI/runtime, environment-specific limitations luôn phải báo.
6. **Không biến thiếu feature thành lỗ hổng:** đặc biệt với Go reference template.
7. **Consent chi tiết:** scan có remote rule fetching, runtime, live target, cài tool, sửa code, deploy đều có ranh giới rõ. Audit read-only cục bộ không cần approval lặp lại khi người dùng đã yêu cầu.

## E. Ghi nhận giấy phép

Một số nguồn OWASP khai báo `CC-BY-4.0`; Sentry các skill và tài liệu có giấy phép riêng; các nguồn khác có thể có điều khoản khác nhau. Gói này ghi công và liên kết chính xác, **không tái phân phối nguyên văn** skill, references hoặc bundled scripts gốc. Người dùng muốn dùng nguyên bản nguồn nào nên kiểm tra LICENSE tại repository đó.
