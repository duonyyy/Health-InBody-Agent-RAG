# Container Security Hardening — kiểm tra nhiều lớp

## 1. Threat model trước khi hardening

Xác định dữ liệu nhạy cảm, network trust boundary, process privileges, registries, CI secrets, volume mounts, host Docker daemon, cấu hình production. Không bật một tính năng hardening chỉ vì “best practice” nếu làm hỏng chức năng mà chưa có phương án thay thế và kiểm thử.

## 2. Checklist Dockerfile

- Base image được duy trì, tương thích CGO/CA/TZ; tránh `latest`; pin digest trong pipeline cần reproducibility và lên lịch cập nhật.
- Multi-stage, không compiler/source/token trong final image; `.dockerignore` không đưa `.env`, keys, private files vào build context.
- `USER` không-root; `COPY --chown` nếu quyền file cần điều chỉnh; không dùng `chmod 777`.
- Không để mật khẩu trong `ARG`, `ENV`, `RUN echo ...`, cache hoặc build log. BuildKit `RUN --mount=type=secret` / `--mount=type=ssh` khi thật sự cần.
- Exec-form `ENTRYPOINT`, xử lý signals và không cần shell trong runtime.
- OCI labels, SBOM, attestation/provenance phù hợp yêu cầu quản trị; không đánh đồng một SBOM với sự an toàn runtime.

## 3. Checklist runtime/Compose

- `privileged: true` và mount `/var/run/docker.sock`: mặc định không chấp nhận; phải được user chấp thuận với threat model rõ.
- `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, root FS `read_only: true` nếu tương thích.
- Chỉ cấp `tmpfs`/volume cho chỗ cần ghi, phân quyền POSIX thực tế, không mở host networking tùy tiện.
- Không publish DB/Redis/queue internet; ràng buộc cổng app/dev về `127.0.0.1` nếu phù hợp.
- Giới hạn process/memory và logging để hạn chế abuse, nhưng test với tải thực tế.
- Quản lý runtime secrets qua cơ chế phù hợp: Compose secrets, cloud secret manager hoặc Kubernetes secrets + mã hóa/quyền truy cập nếu đang dùng K8s.

## 4. Quét và đảm bảo supply chain

Các lệnh dưới đây là **tùy chọn** và chỉ dùng khi có tool/image đã được phê duyệt; một số công cụ có thể tải database qua mạng:

```bash
# Lint Dockerfile nếu cài hadolint
hadolint Dockerfile

# Scan CVE trên image đã build, không phải substitute cho image config review
trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1 app:check

# Thêm scan secrets nếu phù hợp với phạm vi dữ liệu
trivy image --scanners secret app:check

# Sinh SBOM bằng công cụ được chọn
syft app:check -o cyclonedx-json > sbom.json

# Xác minh chữ ký với identity/policy/registry thật (không bỏ verify)
# cosign verify --certificate-identity ... --certificate-oidc-issuer ... IMAGE@sha256:...
```

- Phân biệt `vulnerability detected`, `fix available`, `unfixed`, `false positive` theo evidence và SLA. Không tắt toàn bộ policy để vượt CI.
- Ký image bằng Cosign/attestation là công việc release riêng, không tự bật `push` hoặc ký bằng key chưa được người dùng cấp.
- Kiểm tra SBOM/provenance theo registry và action versions được dự án lựa chọn. Không lưu token/action output vào log.

## 5. Kiểm tra tự động đi kèm

```bash
bash <skill-dir>/scripts/check-security.sh Dockerfile compose.yaml
# Quét image chỉ khi người dùng chủ động muốn:
bash <skill-dir>/scripts/check-security.sh Dockerfile compose.yaml --image app:check
```

Script chạy static checks cơ bản, **không phải SAST/CSPM toàn diện**, không thay Trivy/Hadolint. Khi `--image` được yêu cầu mà không có Trivy, thoát code 2 (không hoàn thành scan).

## 6. Báo cáo an toàn

Báo cáo cần: phát hiện/mức độ/tác động/bằng chứng, bản sửa nhỏ nhất, test sau sửa, hạn chế, các ngoại lệ đã được phê duyệt. Không tiết lộ secret trong báo cáo.

**Nguồn**: https://docs.docker.com/build/building/secrets/ ; https://docs.docker.com/reference/build-checks/ ; https://github.com/sickn33/agentic-awesome-skills/tree/main/skills/container-security-hardening
