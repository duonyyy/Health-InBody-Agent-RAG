# 📱 BodyWise — Đặc Tả Chi Tiết Các Màn Hình Hệ Thống (Screen Specifications)

> **Tài liệu đặc tả kỹ thuật giao diện & trải nghiệm người dùng (UI/UX Specifications)**  
> **Dự án:** Health / InBody AI Agent RAG — **BodyWise**  
> **Phiên bản:** 1.0 · Cập nhật: 2026-11-04  
> **Tiêu chuẩn kỹ thuật:** Next.js 16 (App Router), React 19, TypeScript Strict Mode, Tailwind CSS v4, Recharts, Lucide Icons.  
> **Nguyên tắc thiết kế tối thượng:** **An toàn y tế > Quyền riêng tư (WCAG 2.2 AA) > Khoa học chuẩn xác > Nhất quán thương hiệu.**

---

## 🗺️ 0. Ma Trận Màn Hình Hệ Thống (Master Screen Matrix)

| Mã Màn Hình | Tên Màn Hình & Phân Hệ | Đường Dẫn / Trạng Thái | Vai Trò Người Dùng | Mức Độ Ưu Tiên |
| :--- | :--- | :--- | :--- | :---: |
| **SCR-01** | Khung Vỏ Ứng Dụng & Điều Hướng (Application Shell & Navigation) | Layout Toàn Cục | Tất cả người dùng | **P0 (Cốt lõi)** |
| **SCR-02** | Trợ Lý AI & Hội Thoại Đa Tác Tử (Multi-Agent Assistant & Chat) | `/` (Tab: `chat`) | Tất cả người dùng | **P0 (Cốt lõi)** |
| **SCR-03** | Chỉ Số Thể Trạng & Bảng Điều Khiển InBody (InBody Dashboard) | `/` (Tab: `inbody`) | Người theo dõi thể trạng | **P0 (Cốt lõi)** |
| **SCR-04** | Quét Phiếu Đo InBody Bằng AI (OCR Smart Scanner) | `/` (Modal / Sub-view) | Người có phiếu in InBody | **P1 (Quan trọng)** |
| **SCR-05** | Hồ Sơ Cá Nhân, Mục Tiêu & Ký Ức AI (Profile, Goals & Memory) | `/` (Tab: `profile`) | Người dùng cá nhân hóa | **P1 (Quan trọng)** |
| **SCR-06** | Thư Viện Kiến Thức & Tra Cứu Corpus RAG (Knowledge Search) | `/` (Tab: `search`) | Người tìm kiếm tài liệu | **P2 (Hỗ trợ)** |
| **SCR-07** | Hộp Cát Kỹ Thuật & Giám Sát Nền Tảng (Dev Tools & Sandbox) | `/` (Tab: `dev`) | Kỹ sư / Giảng viên kiểm thử | **Internal (Dev)** |

---

## 🖥️ SCR-01: Khung Vỏ Ứng Dụng & Điều Hướng (Application Shell & Navigation)

### 1.1. Mục Tiêu Nghiệp Vụ & Đối Tượng
Cung cấp khung điều hướng nhất quán, vững chãi, tải trang tức thì, hỗ trợ chuyển đổi giữa các phân hệ nghiệp vụ chính (Trò chuyện AI, Bảng chỉ số InBody, Hồ sơ, Tra cứu kiến thức và Bảng điều khiển kỹ thuật).

### 1.2. Cấu Trúc Bố Cục (ASCII Layout Structure)
```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TOP HEADER: [Logo BodyWise (Mobile)] | [Thống kê nhanh: 72.4kg • PBF 19.5%] | [Backend: Online]   │
├──────────────┬───────────────────────────────────────────────────────────────────────────────────┤
│ SIDEBAR      │ MAIN CONTENT AREA (Vùng hiển thị nội dung phân hệ được kích hoạt)                │
│ [BrandLogo]  │                                                                                   │
│              │                                                                                   │
│ 💬 Trợ lý AI  │                                                                                   │
│ 📊 InBody    │                                                                                   │
│ 👤 Hồ sơ     │                                                                                   │
│ 📚 Thư viện  │                                                                                   │
│ ⚙️ Kỹ thuật  │                                                                                   │
│              │                                                                                   │
│ ──────────── │                                                                                   │
│ User: Admin  │                                                                                   │
│ [Ping: 24ms] │                                                                                   │
└──────────────┴───────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3. Thành Phần Giao Diện & Quy Chuẩn Tương Tác
- **Thanh Điều Hướng Bên Trái (Sidebar Desktop):**
  - Chiều rộng: Cố định `288px` (Expanded) và hỗ trợ thu gọn `72px` (Collapsed).
  - Vị trí Logo: Sử dụng `BrandLogo` (`/brand/logo-horizontal-dark.svg` trên nền tối hoặc `logo-mark.svg` khi thu nhỏ).
  - Danh sách Menu mục:
    1. **Trợ lý AI & Chat** (Icon: `MessageSquare`, Badge: `Multi-Agent`)
    2. **Thể trạng & InBody** (Icon: `Activity`, Badge: `5 Chỉ số`)
    3. **Hồ sơ & Mục tiêu** (Icon: `UserCheck`)
    4. **Thư viện kiến thức** (Icon: `Search` - thay thế cho từ nội bộ "Tra cứu Corpus RAG")
    5. **Kiểm tra hệ thống** (Icon: `Sliders` - chỉ hiển thị trong môi trường development hoặc khi bật chế độ nhà phát triển).
- **Thanh Trạng Thái Nền Tảng (System Status Footer):**
  - Hiển thị chấm tròn trạng thái kết nối Backend (`bg-emerald-400` khi bình thường, `bg-rose-400` khi mất kết nối).
  - Hiển thị độ trễ mạng (Ping ms) và phiên bản nền tảng.
- **Thanh Điều Hướng Di Động (Bottom Mobile Nav):**
  - Tự động hiển thị trên màn hình `< 768px` dạng 4 nút bấm cố định dưới đáy màn hình với chiều cao tương tác `60px` đạt chuẩn WCAG.

---

## 💬 SCR-02: Phân Hệ Trợ Lý AI & Hội Thoại Đa Tác Tử (Multi-Agent Chat)

### 2.1. Mục Tiêu Nghiệp Vụ & Quy Tắc An Toàn Tối Thượng
Hỗ trợ hội thoại tự nhiên về chỉ số thể trạng, tư vấn dinh dưỡng tái tạo cơ mỡ, đề xuất lịch tập và giải thích cặn kẽ thuật ngữ y sinh. **Tuyệt đối tuân thủ deterministic safety pre-check trước khi gọi LLM/RAG.**

### 2.2. Bố Cục Màn Hình Chi Tiết
```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER KHUNG CHAT: "Trợ lý Thể trạng & Dinh dưỡng AI" | Nút [Xóa hội thoại]                       │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ KHUNG DANH SÁCH TIN NHẮN (Cuộn mượt mà, tự động bám đáy):                                        │
│                                                                                                  │
│ [THỜI ĐIỂM: 23:30]                                                                               │
│                                                                                                  │
│ 👤 NGƯỜI DÙNG: "Tôi bị đau ngực dữ dội và khó thở khi đang tập gym, tôi nên uống gì?"           │
│                                                                                                  │
│ 🚨 KHỐI CẢNH BÁO KHẨN CẤP (URGENT SAFETY BANNER):                                               │
│ ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ CẢNH BÁO NGUY HIỂM TÍNH MẠNG - CẦN CẤP CỨU Y TẾ NGAY LẬP TỨC                             │ │
│ │ Triệu chứng đau ngực và khó thở cấp tính có thể là dấu hiệu của hội chứng mạch vành cấp tính. │ │
│ │ KHÔNG TỰ UỐNG NƯỚC/THUỐC. Hãy ngừng vận động ngay lập tức và liên hệ trợ giúp y tế!          │ │
│ │                                                                                              │ │
│ │ [ 📞 GỌI CẤP CỨU 115 NGAY ]                  [ 📍 Tìm cơ sở y tế gần nhất ]                   │ │
│ └──────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                  │
│ 🤖 BODYWISE AI: (Fast-path: Đã kích hoạt bảo vệ an toàn y tế trong 42ms)                         │
│                                                                                                  │
│ ──────────────────────────────────────────────────────────────────────────────────────────────── │
│ [ ⚡ Đa tác tử: medical_safety ]  [ ⏱️ 42ms ]  [ 🔒 Quyền riêng tư: Đã bảo vệ ]                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
│ KHUNG SOẠN THẢO: [ Nhập câu hỏi về InBody, thực đơn, bài tập... ] [ 🚀 Gửi ]                     │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3. Quy Chuẩn Thành Phần & Các Trạng Thái An Toàn
1. **Khối Cảnh Báo An Toàn Khẩn Cấp (`SafetyBanner.tsx`):**
   - **Mức độ Urgent:** Nền đỏ đậm `--brand-danger-soft` (`#FFF1F2`), viền đỏ dày `2px`, icon chuông cảnh báo rung nhẹ theo nhịp dịu mắt, nút **GỌI CẤP CỨU 115** nổi bật với kích thước chạm ≥ 48px. **Không gọi LLM, không sinh văn bản giả định.**
   - **Mức độ Caution:** Nền vàng mật ong `--brand-warning-soft`, hiển thị lời nhắc tham vấn ý kiến chuyên gia sức khỏe hoặc bác sĩ khi người dùng hỏi về các bệnh lý nền (tiểu đường, tim mạch, thoái hóa khớp).
2. **Khối Trích Dẫn Y Tế & Minh Chứng RAG (`CitationsView.tsx`):**
   - Mỗi đoạn tư vấn chuyên sâu đều hiển thị danh sách nguồn trích dẫn: Tên tài liệu nghiên cứu, trang/mục tham chiếu, và mức độ tương đồng ngữ nghĩa (% match).
   - Cho phép người dùng bấm để mở hộp thoại đọc lại đoạn văn gốc trong kho tư liệu đã đối soát.
3. **Khối Theo Dõi Luồng Tác Tử (`AgentTraceView.tsx`):**
   - Hiển thị luồng thực thi từng bước dưới dạng biểu đồ tiến trình:
     `Safety Pre-check` $\rightarrow$ `Router Phân loại` $\rightarrow$ `RAG Dense Retrieval` $\rightarrow$ `Tổng hợp phản hồi`.
   - Giúp sinh viên và giảng viên kiểm tra tính minh bạch của giải thuật Agentic RAG.
4. **Dòng Miễn Trừ Trách Nhiệm Pháp Lý Cố Định:**
   - Dưới mỗi câu trả lời sức khỏe: *"Thông tin được cung cấp bởi trợ lý AI chỉ mang tính chất tham khảo khoa học, không thay thế chẩn đoán hay phác đồ điều trị của bác sĩ chuyên khoa."*

---

## 📊 SCR-03: Phân Hệ Chỉ Số Thể Trạng & Bảng Điều Khiển InBody (InBody Dashboard)

### 3.1. Mục Tiêu Nghiệp Vụ
Trực quan hóa toàn diện 6 chỉ số nhân trắc học cốt lõi từ phiếu đo InBody, đối chiếu theo tiêu chuẩn **WHO Tây Thái Bình Dương (WPRO)** dành cho thể tạng người Việt Nam/Châu Á.

### 3.2. Bố Cục Bảng Điều Khiển (Dashboard Layout)
```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TIÊU ĐỀ: BẢNG CHỈ SỐ THỂ TRẠNG INBODY | Lần đo gần nhất: 04/11/2026 | [ ➕ Thêm lần đo ] [ 📷 Quét ]│
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6 THẺ KPI THỂ TRẠNG TRỰC QUAN (Grid 3 cột × 2 dòng):                                             │
│                                                                                                  │
│ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐      │
│ │ ⚖️ CÂN NẶNG TOÀN THẦN      │ │ 📏 CHỈ SỐ BMI (WHO CHÂU Á)│ │ 💧 TỶ LỆ MỠ CƠ THỂ (PBF)  │      │
│ │ 72.4 kg                   │ │ 22.8 kg/m²                │ │ 19.5 %                    │      │
│ │ ▼ -1.2 kg so với tháng trước│ │ [ Bình thường: 18.5-22.9 ] │ │ [ Chuẩn nam giới: 10-20% ] │      │
│ │ [========•==========] 100%│ │ [=======•===========] 22.8│ │ [==========•========] 19.5│      │
│ └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘      │
│ ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐      │
│ │ 💪 CƠ BẮP XƯƠNG (SMM)     │ │ 🛡️ CẤP ĐỘ MỠ NỘI TẠNG     │ │ 🧈 KHỐI LƯỢNG MỠ (BFM)    │      │
│ │ 33.8 kg                   │ │ Cấp độ 6 / 20             │ │ 14.1 kg                   │      │
│ │ ▲ +0.8 kg tăng cơ tốt     │ │ [ Mức an toàn: Cấp 1 - 9 ]│ │ [ Bình thường ]           │      │
│ └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘      │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ BIỂU ĐỒ TIẾN TRÌNH THEO THỜI GIAN (RECHARTS TIMELINE):                                           │
│ [ Chế độ: Cân nặng & Cơ bắp SMM ]   [ Tỷ lệ mỡ PBF ]   [ Mỡ nội tạng & Ngưỡng nguy cơ ]          │
│                                                                                                  │
│  76kg ─┬──────────────────────────────────────────────────────────────────                       │
│        │        ╭───╮                                                                            │
│  74kg ─┼───────╭╯   ╰╮                                                                           │
│        │  ╭───╮│     ╰───╮             ╭───╮ (Cân nặng kg)                                       │
│  72kg ─┼─╭╯   ╰╯         ╰─────────────╯   ╰────── 72.4kg                                        │
│  34kg ─┼───────────────────────────────╭───────╮ (Cơ xương SMM)                                  │
│  32kg ─┼─╰─────────────────────────────╯       ╰── 33.8kg                                        │
│        └─────┬───────────┬───────────┬───────────┬────────►                                      │
│             Th08        Th09        Th10        Th11                                             │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ BẢNG LỊCH SỬ CÁC LẦN ĐO ĐÃ ĐỐI SOÁT (History Table) kèm nút [Xuất CSV] và [Xóa bản ghi]          │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3. Quy Chuẩn Phân Loại Chỉ Số Chuẩn WHO Châu Á (WPRO)
- **Chỉ số BMI (Body Mass Index):**
  - `< 18.5`: Thiếu cân (Màu xanh da trời `#0284C7`)
  - `18.5 – 22.9`: Thể trạng chuẩn / Bình thường (Màu xanh ngọc `#059669`)
  - `23.0 – 24.9`: Tiền béo phì / Thừa cân (Màu vàng hổ phách `#D97706`)
  - `≥ 25.0`: Béo phì (Màu cam đậm `#C2410C`)
- **Tỷ lệ Mỡ PBF (Percent Body Fat):**
  - Nam: Thiếu mỡ (< 10%), Chuẩn (10% - 20%), Thừa mỡ (> 20%).
  - Nữ: Thiếu mỡ (< 18%), Chuẩn (18% - 28%), Thừa mỡ (> 28%).
- **Cấp độ Mỡ Nội Tạng (Visceral Fat Level):**
  - `Mức 1 – 9`: Ngưỡng an toàn bảo vệ tim mạch.
  - `≥ Mức 10`: Ngưỡng nguy cơ cao đối với bệnh chuyển hóa (Hiển thị nhãn cảnh báo đỏ và khuyến nghị đi khám tổng quát).

---

## 📷 SCR-04: Phân Hệ Quét Phiếu Đo InBody Bằng AI (OCR Smart Scanner)

### 4.1. Mục Tiêu Nghiệp Vụ & Luồng Xử Lý
Giúp người dùng không phải gõ tay từng con số phức tạp trên phiếu kết quả InBody bằng cách chụp ảnh hoặc kéo thả tệp hình ảnh vào hệ thống. Sử dụng kết hợp mô hình PaddleOCR cùng bộ lọc cấu trúc để trích xuất chuẩn xác các trường: Cân nặng, Chiều cao, BMI, PBF, SMM, VFL.

### 4.2. Luồng Trải Nghiệm 3 Bước Chặt Chẽ (3-Step Guided Flow)
```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODAL: QUÉT PHIẾU ĐO INBODY BẰNG TRÍ TUỆ NHÂN TẠO                                               │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ BƯỚC 1: TẢI ẢNH PHIẾU ĐO       BƯỚC 2: ĐỐI CHIẾU SỐ LIỆU (AI)      BƯỚC 3: LƯU VÀO HỒ SƠ         │
│ (Hoàn tất) [✓] ───────────────► (Đang thực hiện) [●] ─────────────► (Chờ) [ ]                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ẢNH CHỤP GỐC:                     │ BẢNG ĐỐI CHIẾU SỐ LIỆU ĐÃ BÓC TÁCH (Cho phép sửa tay):       │
│ ┌───────────────────────────────┐ │                                                              │
│ │ [ Ảnh phiếu InBody 270/770 ]  │ │ 1. Cân nặng (Weight):      [ 72.4 ] kg     (Độ tin cậy: 99%) │
│ │                               │ │ 2. Tỷ lệ mỡ (PBF):         [ 19.5 ] %      (Độ tin cậy: 98%) │
│ │ • Nhận diện ngày: 04/11/2026  │ │ 3. Cơ bắp xương (SMM):     [ 33.8 ] kg     (Độ tin cậy: 97%) │
│ │ • Tên máy: InBody 270         │ │ 4. Mỡ nội tạng (VFL):      [ 6    ] Level  (Độ tin cậy: 95%) │
│ │                               │ │ 5. Chiều cao (Height):     [ 178  ] cm     (Độ tin cậy: 99%) │
│ │ 🔒 Không lưu trữ ảnh chứa CMND│ │                                                              │
│ └───────────────────────────────┘ │ 💡 Bạn hãy kiểm tra lại và chỉnh sửa số liệu nếu cần trước  │
│                                   │    khi bấm lưu vào hồ sơ chính thức.                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ NÚT HÀNH ĐỘNG: [ Hủy bỏ ]                                  [ Chấp nhận & Lưu vào Bảng theo dõi ] │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3. Bảo Mật Dữ Liệu & Quyền Riêng Tư (Privacy Guardrails)
- Hệ thống chỉ bóc tách các trường số học thể trạng, tự động bỏ qua thông tin nhạy cảm như Tên đầy đủ, Số điện thoại hoặc ID phòng tập.
- Ảnh tải lên được xử lý trong bộ nhớ tạm (in-memory) và không lưu trữ vĩnh viễn trên máy chủ nếu người dùng không yêu cầu.

---

## 👤 SCR-05: Phân Hệ Hồ Sơ Cá Nhân, Mục Tiêu Thể Hình & Quản Trị Ký Ức (Profile, Goals & Memory)

### 5.1. Mục Tiêu Nghiệp Vụ
Quản lý thông tin thể chất nền tảng, thiết lập mục tiêu hình thể mong muốn, và đặc biệt là **bảng minh bạch ký ức cá nhân hóa (Memory Facts)** tuân thủ nguyên tắc người dùng toàn quyền kiểm soát dữ liệu cá nhân.

### 5.2. Các Phân Khu Chức Năng
1. **Thông Tin Nhân Trắc & Sức Khỏe Nền Tảng:**
   - Tuổi, Giới tính sinh học (ảnh hưởng trực tiếp đến công thức tính PBF và BMR).
   - Chiều cao (cm), Mức độ vận động hàng ngày (Sedentary, Light, Moderate, Very Active).
   - Tiền sử chấn thương xương khớp (thoát vị đĩa đệm, đau khớp gối) và Dị ứng thức ăn (dị ứng lactose, hải sản, gluten).
2. **Mục Tiêu Thể Trạng (Fitness Goals):**
   - Định hướng: Giảm mỡ tăng cơ (Recomposition), Tăng cân tăng cơ (Lean Bulk), hoặc Cắt giảm mỡ thừa (Fat Loss).
   - Mục tiêu cụ thể: Cân nặng đích, PBF đích, SMM đích và Thời hạn hoàn thành.
3. **Bảng Quản Trị Ký Ức AI (Transparent Memory Facts Console):**
   - Hiển thị danh sách các "sự thật" mà AI đã tự động học từ các phiên chat.
   - Ví dụ:
     - `Fact 01`: *"Người dùng không dung nạp đường lactose trong sữa bò."* $\rightarrow$ Nút [Xác nhận] / [Xóa].
     - `Fact 02`: *"Người dùng bị đau khớp gối trái khi chạy bộ quá 30 phút."* $\rightarrow$ Nút [Xác nhận] / [Xóa].
   - **Quy tắc:** Bấm "Xóa" sẽ kích hoạt API xóa hoàn toàn vector embedding tương ứng trong cơ sở dữ liệu ký ức.

---

## 📚 SCR-06: Phân Hệ Thư Viện Kiến Thức & Tra Cứu Corpus RAG (Knowledge Search)

### 6.1. Mục Tiêu Nghiệp Vụ
Cho phép người dùng chủ động khám phá và tra cứu kho tài liệu y sinh, hướng dẫn phân tích InBody, nguyên lý dinh dưỡng và kỹ thuật vận động đã được thẩm định.

### 6.2. Thành Phần Giao Diện
- **Bộ Lọc Phân Loại Danh Mục:**
  - `Tất cả` | `Tiêu chuẩn InBody` | `An toàn Y tế & Tim mạch` | `Dinh dưỡng & Macros` | `Lịch tập Kháng lực`.
- **Thẻ Kết Quả Tra Cứu:**
  - Tiêu đề tài liệu khoa học, tác giả/cơ quan xuất bản.
  - Đoạn trích dẫn nội dung trọng tâm.
  - Điểm tương đồng ngữ nghĩa (% match).
  - Nút sao chép nội dung trích dẫn vào khung chat với AI.

---

## ⚙️ SCR-07: Hộp Cát Kỹ Thuật & Giám Sát Nền Tảng (Dev Tools & Sandbox)

### 7.1. Mục Tiêu Nghiệp Vụ & Giới Hạn Truy Cập
Công cụ phục vụ đội ngũ kỹ sư, giảng viên đánh giá và chấm đồ án. **Mặc định bị ẩn trong môi trường production.**

### 7.2. Các Chức Năng Cốt Lõi
- **Bảng Giám Sát Sức Khỏe Hạ Tầng (Infrastructure Health Matrix):**
  - Kiểm tra trạng thái và thời gian phản hồi của:
    - FastAPI Backend Gateway (`/health`)
    - Vector Database Qdrant (Collection: `health_inbody_corpus_v1`)
    - Bộ nhớ đệm Valkey (In-memory Cache & Rate Limit)
    - Mô hình BGE-M3 Embedding Serving
    - Cơ sở dữ liệu quan hệ PostgreSQL
- **Hộp Cát Kiểm Thử Thuật Toán (Deterministic Tool Sandbox):**
  - Chạy thử nghiệm trực tiếp công cụ `calculate_bmi_asian` với các tham số đầu vào tùy ý và xem ngay kết quả phân loại chuẩn WPRO.
  - Chạy thử nghiệm công cụ `calculate_tdee_and_macros` theo công thức Mifflin-St Jeor.
  - Thử nghiệm bộ lọc `deterministic_safety_guardrail` với các câu hỏi bẫy khẩn cấp để kiểm chứng thời gian phản hồi P95 < 500ms không gọi LLM.
