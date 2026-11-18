# Báo cáo Triển khai Đợt 1: Hợp đồng Dữ liệu & Cảnh báo An toàn Frontend (R04, R05, R10, R11)

- **Ngày thực hiện:** 2026-11-17 – 2026-11-18
- **Tham chiếu đánh giá:** `docs/reports/upgrade-2026/project-reassessment-2026-11-17.md` và `docs/reports/upgrade-2026/project-reassessment-2026-11-17-evidence.json`
- **Branch / HEAD baseline:** `main` @ `5c8124c`
- **Trạng thái bàn giao:** **Đợt 1 source-ready, chưa deploy.**

---

## 1. Phạm vi & Ràng buộc tuân thủ

- **Các vấn đề xử lý trong đợt 1:** `R04`, `R05`, `R10`, `R11` hoàn toàn ở lớp frontend contract/adapter/type/component (xác minh đối chiếu từ backend producers tại `backend/src/api/app.py`, `personalization.py`, `memory.py`, `persistence/schemas.py`, `harness/layers/citation_checker.py`).
- **Ràng buộc đã tuân thủ:**
  - Giữ nguyên các thay đổi có sẵn của người dùng (`README.md`, 2 tệp báo cáo reassessment).
  - Không thay đổi kiến trúc backend gộp (`backend/src`), không mở migration/schema DB, không chỉnh retrieval/graph/OCR/provider.
  - Không chạy bulk import, không restart/rebuild container, không stage/commit/push Git.

---

## 2. Chi tiết thay đổi theo từng hạng mục

### 2.1 R04 — Giữ đúng ý nghĩa dữ liệu thiếu, số 0 thực và phân loại PBF theo giới tính sinh học

- **Boundary numeric & partial records (`frontend/src/lib/api.ts`, `frontend/src/types/index.ts`):**
  - Thêm `parseOptionalNumeric(val)`: phân biệt rõ `null`, `undefined`, chuỗi rỗng `""`, chuỗi không phải số (trả `undefined`) với số `0` thực và chuỗi số hợp lệ (ví dụ `"68.5"` -> `68.5`, `0` -> `0`).
  - `InBodyMeasurement`: chuyển `weight_kg` và `height_cm` sang optional để khớp `MeasurementBase` của backend.
  - `fetchInBodyMeasurements` và `saveInBodyMeasurement`: giữ các bản ghi từng phần (chỉ cần có `id`, `measured_at` và ít nhất 1 chỉ số hợp lệ), không dùng `Number(null) === 0` để bù dữ liệu thiếu.
- **Phân loại PBF & mỡ nội tạng (`frontend/src/lib/classifiers.ts`):**
  - `classifyPbf(pbf, sex)`: nhận `sex_at_birth` từ profile (`female`, `male`, `intersex`, `prefer_not_to_say`, `null`/`undefined`). Không mặc định `'male'` khi thiếu hoặc không xác định; trả về `status: 'unknown'` với nhãn `Chưa xác định chuẩn giới tính`.
  - `classifyVisceralFat(level)`: phân biệt `null`/`undefined` (`Chưa có số đo`, `status: 'unknown'`) với giá trị `0` thực (`Mức an toàn (0/9)`, `status: 'safe'`).
- **Consumer UI (`InBodyDashboard.tsx`, `MeasurementHistoryTable.tsx`, `ProgressChart.tsx`, `Header.tsx`, `app/page.tsx`):**
  - Truyền `profile` / `sexAtBirth` từ `app/page.tsx` -> `InBodyDashboard` -> `MeasurementHistoryTable` và `classifyPbf`.
  - Chỉ tính delta (`weightDelta`, `smmDelta`, `pbfDelta`, `vflDelta`) khi cả mốc mới nhất và mốc đối chiếu đều có số liệu thực (`!= null`).
  - KPI thiếu dữ liệu hiển thị `--` kèm chú thích `Chưa có số đo`, không tự gắn phân loại nguy cơ.
  - `ProgressChart`: chuẩn hóa missing thành `null` và đặt `connectNulls={false}` trên toàn bộ `<Area>` / `<Line>` để tạo khoảng trống thay vì kéo xuống `0`.
  - `app/page.tsx`: khi danh sách số đo trả về rỗng (ví dụ sau khi xóa hết số đo), chủ động gọi `setLatestMeasurement(null)` để xóa dữ liệu cũ ở `Header` và trang cha. `Header.tsx` dùng kiểm tra `!= null` thay vì `!== undefined` để tránh render `null kg`.

### 2.2 R05 — Giữ và hiển thị `safety_result` trong Check-in + Sửa sai nghĩa dữ liệu form

- **Type & Adapter (`frontend/src/types/index.ts`, `frontend/src/lib/api.ts`):**
  - Bổ sung `'medical_caution'` vào `SafetyResult['risk_level']` và thêm `safety_result?: SafetyResult | null` cùng các trường đúng contract backend (`adherence`, `energy_level`, `sleep_quality`, `soreness`, `symptoms`, `note`, `checked_at`) vào `CheckInLog`.
  - `saveCheckIn` và `fetchCheckIns`: bảo toàn nguyên vẹn `safety_result` từ backend; bỏ hoàn toàn việc bịa giá trị mặc định (`sleep_hours: 7.5`, `workout_rating: soreness ?? 5`).
- **Cảnh báo truy cập & UI (`SafetyBanner.tsx`, `ProfileAndGoals.tsx`):**
  - `SafetyBanner.tsx`: bổ sung thuộc tính accessibility `role="alert"` + `aria-live="assertive"` cho mức `urgent`, và `role="status"` + `aria-live="polite"` cho `medical_caution` / `moderate`.
  - `ProfileAndGoals.tsx`:
    - Chỉnh form Check-in nhập đúng đại lượng backend lưu: `Tuân thủ (%)` (0–100), `Năng lượng (1–5)`, `Giấc ngủ (1–5)`, `Đau mỏi (1–5)`, `Triệu chứng bất thường` (tách danh sách theo dấu phẩy), `Ghi chú thêm`.
    - Hiển thị `<SafetyBanner safety={latestCheckInSafety} />` ngay phía trên form sau khi lưu. Nếu mức `urgent`, không hiện badge xanh "Đã ghi nhận!" che khuất cảnh báo.
    - Dùng `checkInRequestSeqRef` chống race condition để cảnh báo luôn khớp với check-in vừa gửi gần nhất.
    - Lịch sử check-in giữ và hiển thị trạng thái `urgent` (`role="alert"`) và `medical_caution` (`role="status"`) kèm `recommended_action` từ backend khi tải lại.

### 2.3 R10 — Đọc đúng cấu trúc `{items: [...]}` và xử lý lỗi phiên / quyền / consent / dependency

- **Adapter (`frontend/src/lib/api.ts`):**
  - `fetchCheckIns` và `fetchMemoryFacts` đọc đúng `data.items` theo contract backend (`GET /me/check-ins` và `GET /me/memory/facts`); `{items: []}` trả `[]` hợp lệ.
  - Payload sai cấu trúc (không phải array/không có `items`) ném `ApiError(..., 502)` thay vì âm thầm trả `[]`.
  - Không nuốt lỗi HTTP: `401` ném `ApiError(..., 401)` (constructor `ApiError` tự động xóa `accessToken` và phát sự kiện `bodywise-auth-expired` đưa UI về đăng nhập); `403` ném thông báo thiếu quyền tiếng Việt có dấu (không đăng xuất); `409` ném thông báo cần đồng ý xử lý dữ liệu/cá nhân hóa; `503` ném thông báo dịch vụ lưu trữ tạm thời gián đoạn.
- **Consumer (`ProfileAndGoals.tsx`):**
  - Tách riêng `checkInError` và `memoryError` khi xử lý `Promise.allSettled` trong cả lần tải đầu (`useEffect`) và làm mới (`loadAllData`), đảm bảo lỗi check-in/memory không bị che lấp khi profile tải thành công và không hiển thị nhầm thành trạng thái rỗng.

### 2.4 R11 — Mapping tường minh và hiển thị an toàn Citations từ backend

- **Adapter (`frontend/src/lib/api.ts`):**
  - `sendChatMessageApi`: map tường minh `data.citations` / `data.evidence` từ backend sang `Citation`, bảo toàn `id`, `document_id`, `chunk_id`, `excerpt` (gán đồng bộ sang `content`), `source`, `source_url`, `publisher`, `source_tier`, `source_version`, `retrieval_score`, `rerank_score`.
- **Component (`frontend/src/components/chat/CitationsView.tsx`):**
  - Giữ đúng `[id]` của backend để người dùng đối chiếu với `[n]` trong nội dung trả lời.
  - Mở thẻ trích dẫn hiển thị đúng `excerpt` (không bị rỗng), cùng nguồn và phiên bản (`source_version`).
  - Không ép `retrieval_score` thành `%`; hiển thị số điểm kèm chú thích không phải xác suất y khoa.
  - Render `title`, `source`, `excerpt` dưới dạng React text node an toàn (tự động escape HTML) và kiểm tra scheme `http:`/`https:` qua `isValidHttpUrl` trước khi render thẻ `<a>` (chặn `javascript:` hoặc URL không hợp lệ).

---

## 3. Lựa chọn công cụ kiểm thử & Kết quả kiểm chứng

- **Lựa chọn runner:** Frontend chưa cài Jest/Vitest/Playwright. Sử dụng `node:test` + `node:assert/strict` chạy qua `npx tsx --test` (có sẵn qua `npx`, tự phân giải TypeScript & path alias `@/*`) kết hợp `react-dom/server` (`renderToStaticMarkup`) để vừa kiểm tra adapter/classifier/event vừa kiểm tra HTML output thật ở component consumer mà không thêm dependency nặng vào `package.json`.
- **Tệp regression:** `frontend/tests/regression-r04-r05-r10-r11.test.mjs`

| Hạng mục kiểm chứng | Lệnh chạy | Kết quả trước sửa | Kết quả sau sửa |
|---|---|---|---|
| Regression tái hiện lỗi ban đầu (8 ca đầu) | `npx tsx --test frontend/tests/regression-r04-r05-r10-r11.test.mjs` | **7/8 FAILED** (tái hiện đủ lỗi R04, R05, R10, R11) | **8/8 PASSED** |
| Regression mở rộng (14 ca: adapter + edge zero/string + 401/403/409/503 + auth-expired event + React SSR component tests cho `SafetyBanner`, `CitationsView`, `MeasurementHistoryTable`) | `cd frontend; npx tsx --test tests/regression-r04-r05-r10-r11.test.mjs` | — | **14/14 PASSED** |
| TypeScript check | `cd frontend; npx tsc --noEmit` | — | **PASS (0 errors)** |
| ESLint | `cd frontend; npm run lint` | — | **PASS (0 errors, 0 warnings)** |
| Next.js Production Build | `cd frontend; npm run build` | — | **PASS (Next.js 16.4.6 Turbopack)** |
| Kiểm tra vệ sinh diff | `git diff --check -- frontend/` | — | **PASS (0 whitespace issues)** |

### Danh sách tệp thay đổi (`frontend/`)

1. `frontend/src/types/index.ts`
2. `frontend/src/lib/classifiers.ts`
3. `frontend/src/lib/api.ts`
4. `frontend/src/app/page.tsx`
5. `frontend/src/components/layout/Header.tsx`
6. `frontend/src/components/inbody/InBodyDashboard.tsx`
7. `frontend/src/components/inbody/MeasurementHistoryTable.tsx`
8. `frontend/src/components/inbody/ProgressChart.tsx`
9. `frontend/src/components/profile/ProfileAndGoals.tsx`
10. `frontend/src/components/chat/SafetyBanner.tsx`
11. `frontend/src/components/chat/CitationsView.tsx`
12. `frontend/tests/regression-r04-r05-r10-r11.test.mjs` (mới)

---

## 4. Phạm vi chưa kiểm chứng & Bước tiếp theo

- **Phân biệt môi trường kiểm chứng:** Toàn bộ 14 ca kiểm thử trên chạy ở mức Node/tsx với mock `fetch` theo đúng JSON contract của backend và React SSR component rendering (`renderToStaticMarkup`), **chưa** kiểm chứng bằng trình duyệt thật nối tới container/HTTP runtime đang chạy vì yêu cầu đợt 1 chưa rebuild/deploy container.
- **Khuyến nghị khi chuyển sang bước deploy:**
  1. Rebuild/restart frontend container theo quy trình `AGENTS.md`.
  2. Chạy smoke test trình duyệt thật đối chiếu các luồng R04 (số đo thiếu & xóa hết), R05 (check-in triệu chứng cấp cứu `urgent`), R10 (hết hạn phiên 401 & 403/409), R11 (mở citation từ `/agent/answer` thật).
