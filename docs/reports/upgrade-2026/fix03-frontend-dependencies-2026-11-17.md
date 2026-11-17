# FIX-03 — Vá dependency frontend và khôi phục build thành công

Ngày: 2026-11-17. Base revision: `42e717f` + patch working tree.

**SOURCE_READY, VERIFIED_TEST; VERIFIED_RUNTIME chỉ HTTP frontend biệt lập trên host. Chưa build/deploy container sản phẩm.**

## Baseline và phạm vi

- Trước sửa, `npm audit --json` exit 1: 8 mục moderate, 0 high/critical. Đây là các package trực tiếp/bắc cầu của hai advisory, không phải tám lỗ hổng độc lập đã chứng minh khai thác.
- `npm run build` trên Next 16.4.3 compile/TypeScript/prerender 4/4 xong nhưng exit 1 tại `SecurityFatalError`. Không tính việc prerender xong là build đạt.
- Next advisory [GHSA-mfr8-8qww-v76h](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h) nêu dải ảnh hưởng 16.3.0–16.4.4, vá từ 16.4.5. Chưa thấy `use cache`/`unstable_cache` trong frontend/src; không khẳng định đã tái hiện rò rỉ dữ liệu.
- minimatch advisory [GHSA-g3hv-75wg-m249](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249) nêu lỗi amplification trong xử lý glob; bản 10.2.6 có trong chuỗi lint cũ, vá từ 11.0.1. Chưa chứng minh khai thác qua HTTP của dự án.
- Đọc frontend/AGENTS.md và tài liệu nâng cấp đi kèm node_modules/next/dist/docs trước thay đổi. Kiểm tra registry xác nhận 16.4.6 là patch có sẵn trong nhánh 16.4 và peer React hiện tại tương thích.

## Thay đổi

| Package | Trước | Sau | Cách cập nhật |
|---|---|---|---|
| next | 16.4.3 | 16.4.6 | Pin chính xác trong package.json |
| eslint-config-next | 16.4.3 | 16.4.6 | Pin cùng phiên bản Next, giữ devDependency |
| typescript-eslint và nhóm @typescript-eslint | 8.72.0 | 8.73.0 | Cập nhật dependency owner trong major 8, ghi bằng lockfile |
| minimatch dưới typescript-estree | 10.2.6 | 11.0.9 | Owner 8.73.0 khai báo ^11.0.1; không ép override major |

Chỉ sửa `frontend/package.json` và `frontend/package-lock.json` cùng tài liệu tiến độ. Lockfile cập nhật thêm các package @next/env/SWC/plugin tương ứng, dependency nội bộ của typescript-eslint và một số patch của ignore/brace-expansion/semver. minimatch 11 thêm @isaacs/nonrecursive-glob-match. Các consumer minimatch 3.1.5 khác không nằm trong advisory đang xử lý và vẫn giữ nguyên.

React/react-dom giữ 19.3.0, ESLint giữ 9.39.5. Không thêm dependency trực tiếp typescript-eslint/minimatch, không dùng overrides, audit fix --force, codemod hoặc tắt security check. Không đổi next.config.ts, component, auth/API URL, Dockerfile hay corpus.

## Bằng chứng kiểm chứng

Môi trường host Windows, Node v22.23.2, npm 10.9.8. Lệnh chạy tại frontend/:

| Lệnh | Kết quả |
|---|---|
| npm install --save-exact next@16.4.6 eslint-config-next@16.4.6 | Exit 0; còn 7 moderate trước khi cập nhật owner lint |
| npm update typescript-eslint | Exit 0; audit về 0 |
| npm ci | Exit 0, cài sạch; SHA256 lockfile không đổi |
| npm run lint | Exit 0, không lỗi/cảnh báo lint |
| npx --no-install tsc --noEmit | Exit 0 |
| npm run build | Exit 0; Next 16.4.6/Turbopack; prerender 4/4; không SecurityFatalError |
| npm audit --json sau npm ci | Exit 0; vulnerabilities rỗng, tổng 0 |
| npm ls các dependency liên quan | Exit 0; không invalid peer dependency trong cây được kiểm |
| git diff --check cho frontend/docs | Exit 0 |

Lockfile SHA256 sau nâng và sau npm ci: `6315110FAC2EE5A6DF8A479E9D4398633DCC2BEA439F27CA226C25D2BB0F61B1`.

Không thêm test mô phỏng chỉ để kiểm tra version string. Cài sạch, lint, typecheck, security audit, production build và HTTP asset smoke là kiểm chứng cho thay đổi dependency này. Backend không đổi nên không chạy lại suite backend trong FIX-03.

## HTTP production build biệt lập

Khởi chạy local Next CLI `next start --hostname 127.0.0.1 --port <cổng động>` bằng Node từ build mới, NODE_ENV=production. Không thay server đang phục vụ, không gọi API/backend/provider và không tạo dữ liệu sức khỏe.

**5/5 checks đạt:** GET / trả 200, HTML chứa BodyWise và lang=vi; một JS chunk và một CSS stylesheet thực sự được HTML tham chiếu đều trả 200 với content type đúng và nội dung không rỗng; favicon SVG trả 200; đường dẫn không tồn tại trả 404. Server thử nghiệm đã terminate + wait sau kiểm tra.

Đây là bằng chứng server/asset qua HTTP thật, chưa chạy JavaScript/hydration hoặc tương tác trong browser, chưa phải E2E chat/OCR/auth với backend.

## Hạn chế và bàn giao

- npm ci có cảnh báo package ESLint 9.39.5 đã hết hỗ trợ. Audit hiện không báo advisory cho bản này; nâng ESLint major là đợt tương thích riêng, không tự mở rộng FIX-03.
- Audit 0 chỉ mô tả registry tại lúc kiểm tra, không chứng nhận toàn ứng dụng an toàn hoặc production-ready.
- Chưa build image Linux/Alpine, chưa deploy container/browser E2E hoặc chạy FIX-04/05. Frontend API URL/CORS/network vẫn thuộc FIX-04.
- README.md sửa sẵn được giữ nguyên; không stage/commit/push hoặc restart container trong lượt này.
- Rollback bằng patch hai file dependency và dòng tài liệu FIX-03, rồi npm ci; không reset working tree hoặc phục hồi dependency cũ chỉ để bỏ security gate. Không có schema/data migration.
