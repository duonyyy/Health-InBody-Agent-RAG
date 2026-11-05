# 🌿 BodyWise — Cẩm Nang Nhận Diện Thương Hiệu & Quy Chuẩn Thiết Kế (Brand Identity & Guidelines)

> **Tài liệu chuẩn mực kỹ thuật & nhận diện thương hiệu cho dự án Health/InBody Agent RAG**  
> **Tên sản phẩm chính thức:** **BodyWise**  
> **Định danh phụ đề:** `BodyWise — Trợ lý Thể trạng & Dinh dưỡng AI`  
> **Slogan chính thức:** `Hiểu cơ thể. Sống chủ động.`  
> **Định hướng thẩm mỹ:** **Modern Health Tech & Calm Clarity** — Đáng tin cậy, khoa học, điềm tĩnh và tôn trọng quyền riêng tư.  
> **Phiên bản:** 1.0 · Cập nhật: 2026-11-04  
> **Phạm vi áp dụng:** Toàn bộ Web Client (`frontend/`), Tài liệu thiết kế (`docs/frontend-design/`), Báo cáo & Tài liệu hướng dẫn.  
> **Stack công nghệ:** Next.js 16+ App Router, React 19, TypeScript Strict Mode, Tailwind CSS v4, Recharts, Lucide Icons.

---

## 🌟 0. Triết Lý & Định Vị Thương Hiệu

**BodyWise không phải tên placeholder.** Đây là tên sản phẩm chính thức xuất hiện nhất quán trên toàn bộ hệ thống: Web App, Thanh điều hướng (Sidebar), Tiêu đề (Header), Thẻ trích dẫn (Citations), Metadata, Favicon và Báo cáo thể trạng.

- **Tên hiển thị chuẩn:** `BodyWise` (viết hoa chữ `B` và `W`; không viết `Bodywise`, `bodywise`, hay `BODYWISE` trong văn bản thông thường).
- **Tên đầy đủ / Phụ đề:** `BodyWise — Trợ lý Thể trạng & Dinh dưỡng AI`.
- **Slogan chính thức:** `Hiểu cơ thể. Sống chủ động.`
- **Giá trị cốt lõi:**
  1. **Tin cậy & Minh bạch (Evidence-Based):** Mọi tư vấn đều trích dẫn nguồn tri thức y khoa và tài liệu nghiên cứu đối soát.
  2. **An toàn tối thượng (Safety First):** Bảo vệ người dùng trước triệu chứng nguy cấp; không chẩn đoán hoặc kê đơn bừa bãi.
  3. **Điềm tĩnh & Tôn trọng (Calm & Non-Judgmental):** Không phán xét ngoại hình (no body-shaming), không tạo áp lực tiêu cực hay hình tượng "chuẩn mực cơ bắp phi thực tế".
  4. **Quyền riêng tư tuyệt đối (Privacy Guarded):** Người dùng có toàn quyền xem, xác nhận hoặc xóa các ký ức/chỉ số sức khỏe.
- **Đối tượng phục vụ:** Cá nhân theo dõi thể trạng định kỳ (cân nặng, BMI, cơ mỡ InBody), người tập luyện thể thao nâng cao sức bền, và người cần cải thiện chế độ ăn uống khoa học.

> [!CAUTION]
> **Quy tắc ưu tiên tối thượng:**  
> **An toàn y tế & Guardrail can thiệp khẩn cấp > Quyền riêng tư & Tiếp cận (Accessibility WCAG 2.2 AA) > Tính chính xác của số liệu khoa học > Nhất quán thương hiệu > Yếu tố trang trí đồ họa.**  
> Tuyệt đối không thay đổi luồng deterministic safety pre-check, ngưỡng WPRO hay thuật ngữ y khoa chỉ để làm giao diện "bắt mắt" hơn.

---

## 🎯 1. Ý Tưởng Thiết Kế Biểu Tượng (Brand Concept: Body Composition Rings & Wellness Leaf)

Biểu tượng Logo chính thức của **BodyWise** mang cấu trúc hình học giàu tính biểu tượng:

```text
       ┌──────────────┐
       │   ╭──────╮   │  ← 1. Vòng cung ngoài (Teal): Khối cơ & Cân bằng chuyển hóa
       │  │   ╭──╮ │  │  ← 2. Vòng cung trong (Cyan): Lượng nước & Chỉ số sinh học
       │  │  │ 🌿│ │  │  ← 3. Điểm hội tụ & Mầm sống (Vital Spark): Sự sống chủ động
       │  │   ╰──╯ │  │
       │   ╰──────╯   │  ← 4. Gradient chuyển động: #14B8A6 → #0D9488 → #0284C7
       └──────────────┘
```

1. **Vòng cung ngoài (Outer Composition Arc):** Tượng trưng cho cơ thể toàn diện, khối lượng cơ xương (SMM) và sự vững chãi của thể lực.
2. **Vòng cung trong (Inner Metabolism Arc):** Đại diện cho chỉ số nước, tỷ lệ mỡ (PBF) và sự luân chuyển trao đổi chất (BMR/TDEE).
3. **Mầm sống trung tâm (Vital Spark Node):** Thể hiện sự thấu hiểu cơ thể, ý thức sống chủ động và trí tuệ nhân tạo đồng hành.
4. **Dải màu chuyển động Gradient Teal $\rightarrow$ Sky Blue (`#14B8A6` $\rightarrow$ `#0D9488` $\rightarrow$ `#0284C7`):** Biểu trưng cho sự an tâm, khoa học y sinh hiện đại, công nghệ sạch và sự tươi mới.

> 🚫 **Điều cấm kỵ:**  
> 1. Tuyệt đối **không dùng biểu tượng chữ thập đỏ** (Red Cross) hoặc biểu tượng ống nghe/bác sĩ làm logo (tránh hiểu lầm đây là cơ sở y tế/bệnh viện).  
> 2. Không dùng từ "InBody" độc lập làm thương hiệu (InBody là nhãn hiệu của InBody Co., Ltd). Luôn gọi là "Chỉ số InBody" hoặc "Phiếu đo InBody".  
> 3. Không dùng icon Lucide tạm bợ để thay thế logo master.

---

## 📦 2. Danh Mục Tài Sản Thương Hiệu (Brand Asset Manifest)

Toàn bộ tệp tin hình ảnh, biểu tượng và favicon đã được chuẩn hóa và triển khai trực tiếp tại thư mục tĩnh **`frontend/public/brand/`** và lưu trữ tham chiếu tại **`docs/frontend-design/assets/brand/`**:

| Tên Tệp Tin | Định dạng & Kích thước | Mục đích sử dụng | Vị trí hiển thị đề xuất |
| :--- | :--- | :--- | :--- |
| **`logo-horizontal-dark.svg`** | Vector SVG (420×100) | Logo chính trên nền tối | TopBar, Sidebar expanded (Dark mode) |
| **`logo-horizontal-light.svg`** | Vector SVG (420×100) | Logo chính trên nền sáng | Banner, TopBar (Light mode), Báo cáo PDF |
| **`logo-mark.svg`** | Vector SVG (100×100) | Biểu tượng mầm sống đơn độc | Sidebar thu gọn, Avatar trợ lý AI trong Chat |
| **`logo-mono.svg`** | Vector SVG (420×100) | Logo đơn sắc 1 màu | Tài liệu in đen trắng, watermark báo cáo |
| **`app-icon.svg`** | Vector SVG (512×512) | Icon ứng dụng Squircle cao cấp | Khung giới thiệu ứng dụng, PWA splash |
| **`favicon.ico`** | Multi-size ICO (16/32/48) | Favicon chuẩn trình duyệt | Thẻ `<link rel="icon">` trong root layout |
| **`favicon-16.png`** / **`favicon-32.png`** | PNG 16×16 & 32×32 | Favicon độ phân giải thấp | Tab trình duyệt, bookmark bar |
| **`favicon-48.png`** | PNG 48×48 | Favicon trung bình | Windows taskbar pin, macOS dock |
| **`favicon-192.png`** / **`favicon-512.png`** | PNG 192×192 & 512×512 | PWA Web App Manifest icons | Màn hình chính Android, Chrome install prompt |
| **`apple-touch-icon.png`** | PNG 180×180 | Biểu tượng cho thiết bị Apple | Safari iOS Add to Home Screen |
| **`og-image.png`** | PNG 1200×630 (34 KB) | Open Graph Social Preview Image | Preview khi chia sẻ liên kết mạng xã hội |
| **`manifest.webmanifest`** | JSON Metadata | Web App Manifest | Cấu hình PWA cho Next.js 16 |

### Bộ Icon Nghiệp Vụ Chuyên Ngành (`frontend/public/icons/`):
Bộ 11 icon vector SVG chuẩn lưới 24×24px, bo góc nét 2.0px:
- `bmi.svg`: Thước đo chỉ số BMI WHO Châu Á (WPRO).
- `pbf.svg`: Tỷ lệ mỡ cơ thể (Percent Body Fat).
- `smm.svg`: Khối lượng cơ bắp xương (Skeletal Muscle Mass).
- `vfl.svg`: Cấp độ mỡ nội tạng (Visceral Fat Level) kèm khiên an toàn.
- `bfm.svg`: Khối lượng mỡ cơ thể (Body Fat Mass).
- `nutrition.svg`: Chế độ dinh dưỡng & tỷ lệ đa lượng Macros (Carb/Protein/Fat).
- `workout.svg`: Lịch tập kháng lực khoa học.
- `ocr-scan.svg`: Quét & bóc tách phiếu đo InBody bằng AI OCR.
- `safety-shield.svg`: Guardrail an toàn y tế tiền LLM.
- `memory-facts.svg`: Ký ức cá nhân hóa minh bạch.
- `evidence-doc.svg`: Nguồn trích dẫn tài liệu y khoa RAG.

---

## 🎨 3. Hệ Thống Token Thiết Kế (Design Tokens & Color Palette)

### 3.1. Bảng Màu Ngữ Nghĩa (Semantic Color Palette)

```css
:root {
  /* Brand Core Tokens */
  --brand-primary: #0D9488;        /* Teal 600 - Nút chính, Active item, Focus ring */
  --brand-primary-hover: #0F766E;  /* Teal 700 - Hover nút chính */
  --brand-primary-soft: #F0FDFA;   /* Teal 50 - Nền mục được chọn, Highlight nhẹ */
  --brand-accent: #0284C7;         /* Sky 600 - Điểm nhấn khoa học, Trích dẫn RAG */
  --brand-accent-hover: #0369A1;   /* Sky 700 - Hover accent */

  /* Neutral Typography & Surface (Light Theme) */
  --brand-ink: #0F172A;            /* Slate 900 - Tiêu đề, Nội dung chữ chính (AAA) */
  --brand-muted: #475569;          /* Slate 600 - Nhãn phụ, Metadata, Caption (AA) */
  --brand-muted-light: #94A3B8;    /* Slate 400 - Placeholder, Border phụ */
  --brand-bg: #F8FAFC;             /* Slate 50 - Nền trang dịu mắt */
  --brand-surface: #FFFFFF;        /* Trắng - Nền card, Dialog, Bubble */
  --brand-border: #E2E8F0;         /* Slate 200 - Đường phân cách, Viền input */

  /* Functional Status Tokens (Tuân thủ WHO & Guardrail Y Tế) */
  /* Success: Sắc ngọc Jade / Emerald - Chỉ số đạt chuẩn WPRO, Đã lưu */
  --brand-success: #059669;        /* Emerald 600 */
  --brand-success-soft: #ECFDF5;   /* Emerald 50 */
  --brand-success-border: #A7F3D0; /* Emerald 200 */
  --brand-success-text: #065F46;   /* Emerald 800 - Đạt chuẩn WCAG AAA (7.5:1) */

  /* Warning: Sắc mật ong Honey Amber - Chỉ số cần chú ý, Cảnh báo Caution */
  --brand-warning: #D97706;        /* Amber 600 */
  --brand-warning-soft: #FFFBEB;   /* Amber 50 */
  --brand-warning-border: #FDE68A; /* Amber 200 */
  --brand-warning-text: #92400E;   /* Amber 800 - Đạt chuẩn WCAG AA (6.2:1) */

  /* Danger: Sắc hồng ngọc Rose Crimson - Dành riêng cho URGENT Y TẾ & Lỗi cấp */
  --brand-danger: #E11D48;         /* Rose 600 */
  --brand-danger-soft: #FFF1F2;    /* Rose 50 */
  --brand-danger-border: #FECDD3;  /* Rose 200 */
  --brand-danger-text: #9F1239;    /* Rose 800 - Đạt chuẩn WCAG AAA (7.1:1) */
}

/* Chế độ Dark Theme (Mặc định cho Thao tác phân tích chuyên sâu) */
.dark {
  --brand-bg: #080D1A;            /* Deep Slate Navy dịu mắt khi nhìn lâu */
  --brand-surface: #0F172A;       /* Slate 900 */
  --brand-surface-elevated: #1E293B; /* Slate 800 */
  --brand-ink: #F8FAFC;           /* Slate 50 */
  --brand-muted: #94A3B8;         /* Slate 400 */
  --brand-border: #334155;        /* Slate 700 */
  --brand-primary: #14B8A6;       /* Teal 500 */
  --brand-primary-soft: rgba(20, 184, 166, 0.12);

  --brand-success: #10B981;
  --brand-success-soft: rgba(16, 185, 129, 0.12);
  --brand-success-border: rgba(52, 211, 153, 0.28);
  --brand-success-text: #6EE7B7;

  --brand-warning: #F59E0B;
  --brand-warning-soft: rgba(245, 158, 11, 0.12);
  --brand-warning-border: rgba(251, 191, 36, 0.28);
  --brand-warning-text: #FDE68A;

  --brand-danger: #F43F5E;
  --brand-danger-soft: rgba(244, 63, 94, 0.12);
  --brand-danger-border: rgba(251, 113, 133, 0.28);
  --brand-danger-text: #FECDD3;
}
```

---

## 📐 4. Quy Chuẩn Sử Dụng Logo Trong Giao Diện

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│ ĐƯỢC PHÉP                                                                      │
│ ✓ Dùng logo-horizontal-dark trên nền Dark mode (#080D1A, #0F172A)              │
│ ✓ Dùng logo-horizontal-light trên nền Light mode (#FFFFFF, #F8FAFC)            │
│ ✓ Dùng logo-mark (biểu tượng đơn) khi thu nhỏ Sidebar hoặc màn hình Mobile     │
│ ✓ Đảm bảo Clear Space xung quanh logo tối thiểu bằng 1/4 chiều cao biểu tượng  │
│                                                                                │
│ CẤM TUYỆT ĐỐI                                                                  │
│ ❌ Không kéo dãn, méo tỷ lệ (Stretching/Squishing)                              │
│ ❌ Không đảo ngược màu bằng bộ lọc CSS filter thô bạo (invert, hue-rotate)     │
│ ❌ Không thêm drop-shadow lòe loẹt hoặc viền neon dày cộm                      │
│ ❌ Không thay thế logo bằng icon trái tim ngẫu nhiên của thư viện icon         │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Kích Thước Khuyến Nghị Theo Khu Vực:
- **Sidebar Khám phá (Expanded):** Chiều cao logo `32px – 36px`.
- **Sidebar Thu gọn (Collapsed):** Sử dụng `logo-mark.svg` kích thước `32×32px`.
- **Thanh Header Mobile:** Chiều cao logo `28px`.
- **Báo cáo Thể trạng / In ấn:** Chiều cao logo `40px` (dùng bản Light hoặc Mono).

---

## 👥 5. Hướng Dẫn Trải Nghiệm Giao Diện Người Dùng (UX Guidelines)

### 5.1. Phân Hệ Trợ Lý AI & Chat
- **Cảnh báo Y Tế Khẩn Cấp (Urgent Safety Banner):**
  - Luôn hiển thị ở **đầu tiên** trước mọi nội dung trả lời.
  - Tích hợp nút gọi cấp cứu **115** nổi bật, thao tác 1-chạm.
  - Sử dụng viền đỏ trang nhã, không nhấp nháy liên tục gây hoảng loạn người dùng (tuân thủ `prefers-reduced-motion`).
- **Nguồn Trích Dẫn Minh Bạch (Evidence & Citations):**
  - Hiển thị tài liệu trích dẫn kèm mức độ tương đồng ngữ nghĩa.
  - Cho phép người dùng bấm mở xem chi tiết tài liệu tham chiếu từ RAG Corpus.
- **Dòng Miễn Trừ Trách Nhiệm Cố Định:**
  - Ở chân mỗi câu tư vấn sức khỏe: *"Thông tin chỉ mang tính chất tham khảo, không thay thế chẩn đoán hoặc chỉ định của bác sĩ chuyên khoa."*

### 5.2. Phân Hệ Chỉ Số InBody & Biểu Đồ
- **KPI Thể Trạng:**
  - Sử dụng `tabular-nums` cho số liệu để không bị giật layout khi số thay đổi.
  - Kèm nhãn phân loại chữ (Bình thường / Thừa cân / Cần chú ý) bên cạnh màu sắc để hỗ trợ người khiếm thị màu.
- **Biểu Đồ Xu Hướng (Progress Chart):**
  - Đường tham chiếu an toàn (mỡ nội tạng mức 9, BMI chuẩn 23.0) hiển thị dạng nét đứt thanh nhã.

### 5.3. Phân Hệ Hồ Sơ & Ký Ức Cá Nhân
- Người dùng có thể bấm **Xác nhận** hoặc **Xóa** từng sự thật mà AI ghi nhớ để bảo vệ quyền riêng tư theo đạo luật dữ liệu cá nhân.

---

## ✅ 6. Danh Sách Kiểm Tra Nghiệm Thu Nhận Diện (Brand DoD)

- [x] Đã khởi tạo đầy đủ bộ asset thương hiệu: Logo ngang sáng/tối, Logo mark, Mono, Favicon đa kích cỡ, App Icon, OG Image.
- [x] Đã cấu hình Web App Manifest chuẩn PWA.
- [x] Bảng mã màu tuân thủ độ tương phản WCAG 2.2 AA (văn bản ≥ 4.5:1, giao diện ≥ 3:1).
- [x] Component `BrandLogo` tích hợp linh hoạt chế độ thu gọn, dark/light theme.
- [x] Ngôn ngữ người dùng tiếng Việt có dấu, thân thiện, loại bỏ thuật ngữ nội bộ như "MVP fallback", "Agent RAG", "fast_path".
- [x] Safety banner cố định vị trí ưu tiên, không bị che khuất bởi nội dung LLM.

