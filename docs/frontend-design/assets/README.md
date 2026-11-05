# 📁 Thư Mục Lưu Trữ Tài Sản Thiết Kế & Nhận Diện Thương Hiệu (Design Assets & Brand Archive)

Thư mục này là **Kho tư liệu thiết kế master toàn diện** của nền tảng **BodyWise** (Dự án Health/InBody Agent RAG), lưu trữ toàn bộ các tài sản đồ họa chuẩn nhận diện thương hiệu, biểu tượng vector SVG chuyên ngành thể trạng & y tế, hệ thống favicon đa phân giải, thẻ xem trước Open Graph (OG), Web App Manifest và các tệp nguồn master/previews.

> ℹ️ **Ghi chú quan trọng cho Lập trình viên:**  
> - Toàn bộ tài sản đồ họa master được vector hóa chuẩn đường cong Bézier (vô hạn tỷ lệ, siêu nhẹ, tải nhanh) và các tệp raster PNG tối ưu đa phân giải (`@1x`, `@2x`, `@4x`).
> - Tài nguyên phục vụ trực tiếp lúc chạy (Runtime Assets) của ứng dụng web Next.js 16 được đồng bộ tại:  
>   🔗 **[`frontend/public/brand/`](../../../frontend/public/brand/)**, **[`frontend/public/icons/`](../../../frontend/public/icons/)** và **[`frontend/public/favicon.ico`](../../../frontend/public/favicon.ico)**.
> - Cẩm nang hướng dẫn sử dụng thương hiệu, mã màu token và quy chuẩn hiển thị chi tiết xem tại:  
>   🔗 **[`docs/frontend-design/BRAND_GUIDELINES.md`](../BRAND_GUIDELINES.md)**.
> - Cẩm nang thiết kế cho 3D/Designers xem tại:  
>   🔗 **[`docs/frontend-design/CAM_NANG_THIET_KE_CHO_DESIGNER_BODYWISE.md`](../CAM_NANG_THIET_KE_CHO_DESIGNER_BODYWISE.md)**.

---

## 🗂️ Cấu Trúc Phân Tầng Thư Mục `docs/frontend-design/assets/`

```text
docs/frontend-design/assets/
├── README.md                           # [BẠN ĐANG Ở ĐÂY] Bản đồ tra cứu & catalog tài sản thiết kế
│
├── brand/                              # Nhận diện thương hiệu Master, Vector SVGs, App Icons & Favicons
│   ├── logo-mark.svg                   # Biểu tượng mầm sống & vòng thể trạng độc lập (216×184 vector)
│   ├── logo-horizontal-dark.svg        # Logo ngang chính thức trên nền tối (596×184 vector)
│   ├── logo-horizontal-light.svg       # Logo ngang chính thức trên nền sáng (596×184 vector)
│   ├── logo-tagline-dark.svg           # Logo ngang kèm slogan tiếng Việt trên nền tối (596×184 vector)
│   ├── logo-tagline-light.svg          # Logo ngang kèm slogan tiếng Việt trên nền sáng (596×184 vector)
│   ├── logo-stacked.svg                # Logo dạng khối dọc căn giữa đa sắc (350×268 vector)
│   ├── logo-mono-black.svg             # Logo đơn sắc đen (350×268 vector)
│   ├── logo-mono-white.svg             # Logo đơn sắc trắng (350×268 vector)
│   ├── logo-mono.svg                   # Logo đơn sắc alias tương thích ngược (350×268 vector)
│   ├── app-icon.svg                    # Biểu tượng ứng dụng Squircle cao cấp nền Deep Navy (512×512 vector)
│   ├── app-icon.png                    # Icon ứng dụng raster 512×512 (19.4 KB)
│   ├── apple-touch-icon.png            # Icon cho thiết bị iOS Safari (180×180 - 7.3 KB)
│   ├── favicon.ico                     # Multi-size ICO chuẩn trình duyệt (16/32/48 nhúng - 4.5 KB)
│   ├── favicon.svg                     # Favicon định dạng vector SVG hiện đại (4.3 KB)
│   ├── favicon-16.png                  # Favicon độ phân giải 16×16 px cho bookmark bar (591 B)
│   ├── favicon-32.png                  # Favicon độ phân giải 32×32 px cho tab trình duyệt (1.3 KB)
│   ├── favicon-48.png                  # Favicon độ phân giải 48×48 px cho Windows taskbar (2.0 KB)
│   ├── favicon-192.png / icon-192.png  # Favicon kích thước 192×192 px chuẩn PWA (7.7 KB)
│   ├── favicon-512.png / icon-512.png  # Favicon kích thước 512×512 px chuẩn PWA (19.4 KB)
│   ├── icon-maskable-512.png           # Icon PWA hỗ trợ Adaptive Maskable (15.8 KB)
│   ├── og-image.png                    # Thẻ xem trước Open Graph mạng xã hội (1200×630 - 34 KB)
│   ├── manifest.webmanifest            # Cấu hình Web App Manifest chuẩn PWA
│   ├── QA-report.json                  # Báo cáo kiểm định chất lượng hình học và trắc nghiệm màu sắc
│   ├── DESIGNER_NOTES.md               # Ghi chú kỹ thuật & đánh giá độ chính xác từ Designer
│   │
│   ├── source/                         # Tệp nguồn hình học Master Bézier
│   │   ├── logo-master.svg             # Tọa độ hình học và dải gradient gốc
│   │   └── construction-grid.svg       # Khung lưới tỷ lệ và đường gióng đối xứng
│   │
│   ├── png/                            # Bộ raster PNG trong suốt đa phân giải (@1x, @2x, @4x)
│   │   ├── logo-mark@{1x,2x,4x}.png
│   │   ├── logo-horizontal-dark@{1x,2x,4x}.png
│   │   ├── logo-horizontal-light@{1x,2x,4x}.png
│   │   ├── logo-tagline-dark@{1x,2x,4x}.png
│   │   ├── logo-tagline-light@{1x,2x,4x}.png
│   │   ├── logo-stacked@{1x,2x,4x}.png
│   │   ├── logo-mono-black@{1x,2x,4x}.png
│   │   └── logo-mono-white@{1x,2x,4x}.png
│   │
│   └── previews/                       # Bảng đối chiếu kiểm thử thị giác
│       ├── favicon-size-test.png
│       ├── icon-alignment-before-after.png
│       ├── light-dark-comparison.png
│       ├── logo-variants.png
│       └── reconstruction-comparison.png
│
└── icons/                              # Bộ icon vector 24×24px chuẩn hóa cho miền Health & InBody
    ├── bmi.svg                         # Thước đo chỉ số BMI theo chuẩn WHO Châu Á (WPRO)
    ├── pbf.svg                         # Tỷ lệ mỡ cơ thể Percent Body Fat (%)
    ├── smm.svg                         # Khối lượng cơ bắp xương Skeletal Muscle Mass (kg)
    ├── vfl.svg                         # Cấp độ mỡ nội tạng Visceral Fat Level kèm khiên an toàn
    ├── bfm.svg                         # Khối lượng mỡ cơ thể Body Fat Mass (kg)
    ├── nutrition.svg                   # Khay dinh dưỡng & tỷ lệ cân bằng đa lượng Macros
    ├── workout.svg                     # Lịch tập kháng lực khoa học
    ├── ocr-scan.svg                    # Quét phiếu in kết quả đo InBody bằng AI OCR
    ├── safety-shield.svg               # Khiên bảo vệ & Guardrail an toàn y tế tiền LLM
    ├── memory-facts.svg                # Ký ức thể trạng cá nhân hóa người dùng
    ├── evidence-doc.svg                # Nguồn trích dẫn tài liệu y khoa trong Corpus RAG
    └── icons.json                      # Metadata mô tả bộ icon nghiệp vụ
```

---

## 🎨 1. Bảng Tra Cứu Hệ Thống Thương Hiệu Master (`brand/`)

| Tên Tệp Tin | Định Dạng & Kích Thước | Dung Lượng | Mô Tả & Chi Tiết Thiết Kế | Vị Trí Nhúng / Mục Đích Sử Dụng |
| :--- | :---: | :---: | :--- | :--- |
| **`logo-mark.svg`** | Vector SVG (216×184) | 4.3 KB | Biểu tượng mầm sống (Vital Spark) lồng trong 2 vòng cung thể trạng phối màu Vital Teal $\rightarrow$ Sky. | Sidebar thu gọn (Collapsed), Avatar trợ lý AI trong khung chat, Favicon SVG. |
| **`logo-horizontal-dark.svg`** | Vector SVG (596×184) | 6.9 KB | Logo ngang hoàn chỉnh gồm Mark + Wordmark `BodyWise` trắng tuyết trên nền trong suốt. | TopBar, Sidebar mở rộng (Expanded) trên giao diện nền tối (`#0F172A` / `#080D1A`). |
| **`logo-horizontal-light.svg`** | Vector SVG (596×184) | 6.9 KB | Phiên bản logo ngang nền sáng với Wordmark đen đá phiến (`#0F172A`). | Giao diện nền sáng (Light mode), báo cáo xuất PDF, email thông báo thể trạng. |
| **`logo-tagline-dark.svg`** | Vector SVG (596×184) | 14.2 KB | Logo ngang kèm Slogan chính thức "Hiểu cơ thể. Sống chủ động." trên nền tối. | Trang đích giới thiệu sản phẩm (Landing Page), Hero banner, Splash screen. |
| **`logo-tagline-light.svg`** | Vector SVG (596×184) | 14.2 KB | Logo ngang kèm Slogan tiếng Việt trên nền sáng. | Tài liệu in ấn màu, hồ sơ năng lực dự án, thư ngỏ đối tác y tế. |
| **`logo-stacked.svg`** | Vector SVG (350×268) | 7.0 KB | Khối logo dọc căn giữa hoàn chỉnh Mark + BodyWise đa sắc. | Màn hình đăng nhập/xác thực, màn hình tải trang (Loading screen), App Card. |
| **`logo-mono-black.svg`** | Vector SVG (350×268) | 5.5 KB | Logo khối dọc đơn sắc đen tuyền (`#000000`). | Tài liệu in ấn đen trắng, photocopy kết quả thể trạng. |
| **`logo-mono-white.svg`** | Vector SVG (350×268) | 5.5 KB | Logo khối dọc đơn sắc trắng tinh (`#FFFFFF`). | Khắc laser, in trên nền màu đặc biệt, watermark chống sao chép tài liệu. |
| **`favicon.ico`** | Multi-size ICO (16/32/48) | 4.5 KB | Tệp ICO tiêu chuẩn chứa đầy đủ 3 kích thước 16×16, 32×32, 48×48. | Tự động phục vụ tại `/favicon.ico` cho trình duyệt web. |
| **`favicon.svg`** | Vector SVG (216×184) | 4.3 KB | Favicon vector sắc nét vô hạn trên trình duyệt hiện đại. | Thẻ `<link rel="icon" type="image/svg+xml">`. |
| **`favicon-16.png`** | Raster PNG (16×16) | 591 B | Biểu tượng siêu nhỏ tối ưu pixel cho thanh bookmark bar. | Thanh dấu trang và danh sách tab thu nhỏ. |
| **`favicon-32.png`** | Raster PNG (32×32) | 1.3 KB | Biểu tượng tiêu chuẩn hiển thị trên tab trình duyệt hiện đại. | Tab trình duyệt Chrome, Edge, Safari, Firefox. |
| **`favicon-48.png`** | Raster PNG (48×48) | 2.0 KB | Biểu tượng trung bình cho thanh tác vụ hệ điều hành. | Ghim ứng dụng lên Windows Taskbar, macOS Dock. |
| **`icon-192.png`** | Raster PNG (192×192) | 7.7 KB | Biểu tượng lớn chuẩn Web App Manifest (PWA). | Màn hình chính thiết bị di động Android khi lưu ứng dụng. |
| **`icon-512.png`** | Raster PNG (512×512) | 19.4 KB | Biểu tượng độ phân giải siêu cao chuẩn PWA. | Màn hình khởi động ứng dụng (Splash Screen) của PWA. |
| **`icon-maskable-512.png`** | Raster PNG (512×512) | 15.8 KB | Biểu tượng PWA hỗ trợ Adaptive Masking theo hình tròn/vuông. | Đảm bảo không bị viền trắng cắt góc trên Android Launcher. |
| **`apple-touch-icon.png`** | Raster PNG (180×180) | 7.3 KB | Biểu tượng vuông bo góc theo chuẩn Apple iOS. | Màn hình chính Safari iOS khi chọn "Add to Home Screen". |
| **`og-image.png`** | Raster PNG (1200×630) | 34.1 KB | Thẻ hình ảnh xem trước mạng xã hội chứa Logo và KPI thể trạng. | Thẻ card Open Graph khi chia sẻ qua Zalo, Facebook, LinkedIn. |
| **`manifest.webmanifest`** | JSON Metadata | 520 B | Tệp cấu hình tiêu chuẩn của Progressive Web App (PWA). | Đăng ký tên ứng dụng, màu chủ đề, biểu tượng và chế độ standalone. |

---

## 🩺 2. Bảng Tra Cứu Bộ Icon Nghiệp Vụ Chuyên Ngành (`icons/`)

Toàn bộ icon được thiết kế theo tiêu chuẩn vector SVG tối giản trên **khung lưới chuẩn 24×24px**, độ dày nét viền **`stroke-width="2"`**, bo tròn đầu nét (`stroke-linecap="round"`, `stroke-linejoin="round"`), màu sắc kế thừa linh hoạt qua **`stroke="currentColor"`**:

| Tên Tệp SVG | Kích Thước | Nghiệp Vụ Tương Ứng Trong Hệ Thống | Ý Nghĩa Hình Tượng & Ứng Dụng |
| :--- | :---: | :--- | :--- |
| **`bmi.svg`** | 24×24 px | Chỉ số Khối Cơ Thể BMI (WHO WPRO) | Đồng hồ đo áp suất thể trạng với kim chỉ thị trung tâm, đại diện cho phân loại thiếu cân/chuẩn/thừa cân/béo phì. |
| **`pbf.svg`** | 24×24 px | Tỷ lệ Mỡ Cơ Thể Percent Body Fat (%) | Giọt lipid cách điệu dạng hình học kèm thước đo vi lượng, hiển thị trên thẻ KPI tỷ lệ mỡ sinh học. |
| **`smm.svg`** | 24×24 px | Khối lượng Cơ bắp Xương (SMM kg) | Cặp tạ chuông vươn chéo tượng trưng cho sức mạnh bó cơ và sự phát triển của cơ xương vận động. |
| **`vfl.svg`** | 24×24 px | Cấp độ Mỡ Nội Tạng (Visceral Fat Level) | Khiên chắn bảo vệ bao quanh vùng tâm cơ thể, cảnh báo ngưỡng an toàn (mức 1–9) và nguy cơ (≥ 10). |
| **`bfm.svg`** | 24×24 px | Khối lượng Mỡ Cơ Thể (BFM kg) | Vòng tròn khối lượng mỡ toàn phần với các điểm phân bố lipid cơ thể. |
| **`nutrition.svg`** | 24×24 px | Kế hoạch Dinh Dưỡng & Đa Lượng Macros | Bữa ăn cân bằng dưỡng chất với đĩa ăn khoa học và vạch định lượng TDEE / Calories. |
| **`workout.svg`** | 24×24 px | Lịch Tập Luyện & Vận Động Kháng Lực | Biểu tượng tạ đòn phối hợp vận động thể thao nâng cao sức bền thể chất. |
| **`ocr-scan.svg`** | 24×24 px | Quét Phiếu Đo InBody bằng AI OCR | Khung ngắm cảm biến quét 4 góc bao quanh tờ kết quả đo và các dòng dữ liệu chỉ số. |
| **`safety-shield.svg`** | 24×24 px | Guardrail An Toàn Y Tế Tiền LLM | Khiên an toàn có dấu tích kiểm định, biểu tượng cho bộ lọc triệu chứng tim mạch/hô hấp cấp cứu 115. |
| **`memory-facts.svg`** | 24×24 px | Quản Trị Ký Ức Cá Nhân Hóa | Não bộ trí tuệ nhân tạo ghi nhớ các sự thật thể trạng, dị ứng thức ăn và tiền sử vận động. |
| **`evidence-doc.svg`** | 24×24 px | Nguồn Trích Dẫn Y Khoa RAG | Quyển tài liệu nghiên cứu y học có đánh dấu đoạn trích minh bạch và điểm tương đồng ngữ nghĩa. |
| **`icons.json`** | JSON Metadata | Metadata mô tả bộ icon nghiệp vụ | Danh mục phân loại và ánh xạ icon theo luồng Agent. |

---

## 🛠️ 3. Quy Chuẩn Kỹ Thuật Khi Sử Dụng Trong Frontend (Next.js 16)

### 3.1. Nhúng Logo bằng Component `BrandLogo.tsx`
```tsx
import { BrandLogo } from '@/components/branding/BrandLogo';

// 1. Logo ngang tiêu chuẩn trên nền tối (Sidebar expanded / TopBar)
<BrandLogo theme="dark" href="/" />

// 2. Logo ngang kèm slogan tiếng Việt "Hiểu cơ thể. Sống chủ động."
<BrandLogo variant="tagline" theme="dark" href="/" />
// Hoặc ngắn gọn:
<BrandLogo withTagline theme="dark" href="/" />

// 3. Logo thu gọn chỉ hiện icon mark (Sidebar collapsed / Mobile)
<BrandLogo compact href="/" />

// 4. Logo dạng khối dọc căn giữa (Màn hình Login / Splash)
<BrandLogo variant="stacked" height={64} href="/" />

// 5. Logo đơn sắc (In ấn / Watermark)
<BrandLogo variant="mono-black" href="/" />
<BrandLogo variant="mono-white" href="/" />
```

### 3.2. Cấu Hình Metadata Favicons trong `app/layout.tsx`
```tsx
export const metadata: Metadata = {
  title: 'BodyWise — Trợ lý Sức khỏe & Thể trạng Agent RAG',
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/brand/favicon.svg', type: 'image/svg+xml' },
      { url: '/brand/favicon-32.png', sizes: '32x32', type: 'image/png' },
      { url: '/brand/favicon-16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: [
      { url: '/brand/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
  manifest: '/brand/manifest.webmanifest',
};
```
