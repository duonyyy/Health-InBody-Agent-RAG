# Health / InBody AI — Next.js Modern Frontend

Giao diện người dùng hiện đại xây dựng bằng **Next.js 16 (App Router)**, **TypeScript**, **Tailwind CSS**, và **Recharts** cho dự án Health/InBody Agent RAG.

Được phát triển song song trong thư mục `frontend-next/` nhằm nâng cấp trải nghiệm người dùng từ phiên bản Streamlit cũ mà không làm gián đoạn hay thay đổi mã nguồn gốc trong `frontend/`.

---

## 1. Các Tính năng Cốt lõi Đã Hoàn thiện

### 🩺 1. Trợ lý AI & Hội thoại Đa Tác tử (Multi-Agent Chat)
- **Giao diện hội thoại hiện đại**: Hỗ trợ Markdown đa phương thức, bảng biểu, danh sách chỉ số và khối code.
- **Safety Pre-Check & Banner khẩn cấp**:
  - Tự động hiển thị banner đỏ nhấp nháy khi phát hiện triệu chứng tim mạch/hô hấp nguy cấp (đau ngực, khó thở).
  - Tích hợp nút bấm gọi thẳng đường dây cấp cứu **115**.
  - Không chẩn đoán hoặc kê đơn y khoa theo chuẩn AGENTS.md.
- **Luồng thực thi Multi-Agent (Agent Trace)**:
  - Stepper dạng thu gọn trực quan hóa từng bước xử lý: `safety_pre_check` → `agent_router` → `rag_dense_search` → `response_composer` kèm thời gian thực thi (ms).
- **Trích dẫn Y tế & Kho tri thức (Citations / Evidence)**:
  - Thẻ trích dẫn với điểm số tương đồng ngữ nghĩa (% match), tên tệp tài liệu và nội dung đoạn trích.
- **Meta Chips**:
  - Hiển thị độ trễ mạng (latency ms), loại Fast-path, tác tử được chọn (`medical_safety`, `inbody_analyzer`), và trạng thái nạp hồ sơ cá nhân hóa.
- **Gợi ý câu hỏi nhanh (Quick Prompts)**: 1-click để hỏi về chỉ số InBody, thực đơn tăng cơ giảm mỡ, hoặc test an toàn y tế.

### 📊 2. Chỉ số Thể trạng & InBody (InBody Dashboard)
- **6 Thẻ KPI Thể trạng Trực quan**:
  - **Cân nặng (kg)** kèm delta chênh lệch so với lần đo đầu tiên.
  - **BMI (kg/m²)** theo chuẩn **WHO Châu Á (WPRO)**: Thiếu cân (< 18.5), Bình thường (18.5 - 22.9), Tiền béo phì (23.0 - 24.9), Béo phì (≥ 25.0) kèm thước đo trực quan.
  - **Tỷ lệ Mỡ PBF (%)** phân loại chuẩn theo giới tính sinh học (Nam / Nữ).
  - **Khối lượng Cơ xương SMM (kg)**.
  - **Mỡ Nội tạng (Visceral Fat Level)** với cảnh báo ngưỡng an toàn (Level 1-9) và nguy cơ (≥ 10).
  - **Khối lượng Mỡ BFM (kg)**.
- **Biểu đồ Tiến trình Recharts Timeline**:
  - Chế độ 1: Cân nặng & Khối cơ bắp SMM (Area dual gradient).
  - Chế độ 2: Tỷ lệ mỡ PBF & Khối lượng mỡ BFM.
  - Chế độ 3: Mỡ nội tạng kèm đường tham chiếu an toàn màu đỏ (Reference line y = 9).
- **Ghi nhận Chỉ số Thủ công (Manual Entry)**:
  - Form nhập liệu có validation tức thì.
  - **Tính nhanh BMI & BMR (Mifflin-St Jeor)** ngay khi người dùng gõ cân nặng và chiều cao.
- **Bảng Lịch sử Đo đạc (History Table)**:
  - Bảng danh sách các lần đo xếp theo thời gian mới nhất.
  - Hỗ trợ xóa lần đo với hộp thoại xác nhận an toàn.
- **Quét Phiếu Đo InBody bằng AI (OCR Scanner)**:
  - Kéo thả / tải ảnh phiếu in InBody với hình thu nhỏ xem trước.
  - Tích hợp quy trình PaddleOCR + LLM Gateway.
  - **Bảng đối chiếu & chỉnh sửa số liệu trước khi lưu** (cho phép người dùng kiểm tra lại các số bóc tách được trước khi đưa vào hồ sơ chính thức).

### 🎯 3. Hồ sơ Cá nhân, Mục tiêu & Ký ức (Profile & Goals)
- **Hồ sơ cá nhân**: Tuổi, Giới tính, Chiều cao, Mức độ vận động, Tiền sử bệnh nền/cơ xương khớp, Dị ứng và kiêng cữ thức ăn.
- **Mục tiêu hình thể**: Cân nặng mục tiêu, PBF mục tiêu, SMM mục tiêu, thời hạn hoàn thành.
- **Check-in thể trạng định kỳ**: Đánh giá hoàn thành buổi tập (1-5 sao), năng lượng, giấc ngủ và cảnh báo triệu chứng bất thường.
- **Ký ức Cá nhân hóa (Memory Facts)**: Xem các sự thật mà AI đã học từ hội thoại, hỗ trợ **Xác nhận (Confirm)** hoặc **Xóa (Delete)** từng mục theo đúng quy định bảo vệ dữ liệu sức khỏe.

### 🔍 4. Tra cứu Kho Tri thức & RAG (Corpus Search)
- Tra cứu tài liệu theo chủ đề: Tiêu chuẩn InBody, An toàn y tế & Tim mạch, Dinh dưỡng & Macros, Lịch tập kháng lực.
- Hiển thị điểm số phù hợp (% match) và đoạn trích dẫn.

### ⚙️ 5. Dev Tools & Sandbox
- **Giám sát Trạng thái Backend**: Ping `/health`, kiểm tra độ trễ mạng và trạng thái nền tảng.
- **Hộp cát Kiểm thử Công cụ (Tool Sandbox)**: Chạy thử nghiệm trực tiếp các tool `calculate_bmi_asian`, `calculate_tdee_and_macros`, và `deterministic_safety_guardrail` với kết quả JSON tức thì.
- **Cấu hình API linh hoạt**: Modal trong Header cho phép đổi URL backend (mặc định `http://localhost:8000`).
- **Chế độ Ngoại tuyến Tự phục hồi (Offline Fallback Engine)**: Nếu backend offline, giao diện vẫn hoạt động trơn tru với dữ liệu mẫu chân thực và thuật toán mô phỏng deterministic an toàn.

---

## 2. Hướng dẫn Khởi chạy

### Yêu cầu môi trường
- **Node.js**: phiên bản `>= 20` (đã kiểm thử tương thích hoàn hảo trên Node v22)
- **npm**: `>= 10`

### Chạy chế độ Phát triển (Development)
```bash
cd frontend-next
npm run dev
```
Ứng dụng sẽ mở tại `http://localhost:3000`.

### Biên dịch & Chạy Production
```bash
cd frontend-next
npm run build
npm start
```

### Chạy bằng Docker
```bash
cd frontend-next
docker compose up -d --build
```
Ứng dụng sẽ phục vụ tại cổng `3000`.

---

## 3. Cấu trúc Thư mục

```
frontend-next/
├── src/
│   ├── app/
│   │   ├── layout.tsx                # Cấu hình font Google, SEO metadata tiếng Việt
│   │   ├── page.tsx                  # Điều phối Sidebar, Header, và 5 Tabs
│   │   └── globals.css               # Hệ màu Sleek Dark, Glassmorphism, Glow
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx           # Thanh điều hướng trái + Ping backend health
│   │   │   └── Header.tsx            # Tiêu đề, tóm tắt KPI nhanh, modal cấu hình
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx     # Luồng chat cuộn mượt mà
│   │   │   ├── MessageBubble.tsx     # Bong bóng tin nhắn + Markdown renderer
│   │   │   ├── SafetyBanner.tsx      # Cảnh báo an toàn y tế khẩn cấp / Hotline 115
│   │   │   ├── MetaChips.tsx         # Latency, route, fast-path tags
│   │   │   ├── AgentTraceView.tsx    # Stepper trực quan hóa multi-agent steps
│   │   │   ├── CitationsView.tsx     # Bằng chứng & trích dẫn tài liệu
│   │   │   └── QuickPrompts.tsx      # Gợi ý câu hỏi mẫu nhanh
│   │   ├── inbody/
│   │   │   ├── InBodyDashboard.tsx   # Dashboard tổng hợp InBody
│   │   │   ├── KpiCard.tsx           # Thẻ KPI kèm thanh đo gauge phân loại
│   │   │   ├── ProgressChart.tsx     # Biểu đồ Recharts timeline 3 chế độ
│   │   │   ├── MeasurementForm.tsx   # Form nhập liệu + tính nhanh BMI/BMR
│   │   │   ├── MeasurementHistoryTable.tsx # Bảng lịch sử đo đạc & xóa
│   │   │   └── OcrScanner.tsx        # Kéo thả ảnh & bóc tách AI OCR
│   │   ├── profile/
│   │   │   └── ProfileAndGoals.tsx   # Hồ sơ cá nhân, check-in & quản lý ký ức
│   │   ├── search/
│   │   │   └── CorpusSearch.tsx      # Tra cứu vector corpus tài liệu y tế
│   │   └── dev/
│   │       └── DevTools.tsx          # Ping health & Sandbox thử nghiệm công cụ
│   ├── lib/
│   │   ├── api.ts                    # Client gọi API FastAPI, timeout, error fallback
│   │   ├── classifiers.ts            # Phân loại WHO Châu Á (BMI, PBF, Visceral Fat)
│   │   └── mockData.ts               # Dữ liệu mẫu chuẩn thể trạng người Việt
│   └── types/
│       └── index.ts                  # Toàn bộ TypeScript interfaces chuẩn
├── Dockerfile                        # Multi-stage production build
├── docker-compose.yml                # Cấu hình container port 3000
└── package.json
```
