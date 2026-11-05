# 🌿 Nhóm Tài Liệu: Kiến Trúc Giao Diện, Nhận Diện Thương Hiệu & Trải Nghiệm Người Dùng (BodyWise Frontend Design)

> **Dự án:** Health / InBody AI Agent RAG  
> **Tên thương hiệu chính thức:** **BodyWise** (`BodyWise — Trợ lý Thể trạng & Dinh dưỡng AI`)  
> **Slogan chính thức:** `Hiểu cơ thể. Sống chủ động.`  
> **Định hướng thẩm mỹ:** **Modern BioTech & Calm Vitality** (Sứ Men Sinh Học & Khối Chuyển Hóa Năng Lượng)  
> **Stack công nghệ frontend:** Next.js 16 (App Router), React 19, TypeScript Strict Mode, Tailwind CSS v4, Recharts, Lucide Icons.

---

## 🧭 1. Tổng Quan & Triết Lý Thiết Kế Sản Phẩm

BodyWise là nền tảng trợ lý trí tuệ nhân tạo chuyên sâu về **phân tích thành phần cơ thể InBody (BMI, PBF, SMM, BFM, Mỡ nội tạng theo chuẩn WHO Châu Á WPRO)**, tư vấn dinh dưỡng tái tạo cơ mỡ, lập lịch tập kháng lực và cảnh báo an toàn y tế.

### Nguyên Tắc Thiết Kế Ưu Tiên Tối Thượng:
```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. AN TOÀN Y TẾ & CHỐT CHẶN CẤP CỨU 115 (Medical Safety Guardrail)                          │
│    Fast-path phản hồi < 50ms, không gọi LLM, không kê đơn hay chẩn đoán bừa bãi.           │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. QUYỀN RIÊNG TƯ & KHẢ NĂNG TIẾP CẬN (Privacy & Accessibility WCAG 2.2 AA)                 │
│    Người dùng toàn quyền xem, xác nhận hoặc xóa ký ức AI. Độ tương phản chữ đạt chuẩn AA.  │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. ĐỘ CHUẨN XÁC KHOA HỌC (Evidence-Based & Scientific Accuracy)                             │
│    Mọi tư vấn đều trích dẫn nguồn tài liệu nghiên cứu y khoa từ kho tri thức RAG.          │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. NHẤT QUÁN THƯƠNG HIỆU & ĐIỀM TĨNH THỊ GIÁC (Calm Clarity)                               │
│    Màu sắc hài hòa, không body-shaming, không hình ảnh cơ bắp phi thực tế.                  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ 2. Bản Đồ Cấu Trúc Tài Liệu Nhóm Thiết Kế (Documentation Map)

Toàn bộ hệ thống tài liệu và tài sản thiết kế được quy hoạch bài bản và đồng bộ trong thư mục `docs/frontend-design/`:

```text
docs/frontend-design/
├── README.md                                    # [BẠN ĐANG Ở ĐÂY] Bản đồ tổng quan kiến trúc & chỉ dẫn tra cứu
│
├── DESIGN_BRIEF_CHO_DESIGNER_BODYWISE.md        # Creative Brief 14 mục gửi Nhà thiết kế (Đọc 20 phút bắt tay làm ngay)
│                                                # (Mục tiêu, cảm xúc, bảng màu, 8 tranh 3D, 6 tranh trạng thái, checklist)
│
├── CAM_NANG_THIET_KE_CHO_DESIGNER_BODYWISE.md   # Cẩm nang thi công chi tiết cho 3D Artist, Designer & Motion Artist
│                                                # (Vật liệu PBR, thông số màu, brief 8 tranh 3D, quy chuẩn icon)
│
├── BRAND_GUIDELINES.md                          # Cẩm nang nhận diện thương hiệu & quy chuẩn thiết kế
│                                                # (Triết lý, ý tưởng logo, token CSS, Clear space, typography, UX rules)
│
├── SCREEN_SPECIFICATIONS.md                     # Đặc tả chi tiết 7 màn hình & phân hệ hệ thống (SCR-01 đến SCR-07)
│                                                # (Wireframe ASCII, component inventory, data contract, edge cases)
│
├── KE_HOACH_THIET_KE_UI_THUONG_HIEU.md          # Kế hoạch chiến lược & lộ trình nâng cấp giao diện toàn diện
│                                                # (So sánh trước/sau, bảng ánh xạ thuật ngữ người dùng, kế hoạch 7 đợt)
│
└── assets/                                      # Kho lưu trữ tài sản thiết kế master
    ├── README.md                                # Catalog tra cứu toàn bộ assets, kích thước, định dạng, vị trí nhúng
    ├── brand/                                   # Logo master SVG, favicon đa kích cỡ, app icon, OG image, manifest
    └── icons/                                   # Bộ 11 icon vector SVG chuyên ngành InBody & Y tế (24×24px)
```

---

## 📚 3. Hướng Dẫn Sử Dụng Nhanh Từng Tài Liệu

| Tài Liệu | Đối Tượng Sử Dụng Chính | Nội Dung Cốt Lõi |
| :--- | :--- | :--- |
| **[`DESIGN_BRIEF_CHO_DESIGNER_BODYWISE.md`](DESIGN_BRIEF_CHO_DESIGNER_BODYWISE.md)** | **Brand Designer, 3D Artist, Illustrator** | Creative Brief 14 mục toàn diện: giải thích đời thường, bảng màu chốt, brief 8 tranh 3D, 6 tranh state, quy trình M0-M5, checklist bàn giao. |
| **[`CAM_NANG_THIET_KE_CHO_DESIGNER_BODYWISE.md`](CAM_NANG_THIET_KE_CHO_DESIGNER_BODYWISE.md)** | **3D Artist, UI Designer, Modeler** | Thiết lập shader PBR (Albedo/Roughness/Metallic), góc máy 85mm, nguồn sáng 5400K, brief 8 tranh 3D và lưới icon 24px. |
| **[`BRAND_GUIDELINES.md`](BRAND_GUIDELINES.md)** | **Brand Designer, Frontend Dev, PO** | Triết lý thương hiệu, bản vẽ hình học Logo, bảng mã màu semantic CSS, font chữ, khoảng cách an toàn và component `BrandLogo.tsx`. |
| **[`SCREEN_SPECIFICATIONS.md`](SCREEN_SPECIFICATIONS.md)** | **UI/UX Designer, Frontend Developer** | Bố cục wireframe ASCII, thông số chi tiết từng màn hình từ Trợ lý Chat, InBody Dashboard, Quét OCR đến Quản trị ký ức. |
| **[`KE_HOACH_THIET_KE_UI_THUONG_HIEU.md`](KE_HOACH_THIET_KE_UI_THUONG_HIEU.md)** | **Project Lead, Tech Lead, Reviewer** | Lộ trình thi công 7 bước, tiêu chí nghiệm thu (DoD), bảng chuyển đổi ngôn ngữ kỹ thuật sang ngôn ngữ người dùng. |
| **[`assets/README.md`](assets/README.md)** | **Lập trình viên tích hợp (Frontend)** | Danh mục tra cứu nhanh từng tệp ảnh, đường dẫn tĩnh, dung lượng, độ phân giải và mục đích sử dụng. |

---

## 🎨 4. Hệ Thống Màu Sắc & Token Chủ Đạo

```css
:root {
  /* Bảng màu nhận diện thương hiệu BodyWise */
  --brand-primary: #0D9488;        /* Vital Teal 600 - Màu mầm sống chủ đạo */
  --brand-primary-hover: #0F766E;  /* Teal 700 - Hover nút bấm */
  --brand-accent: #0284C7;         /* Bio Sky 600 - Điểm nhấn nước & RAG */
  
  /* Bề mặt & Chữ nền sáng */
  --brand-bg: #F8FAFC;             /* Sứ men Sand dịu mắt */
  --brand-surface: #FFFFFF;        /* Trắng tinh khiết */
  --brand-ink: #0F172A;            /* Đá phiến Slate 900 (Độ tương phản AAA) */
  --brand-muted: #475569;          /* Slate 600 */

  /* Màu trạng thái y tế chuẩn WHO */
  --brand-success: #059669;        /* Emerald 600 - Chỉ số chuẩn WPRO */
  --brand-warning: #D97706;        /* Amber 600 - Cần chú ý điều chỉnh */
  --brand-danger: #E11D48;         /* Coral Rose 600 - Cảnh báo khẩn cấp 115 */
}
```

---

## 🏁 5. Tiêu Chuẩn Nghiệm Thu Giao Diện (Definition of Done)

Một màn hình hoặc tính năng frontend chỉ được xem là hoàn tất thiết kế và nghiệm thu khi:
1. **Tuân thủ nhận diện:** Sử dụng đúng Logo `BodyWise` từ kho vector `/brand/`, đúng màu thương hiệu, không dùng icon placeholder.
2. **Ngôn ngữ người dùng:** Toàn bộ văn bản hiển thị là tiếng Việt có dấu, thân thiện, đã loại bỏ các thuật ngữ nội bộ ("Multi-Agent", "Corpus RAG", "fast_path", "MVP fallback").
3. **An toàn y tế tối thượng:** Cảnh báo khẩn cấp (Urgent) luôn hiển thị nổi bật trên cùng kèm nút gọi **115**, không bị che lấp bởi phản hồi LLM.
4. **Tiêu chuẩn WHO:** Bảng chỉ số thể trạng phân loại chính xác theo ngưỡng WHO Tây Thái Bình Dương (WPRO).
5. **Tiếp cận & Hiệu năng:** Tương phản WCAG 2.2 AA (≥ 4.5:1), có hỗ trợ `prefers-reduced-motion`, tổng dung lượng asset tĩnh web `< 100 KB`.

