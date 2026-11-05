# Báo cáo Nghiệm thu Kỹ thuật WP-04: Hoàn thiện Frontend BodyWise

- **Ngày thực hiện:** 2026-11-05
- **Phạm vi:** Work Package 04 (Frontend dùng API thật và lỗi thật, tích hợp Brand Identity BodyWise)
- **Vị trí nguồn:** `frontend/` (`Next.js 16.4.3`, React 19, Tailwind CSS v4, TypeScript 5)
- **Mức độ bằng chứng:** `VERIFIED_SOURCE` + `VERIFIED_TEST` + `VERIFIED_RUNTIME (Frontend HTTP)`

---

## 1. Mục tiêu và Tiêu chí Nghiệm thu đã Đạt

1. **Nhận diện Thương hiệu BodyWise (SCR-01 đến SCR-07):**
   - Đã giải nén và sắp xếp trọn vẹn bộ nhận diện `BodyWise_Logo_Assets_FIXED.zip` vào kho thiết kế `docs/frontend-design/assets/brand/` và đồng bộ vào `frontend/public/brand/` và `frontend/public/favicon.ico`.
   - Cập nhật Logo thương hiệu tại `README.md` (hỗ trợ tự đổi theme Dark/Light qua `<picture>`).
   - Xây dựng component `BrandLogo.tsx` hỗ trợ đầy đủ các biến thể: `horizontal`, `tagline`, `stacked`, `mono-black`, `mono-white`, `compact`.
   - Cập nhật avatar trợ lý AI trong bong bóng chat bằng biểu tượng chính thức `logo-mark.svg`.

2. **Xóa bỏ 100% Fallback Mô phỏng Ngầm (Zero Silent Fallbacks):**
   - Đã loại bỏ hoàn toàn cơ chế tự sinh dữ liệu giả trong `frontend/src/lib/api.ts` khi gọi backend thất bại.
   - Khi backend offline, mất mạng hoặc lỗi máy chủ, hệ thống trả về lỗi chuẩn `ApiError` và hiển thị Error Banner bằng tiếng Việt có dấu, kèm nút **"Thử lại" (Retry)**.
   - Chế độ Demo (nếu cần trình diễn) được tách bạch tường minh qua cờ `isExplicitDemoMode()` với toggle rõ ràng trên Header, không lẫn lộn với dữ liệu người dùng thật.

3. **Giao tiếp Chat Đa tác tử & Bảo toàn Ngữ cảnh (SCR-01):**
   - Chat Client tiếp nhận và **gửi lại `conversation_id`** do server cấp phát sau mỗi lượt trao đổi, đảm bảo tính liên tục của phiên hội thoại trên server.
   - Xử lý đầy đủ các metadata từ backend gộp: `request_id`, `status` (`ok`, `degraded`, `error`), `fast_path`, `safety_result`, `citations`, `errors`, `latency_ms`.
   - Nút "Cuộc trò chuyện mới" được diễn đạt chính xác: chỉ reset phiên hội thoại phía client để bắt đầu hội thoại mới, không gây hiểu nhầm là đã xóa dữ liệu trên database server.
   - Thêm nút "Thử lại câu hỏi" khi gặp lỗi kết nối mà không làm mất nội dung prompt người dùng vừa nhập.

4. **Đồng bộ Schema InBody với Backend P1 (SCR-02, SCR-03, SCR-04):**
   - Map chính xác các trường dữ liệu của backend gộp: `smm_kg`, `bfm_kg`, `pbf_percent`, `source_type`, `confirmed_by_user`.
   - `InBodyDashboard`: Xử lý trọn vẹn 3 trạng thái: Đang tải (Loading Skeleton), Trống (Empty State hướng dẫn đo) và Lỗi (Error State kèm Retry).
   - `OcrScanner` (SCR-04): Tuân thủ quy trình 3 bước chuẩn y tế: **Tải ảnh lên $\rightarrow$ Xem trước bản nháp (Draft) $\rightarrow$ Người dùng kiểm tra/chỉnh sửa $\rightarrow$ Xác nhận lưu**. Khi backend chưa kích hoạt `FEATURE_OCR_UPLOAD=true`, hệ thống hiển thị thông báo trung thực (404/503) và mở biểu mẫu nhập tay, không tự bịa số đo từ ảnh.

5. **Hồ sơ Cá nhân, Check-ins & Ký ức (SCR-05):**
   - Quản lý Profile (`/me/profile`), Check-in logs hàng ngày (`/me/check-ins`), và Memory facts (`/me/memory/facts`).
   - Xóa bỏ mock tĩnh, kết nối API thật, hỗ trợ cập nhật và xóa ký ức theo chuẩn backend.

6. **Tra cứu Kho Tri thức & An toàn Y tế (SCR-06):**
   - Tìm kiếm trực tiếp qua endpoint `/search` (Qdrant & BM25 hybrid search).
   - Nội dung trích dẫn được escape an toàn chống XSS; nhãn tương đồng được ghi rõ: *"Tương đồng: XX% (Điểm đối chiếu thuật toán, không phải độ chính xác y khoa)"*.

7. **Công cụ Kỹ thuật DevTools (SCR-07):**
   - Chỉ xuất hiện trong môi trường phát triển (`NODE_ENV !== 'production' || getAuthMode() === 'development'`). Bị vô hiệu hóa hoàn toàn ở production.
   - Kiểm tra kết nối ping `/health` thời gian thực tới FastAPI, PostgreSQL và Qdrant.
   - Sandbox kiểm tra các công cụ độc lập: Tính BMI WHO Châu Á, BMR/TDEE Macros, Triage An toàn Y tế (Fast-path).

---

## 2. Kết quả Kiểm thử & Biên dịch

### 2.1 Kiểm tra Cú pháp & Linter (`ESLint`)
- **Lệnh thực thi:** `npm --prefix frontend run lint`
- **Kết quả:** `Exit code 0`
- **Chi tiết:** 0 error, 0 warning. Đã khắc phục toàn bộ các lỗi purity và cascading renders theo tiêu chuẩn mới của React 19 / Next.js 16.

### 2.2 Kiểm tra Kiểu dữ liệu (`TypeScript Typecheck`)
- **Lệnh thực thi:** `npx --prefix frontend tsc -p frontend/tsconfig.json --noEmit`
- **Kết quả:** `Exit code 0`
- **Chi tiết:** 0 type errors. Toàn bộ types giữa Frontend và Backend gộp đã khớp 100%.

### 2.3 Bản dựng Production (`Next.js Build`)
- **Lệnh thực thi:** `npm --prefix frontend run build`
- **Kết quả:** `Exit code 0`
- **Chi tiết:**
  - Biên dịch thành công trong 5.6s bằng Turbopack.
  - Tạo trang tĩnh 4/4 pages (`/`, `/_not-found`).

### 2.4 Kiểm thử Giao diện Thực tế & Responsive (Chrome/Edge Headless)
Giao diện đã được kiểm tra trên trình duyệt thực tế tại cổng HTTP `http://localhost:3000` ở 3 kích thước tiêu chuẩn:
- **Desktop (1440x900):** Đầy đủ thanh Sidebar điều hướng, Header, Chat view, InBody dashboard, Chart 3 chế độ.
- **Tablet (768x1024):** Responsive co giãn linh hoạt, bảng số liệu cuộn ngang mượt mà, layout 2 cột chuyển thành 1-2 cột hợp lý.
- **Mobile (320x640):** Thanh điều hướng trên đỉnh kèm Logo BodyWise compact, Drawer menu trượt, phông chữ và nút bấm tối ưu cảm ứng.

Toàn bộ ảnh chụp màn hình bằng chứng đã được lưu trữ tại:
`docs/frontend-design/evidence/screenshots/`:
1. `SCR-01_chat_desktop_1440.png` (226 KB)
2. `SCR-01_chat_tablet_768.png` (210 KB)
3. `SCR-01_chat_mobile_320.png` (74 KB)
4. `SCR-02_inbody_desktop_1440.png` (226 KB)
5. `SCR-02_inbody_tablet_768.png` (142 KB)
6. `SCR-02_inbody_mobile_320.png` (74 KB)
7. `SCR-05_profile_desktop_1440.png` (226 KB)
8. `SCR-05_profile_tablet_768.png` (210 KB)
9. `SCR-06_search_desktop_1440.png` (152 KB)
10. `SCR-07_devtools_desktop_1440.png` (226 KB)

---

## 3. Danh sách File Đã Sửa Đổi / Tạo Mới

### 3.1 Nhận diện & Assets
- `frontend/public/brand/`: Bộ logo vector và raster đầy đủ kích thước.
- `frontend/public/favicon.ico`: Favicon chính thức của BodyWise.
- `frontend/src/components/branding/BrandLogo.tsx`: Component hiển thị logo thông minh.
- `README.md`: Bổ sung header logo thương hiệu với `<picture>`.

### 3.2 Tầng Tích hợp API & Dữ liệu
- `frontend/src/types/index.ts`: Mở rộng schema đồng bộ với Backend P1.
- `frontend/src/lib/api.ts`: Viết lại hoàn toàn, xóa 100% silent mock fallback, chuẩn hóa error handling và auth header.

### 3.3 Tầng Giao diện Người dùng
- `frontend/src/app/page.tsx`: Quản lý state toàn cục, deep-linking URL `?tab=...`, thanh top-bar mobile.
- `frontend/src/components/layout/Sidebar.tsx`: Brand logo, chỉ báo trạng thái máy chủ thật, ẩn DevTools ở production.
- `frontend/src/components/layout/Header.tsx`: Nút bắt đầu cuộc trò chuyện mới, hiển thị chỉ số đo gần nhất thật, toggle demo mode tường minh.
- `frontend/src/components/chat/ChatContainer.tsx`: Quản lý `conversation_id`, retry prompt, error banner.
- `frontend/src/components/chat/MessageBubble.tsx`: Avatar logo thương hiệu, hiển thị trạng thái degraded.
- `frontend/src/components/chat/CitationsView.tsx`: XSS sanitization, làm rõ điểm tương đồng không phải xác suất y tế.
- `frontend/src/components/inbody/InBodyDashboard.tsx`: Xử lý Loading/Empty/Error state.
- `frontend/src/components/inbody/MeasurementForm.tsx`: Đồng bộ schema `smm_kg`, `bfm_kg`, `pbf_percent`.
- `frontend/src/components/inbody/MeasurementHistoryTable.tsx`: Hiển thị nguồn dữ liệu thật và các chỉ số chuẩn hóa.
- `frontend/src/components/inbody/ProgressChart.tsx`: Biểu đồ Recharts theo dõi tiến trình tái tạo thể trạng.
- `frontend/src/components/inbody/OcrScanner.tsx`: Quy trình 3 bước OCR, khóa hành động và báo lỗi thật khi backend OCR chưa bật.
- `frontend/src/components/profile/ProfileAndGoals.tsx`: Hồ sơ, check-ins và ký ức cá nhân hóa thật.
- `frontend/src/components/search/CorpusSearch.tsx`: Tìm kiếm RAG ngữ nghĩa, xử lý loading/empty/error với nút thử lại.
- `frontend/src/components/dev/DevTools.tsx`: Giám sát hạ tầng và hộp cát kiểm thử thuật toán an toàn y tế.

### 3.4 Kế hoạch & Tài liệu
- `docs/KE_HOACH_NANG_CAP_DU_AN_2026.md`: Cập nhật trạng thái nghiệm thu của WP-04.

---

## 4. Những Giới Hạn & Blocker Còn Tồn Tại

1. **Chưa có Authentication Production:**
   - Frontend hiện sử dụng header `X-Dev-User-Id` thông qua cơ chế phát triển (`AUTH_MODE=development`). Khi triển khai lên môi trường production, cần tích hợp Identity Provider (OAuth2 / OIDC / Session Cookie) theo đúng yêu cầu tại WP-03 trước khi có thể công bố là Production-Ready.
2. **Tính năng InBody OCR Backend đang tắt:**
   - Khi `FEATURE_OCR_UPLOAD=false` trên backend, API `/me/inbody-ocr` trả về 404. Frontend đã xử lý đúng bằng cách hiển thị thông báo lỗi trung thực và hướng dẫn người dùng nhập tay, không tự sinh số giả. Tính năng OCR trích xuất tự động sẽ sẵn sàng hoạt động ngay khi backend bật tính năng này tại WP-10.
3. **Chưa qua kiểm thử tải và Soak Test:**
   - Cần hoàn thành các gate tại WP-12 (Soak test, latency benchmark, privacy audit) trước khi phát hành phiên bản chính thức.

