  # 🎨 CẨM NANG THIẾT KẾ & ĐẶC TẢ SẢN XUẤT CHO DESIGNER
  ## Health / InBody AI Agent Platform (BodyWise) — Production Playbook & Creative Asset Specs

  **Dành cho:** Brand Designer, 3D Artist, UI/UX Designer & Motion Artist  
  **Phong cách nghệ thuật:** **Bio-Porcelain & Vital Teal** *(Y Sinh Hiện Đại · Tinh Thể Sứ Men Sinh Học & Khối Chuyển Hóa Năng Lượng · Điềm Tĩnh & Đáng Tin Cậy)*  
  **Hệ màu chủ đạo:** Porcelain Sand `#F8FAFC` · Deep Slate `#0F172A` · Vital Teal `#0D9488` · Bio Sky `#0284C7` · Emerald Jade `#059669` · Coral Rose `#E11D48`  
  **Phiên bản:** 2.0 (Designer Execution Ready) · Cập nhật: 2026

  ---

  ## 🧭 LỜI DẪN CHO NHÀ THIẾT KẾ

  Tài liệu này được biên soạn theo **ngôn ngữ chuyên ngành của người làm thiết kế (Designers, 3D Modeler & Motion Artists)**. Bạn không cần đọc mã nguồn backend, thuật toán LangGraph hay giải thuật vector search. 

  Mục tiêu duy nhất của bạn: **Mở tài liệu này ra, nắm bắt chuẩn xác tinh thần thị giác, lấy đúng mã màu PBR, mở Blender/C4D/Figma/Illustrator và sản xuất chính xác từng tài sản đồ họa** theo đúng thông số, góc máy, nguồn sáng và tên tệp chuẩn tiếng Việt snake_case để đội ngũ kỹ thuật frontend ráp trực tiếp vào hệ thống mà không phải tinh chỉnh lại bất kỳ pixel nào.

  ---

  ## 🏛️ PHẦN 1: ĐỊNH HƯỚNG NGHỆ THUẬT & KHÔNG GIAN THỊ GIÁC (MOOD & TONE)

  ### 1.1. Tinh Thần Nghệ Thuật: "Bio-Porcelain & Vital Teal"
  Chúng ta đang xây dựng **Trợ lý AI Đa Tác Tử về Thể Trạng & Dinh Dưỡng Chuyên Sâu (BodyWise)**, phục vụ theo dõi chỉ số InBody, tái tạo cơ mỡ khoa học và bảo vệ an toàn y tế.

  ```text
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │ CẢM XÚC THỊ GIÁC MỤC TIÊU (DO)                                                  │
  │ ✓ Điềm tĩnh, đáng tin cậy, khoa học và vệ sinh như thiết bị y sinh cao cấp.    │
  │ ✓ Khối 3D dạng gốm sứ men mịn màng (Bio-Porcelain Matte) phối hợp kính mờ.       │
  │ ✓ Các đường dẫn năng lượng sinh học (Vitality Arcs) màu Teal & Cyan sắc sảo.   │
  │ ✓ Ánh sáng studio y khoa dịu mắt (Soft Medical Daylight 5500K), bóng đổ nông.  │
  │ ✓ Tôn trọng người dùng: Hình ảnh minh họa thân thiện, không phán xét ngoại hình.│
  │                                                                                 │
  │ ĐIỀU TUYỆT ĐỐI CẤM (DON'T)                                                      │
  │ ❌ KHÔNG dùng biểu tượng chữ thập đỏ (Red Cross) hoặc hình ống nghe bệnh viện.  │
  │ ❌ KHÔNG vẽ người cơ bắp cuồn cuộn phi thực tế hoặc hình ảnh body-shaming.      │
  │ ❌ KHÔNG dùng hiệu ứng neon gay gắt, gradient tím hồng vũ trường cyberpunk.     │
  │ ❌ KHÔNG vẽ robot mắt cười hoạt hình chibi hay icon trẻ con thiếu nghiêm túc.   │
  │ ❌ KHÔNG dùng bóng đổ phát sáng (Glow) nhòe nhoẹt vi phạm độ tương phản mắt.   │
  └─────────────────────────────────────────────────────────────────────────────────┘
  ```

  ### 1.2. Thư Viện Vật Liệu 3D (PBR Material Settings cho 3D Artists)
  Khi thiết lập shader trong **Blender (Cycles/Eevee)** hoặc **Cinema 4D (Octane/Redshift)**:

  | Tên Vật Liệu | Màu Albedo (Base Color) | Roughness (Độ nhám) | Metallic (Kim loại) | Đặc tính quang học khác | Ứng dụng trong cảnh |
  | :--- | :--- | :---: | :---: | :--- | :--- |
  | **Bio-Porcelain (Sứ Men Sinh Học)** | `#F8FAFC` hoặc `#F1F5F9` | `0.40 – 0.50` | `0.00` | Subsurface Scattering nhẹ (`0.08`, màu ấm `#FFFBEB`) | Thân vỏ máy đo, bục đỡ khối, thẻ chỉ số |
  | **Deep Slate Graphite (Đá Phiến)** | `#0F172A` | `0.75` | `0.05` | Tán xạ mờ chống lóa, tương phản cao | Khối đế kỹ thuật, khung viền ngoài |
  | **Vital Teal Crystal (Ngọc Lục Thể)** | `#0D9488` | `0.25` | `0.10` | Transmission (`0.35`), độ phát quang sinh học dịu | Lõi mầm sống (Vital Spark), khối cơ SMM |
  | **Hydration Sky Glass (Thủy Tinh Nước)** | `#0284C7` $\rightarrow$ `#38BDF8` | `0.10 – 0.20` | `0.00` | Transmission (`0.92`), IOR (`1.33` - chỉ số khúc xạ nước) | Cung nước chuyển hóa, ống nghiệm dữ liệu |
  | **Emerald Tissue (Mô Sinh Học An Toàn)** | `#059669` | `0.45` | `0.00` | Tán xạ bề mặt nhẹ, màu ngọc bích tươi tắn | Huy hiệu đạt chuẩn WHO, vùng chỉ số an toàn |
  | **Medical Coral (San Hô Cảnh Báo)** | `#E11D48` | `0.30` | `0.05` | Màu đỏ san hô đĩnh đạc, không chói gắt | Khiên an toàn cấp cứu 115, vùng mỡ nội tạng cao |

  ---

  ## 🎨 PHẦN 2: BẢNG THÔNG SỐ MÀU CHUẨN (EXACT COLOR PALETTE)

  Toàn bộ sản phẩm thiết kế 2D & 3D phải tuân thủ tuyệt đối dải màu sRGB chuẩn sau:

  ```text
        CANVAS                 SLATE                  VITAL TEAL              BIO SKY
        #F8FAFC                 #0F172A                 #0D9488                #0284C7
    R:248 G:250 B:252        R:15 G:23 B:42          R:13 G:148 B:136        R:2 G:132 B:199
  [Nền Sứ Bio-Sand]      [Thanh Điều Hướng]      [Lõi Chuyển Hóa & CTA]  [Nước Tế Bào & RAG]
  ```

  ### Chi tiết thông số màu kỹ thuật:
  - **Canvas Sứ Men Sáng:** `#F8FAFC` (RGB: `248, 250, 252`) — Nền sáng dịu mắt, chống mỏi mắt cho màn hình đọc dữ liệu.
  - **Deep Slate Navy:** `#0F172A` (RGB: `15, 23, 42`) — Màu đá phiến than chì sâu thẳm, nền chế độ tối và thanh điều hướng.
  - **Vital Teal (Chủ Đạo):** `#0D9488` (RGB: `13, 148, 136`) — Đại diện cho sự sống, mầm sống tế bào và cân bằng cơ thể.
  - **Teal Light (Phát Quang):** `#14B8A6` (RGB: `20, 184, 166`) — Dùng cho vạch sáng tiến trình, hiệu ứng tương tác active.
  - **Bio Sky (Dữ Liệu & Nước):** `#0284C7` (RGB: `2, 132, 199`) — Đại diện cho tỷ lệ nước cơ thể, trích dẫn tài liệu y khoa RAG.
  - **Sky Light:** `#38BDF8` (RGB: `56, 189, 248`) — Điểm nhấn công nghệ AI và luồng xử lý Agent.
  - **Emerald Jade (An Toàn / Đạt Chuẩn):** `#059669` (RGB: `5, 150, 105`) — Thể trạng chuẩn WHO WPRO, phản hồi đã lưu thành công.
  - **Amber Gold (Cảnh Báo Lưu Tâm):** `#D97706` (RGB: `217, 119, 6`) — Cảnh báo tiền béo phì, chỉ số cần điều chỉnh dinh dưỡng.
  - **Coral Rose (Khẩn Cấp Y Tế):** `#E11D48` (RGB: `225, 29, 72`) — Dành riêng cho chốt chặn cấp cứu 115 và mỡ nội tạng nguy cơ cao.
  - **Technical Hairline:** `#E2E8F0` (RGB: `226, 232, 240`) — Đường kẻ viền mỏng 1px ngăn cách bảng biểu.

  ---

  ## 📐 PHẦN 3: BẢN VẼ KỸ THUẬT LOGO & BIỂU TƯỢNG (LOGO BLUEPRINT)

  ### 3.1. Hình Học Biểu Tượng: "The Vitality Orbit & Spark" (Vòng Thể Trạng & Mầm Sống)
  Biểu tượng chính thức kết hợp giữa **Cấu trúc vòng cung thành phần cơ thể (Body Composition Rings)** và **Mầm sống trung tâm (Vital Spark)**:

  ```text
                      ╭─────────────╮
                    ╭──╯   Cung Cơ   ╰──╮  ← 1. Vòng cung ngoài: Khối cơ & Cân bằng (Teal #14B8A6)
                  ╭─╯      (SMM)        ╰─╮
                ╭╯    ╭───────────╮      ╰╮
                │     ╭╯  Cung Nước ╰╮     │ ← 2. Vòng cung trong: Lượng nước & Trao đổi chất (Sky #38BDF8)
                │    │    (Nước/PBF)  │    │
                │    │      ╭───╮     │    │
                │    │     │ 🌿  │    │    │ ← 3. Mầm sống trung tâm: Vital Spark (#0D9488)
                │    │     │  •  │    │    │      (Hạt nhân trắng tuyết #FFFFFF)
                │    │      ╰───╯     │    │
                │     ╰╮             ╭╯    │
                ╰─╮   ╰───────────╯     ╭─╯
                  ╰──╮               ╭──╯
                      ╰───────────────╯
  ```

  ### 3.2. Quy Chuẩn Kích Thước & Vùng An Toàn (Clear Space)
  - **Vùng an toàn (Clear Space $X$):** Bằng $1/4$ chiều cao biểu tượng. Tuyệt đối không đặt chữ, đường viền hay icon khác vào vùng đệm này.
  - **Kích thước hiển thị tối thiểu:**
    - Bản in giấy/tài liệu: Chiều cao tối thiểu `12mm`.
    - Màn hình số: Chiều cao tối thiểu `16px` đối với Favicon, `28px` đối với Logo mark thu gọn, và `36px` đối với Logo ngang đầy đủ.

  ### 3.3. Typography Đi Kèm (Wordmark Specs)
  - **Tên thương hiệu:** `BodyWise`. Viết hoa chữ `B` và `W`.
  - **Phụ đề chính thức:** `TRỢ LÝ THỂ TRẠNG & DINH DƯỠNG AI`.
  - **Slogan đồng hành:** `Hiểu cơ thể. Sống chủ động.`
  - **Font chữ đề xuất:** **Plus Jakarta Sans**, **Be Vietnam Pro** hoặc **Inter**.
  - **Độ dày nét chữ:** Chữ "Body" (Bold 800), chữ "Wise" (Bold 800 phối dải màu gradient Teal $\rightarrow$ Sky), Phụ đề (Semibold 600, dãn chữ `tracking-[0.15em]`).

  ---

  ## 📸 PHẦN 4: BRIEF THI CÔNG CHI TIẾT 8 TRANH 3D (3D PRODUCTION SHEETS)

  Dành riêng cho **3D Modeler, Lighting & Render Artist**. Tất cả tranh phải được render ở định dạng **PNG 24-bit nền trong suốt (Alpha Channel)** hoặc trên bục sứ men `#F8FAFC`, độ phân giải siêu nét (1254px – 1672px):

  ```text
  SETUP CAMERA & ÁNH SÁNG CHUẨN (GLOBAL MEDICAL-TECH 3D SETUP):
  - Camera: Focal Length 85mm (Trực giao nhẹ, không méo góc), góc nghiêng phối cảnh 25° – 30° từ trên nhìn xuống.
  - Key Light: Đèn studio y sinh góc 45° bên trái, ánh sáng trắng mềm 5400K, cường độ 1.15.
  - Fill Light: Đèn hắt dịu góc 45° bên phải, ánh xanh cyan nhạt 6200K, cường độ 0.45.
  - Rim/Accent Light: Đèn viền từ phía sau hắt lên, sắc xanh ngọc Vital Teal (#14B8A6), tạo viền sáng tách vật thể khỏi nền.
  - Shadow: Bóng mờ mềm tự nhiên (Soft contact shadows), opacity tối đa 16% (không dùng bóng đen sì).
  ```

  ---

  ### TRANH 01 (HERO BANNER): QUỸ ĐẠO ĐA TÁC TỬ SỨC KHỎE & VÒNG THỂ TRẠNG
  - **Tên tệp xuất bản:** `01_minh_hoa_hero_quy_dao_the_trang_da_tac_tu_3d.png`
  - **Kích thước render:** `1672 × 941 px`
  - **Bố cục:** Trung tâm lan tỏa quỹ đạo (Central Dynamic Orbit).
  - **Vật thể chính:**
    - Ở giữa: Biểu tượng BodyWise 3D lớn dạng sứ men trắng ngà kết hợp ngọc lục phát quang nhẹ.
    - Vành đai quỹ đạo: Hai vòng elip ngọc bích xoay nghiêng quanh tâm, trên đó có 4 hạt nhân tác tử đại diện cho:
      1. *Tác tử An toàn Y tế* (Khiên viền hồng ngọc bảo vệ).
      2. *Tác tử Phân tích InBody* (Thước đo chỉ số nhân trắc).
      3. *Tác tử Dinh dưỡng TDEE* (Đĩa dưỡng chất cân bằng).
      4. *Tác tử Lịch tập Kháng lực* (Tạ đòn công nghệ).
    - Chi tiết phụ: Các thẻ kính mờ trôi nổi hiển thị biểu đồ phổ điểm cơ thể, huy hiệu `WHO WPRO STANDARD` và các nốt sóng sinh học mờ ảo.

  ---

  ### TRANH 02: BÓC TÁCH PHIẾU ĐO INBODY BẰNG CẢM BIẾN AI OCR
  - **Tên tệp xuất bản:** `02_minh_hoa_boc_tach_phieu_inbody_ocr_3d.png`
  - **Kích thước render:** `1254 × 1254 px` (Tỷ lệ vuông 1:1)
  - **Bố cục:** Khung quét số hóa công nghệ cao (OCR Scanning Pod).
  - **Vật thể chính:**
    - Một tờ phiếu in kết quả đo InBody uốn lượn mềm mại bằng chất liệu giấy sợi cao cấp.
    - Một khung ngắm cảm biến laser 4 góc màu xanh ngọc bích (`#0D9488`) đang quét qua thân phiếu.
    - Các con số thể trạng quan trọng (`72.4 kg`, `19.5%`, `33.8 kg`) được trích xuất và bay bổng thành các khối số 3D phát sáng nhẹ, xếp ngay ngắn vào bảng đối chiếu.
    - Con tem niêm phong kỹ thuật số màu xanh ngọc xác nhận: **"OCR VERIFIED - ZERO PII LEAK"**.

  ---

  ### TRANH 03: THƯỚC ĐO PHÂN LOẠI THỂ TRẠNG 6 CHỈ SỐ WHO CHÂU Á
  - **Tên tệp xuất bản:** `03_minh_hoa_thuoc_do_the_trang_who_chau_a_3d.png`
  - **Kích thước render:** `1448 × 1086 px`
  - **Bố cục:** Bảng đồng hồ kiểm định nhân trắc học 3D (Biometric Gauge Array).
  - **Vật thể chính:**
    - Một đồng hồ bán nguyệt 3D chia 4 cung màu rõ ràng: Xanh lam (Thiếu cân), Xanh lá (Chuẩn 18.5 - 22.9), Vàng (Thừa cân 23 - 24.9), Cam đỏ (Béo phì $\ge 25$).
    - Kim chỉ thị bằng kim loại titan mảnh chỉ chuẩn xác vào mức `22.8` (Ngưỡng lý tưởng người Châu Á).
    - 5 cột trụ tinh thể nhỏ xung quanh đại diện cho PBF, SMM, BFM, VFL và Nước nội bào.
    - Nhãn khắc kim loại dập nổi: `WHO WPRO CLASSIFICATION`.

  ---

  ### TRANH 04: KHIÊN BẢO VỆ AN TOÀN Y TẾ & CHỐT CHẶN KHẨN CẤP 115
  - **Tên tệp xuất bản:** `04_minh_hoa_khien_an_toan_y_te_guardrail_3d.png`
  - **Kích thước render:** `1254 × 1254 px` (Tỷ lệ vuông 1:1)
  - **Bố cục:** Khiên áp lực bảo vệ y tế bất khả xâm phạm (Medical Guardrail Fortress).
  - **Vật thể chính:**
    - Một tấm khiên bảo vệ 3D lớn bằng đá khoáng và viền san hô Coral Rose (`#E11D48`).
    - Trên mặt khiên có biểu tượng đường sóng điện tim ECG ổn định kết hợp số điện thoại cấp cứu `115` phát sáng rõ ràng.
    - Một bức tường lưới phân tử trong suốt chặn đứng các câu hỏi nguy hiểm về chẩn đoán/kê đơn bừa bãi.
    - Đèn tín hiệu màu xanh bảo chứng cơ chế: `DETERMINISTIC LATENCY < 50ms (FAST-PATH)`.

  ---

  ### TRANH 05: ĐĨA CÂN BẰNG DINH DƯỠNG & TỶ LỆ ĐA LƯỢNG MACROS
  - **Tên tệp xuất bản:** `05_minh_hoa_dia_dinh_duong_can_bang_macros_3d.png`
  - **Kích thước render:** `1448 × 1086 px`
  - **Bố cục:** Đĩa phân bổ dinh dưỡng khoa học (Precision Nutritional Palette).
  - **Vật thể chính:**
    - Chiếc đĩa sứ tròn men trắng ngà chia 3 múi tỷ lệ hình học thanh lịch:
      1. *Khối Đạm Protein* (30% - màu ngọc bích tăng cơ).
      2. *Khối Tinh Bột Phức Hợp Carb* (45% - màu vàng ngô ấm năng lượng sạch).
      3. *Khối Chất Béo Tốt Fat* (25% - màu xanh bơ dịu).
    - Một chiếc cân tiểu ly kỹ thuật số nhỏ bên cạnh hiển thị chuẩn mục tiêu calo `2,150 kcal (TDEE Deficit)`.
    - Giọt nước tinh khiết đại diện cho khuyến nghị cấp nước 2.5 lít/ngày.

  ---

  ### TRANH 06: LỘ TRÌNH VẬN ĐỘNG KHÁNG LỰC & TÁI TẠO KHỐI CƠ SMM
  - **Tên tệp xuất bản:** `06_minh_hoa_lo_trinh_tap_luyen_tai_tao_co_bap_3d.png`
  - **Kích thước render:** `1448 × 1086 px`
  - **Bố cục:** Cầu thang tiến trình thể lực bậc thang (Progressive Overload Stairway).
  - **Vật thể chính:**
    - Dãy bậc thang đá khoáng tiến lên phía trước, mỗi bậc đại diện cho 1 tuần tập luyện thích nghi.
    - Trên các bậc thang là các quả tạ chuông (Kettlebell) và tạ đòn tinh xảo làm từ sứ gốm trắng viền kim loại đồng nhẹ.
    - Biểu đồ mũi tên năng lượng vút lên biểu thị khối lượng cơ bắp xương SMM tăng trưởng từ 32.0kg $\rightarrow$ 33.8kg.
    - Không có hình ảnh mệt mỏi, thể hiện năng lượng sống tích cực và an toàn cho cột sống.

  ---

  ### TRANH 07: TRỤC TRI THỨC Y KHOA RAG & MINH CHỨNG TRÍCH DẪN
  - **Tên tệp xuất bản:** `07_minh_hoa_truc_tri_thuc_y_khoa_rag_3d.png`
  - **Kích thước render:** `1448 × 1086 px`
  - **Bố cục:** Tòa tháp dữ liệu y học đối soát (Evidence-Based Knowledge Tower).
  - **Vật thể chính:**
    - Chồng tài liệu nghiên cứu y khoa, hướng dẫn dinh dưỡng lâm sàng và cẩm nang InBody số hóa dạng kính mờ.
    - Một chùm tia sáng quét màu xanh Cyan phân rã tài liệu thành các khối vector chunks đa chiều.
    - Thẻ trích dẫn nổi bật phía trước có dấu tích xanh: `CITATION MATCH: 96%` và tên nguồn tham chiếu `WHO_Guidelines_Asia_Pacific.pdf`.
    - Minh chứng cho nguyên tắc: Nói có sách, mách có chứng, không bịa đặt kiến thức y học.

  ---

  ### TRANH 08: BẢNG MINH BẠCH KÝ ỨC THỂ TRẠNG CÁ NHÂN HÓA
  - **Tên tệp xuất bản:** `08_minh_hoa_minh_bach_ky_uc_ca_nhan_hoa_3d.png`
  - **Kích thước render:** `1448 × 1086 px`
  - **Bố cục:** Bảng điều khiển ký ức AI minh bạch (Transparent Memory Console).
  - **Vật thể chính:**
    - Một khối chip xử lý sinh học bằng gốm sứ có các đường viền mạch dẫn màu ngọc bích.
    - Các thẻ ghi nhớ (Memory Fact Cards) lơ lửng xung quanh:
      - Thẻ 01: *"Dị ứng sữa bò (Lactose Intolerance)"* kèm nút công tắc [Xác nhận].
      - Thẻ 02: *"Tiền sử đau khớp gối trái"* kèm nút [Xóa bỏ an toàn].
    - Một chiếc ổ khóa số bằng kim loại sáng bóng tượng trưng cho quyền làm chủ dữ liệu cá nhân của người dùng.

  ---

  ## 📐 PHẦN 5: BẢNG ĐẶC TẢ THIẾT KẾ BỘ ICON (2D SVG & 3D MINI)

  ### 5.1. Quy Chuẩn Lưới Thiết Kế Icon 2D SVG
  - **Khung lưới cơ sở (Grid):** Chuẩn `24 × 24 px` (hành động nhỏ) và `32 × 32 px` (icon điều hướng Sidebar).
  - **Độ dày nét vẽ (Stroke weight):** Cố định `2.0 px`. Bo tròn đầu nét (`stroke-linecap="round"`, `stroke-linejoin="round"`).
  - **Màu sắc:** Sử dụng `currentColor` để thích ứng linh hoạt với cả Light mode và Dark mode.

  ```text
  DANH SÁCH 12 ICON VECTOR NGHIỆP VỤ CỐT LÕI (2D SVG):
  1.  bmi.svg             : Đồng hồ đo áp suất thể trạng với kim chỉ thị trung tâm.
  2.  pbf.svg             : Giọt lipid hình học kèm thước đo vi lượng tỷ lệ mỡ.
  3.  smm.svg             : Cặp tạ chuông vươn chéo tượng trưng cho sức mạnh cơ bắp.
  4.  vfl.svg             : Khiên an toàn bao quanh vùng lõi nội tạng.
  5.  bfm.svg             : Vòng tròn khối mỡ toàn phần với các điểm lipid phân bố.
  6.  nutrition.svg       : Đĩa ăn khoa học chia 3 ngăn tỷ lệ cân bằng đa lượng.
  7.  workout.svg         : Tạ đòn phối hợp vận động kháng lực tiến bộ.
  8.  ocr-scan.svg        : Khung ngắm 4 góc cảm biến bóc tách phiếu đo InBody.
  9.  safety-shield.svg   : Khiên an toàn có dấu tích bảo vệ y tế khẩn cấp 115.
  10. memory-facts.svg    : Não bộ tế bào AI ghi nhớ thông tin thể trạng cá nhân.
  11. evidence-doc.svg    : Quyển cẩm nang y khoa có đoạn trích dẫn minh bạch.
  12. heart-pulse-safe.svg: Nhịp tim sinh học ổn định trong ngưỡng an toàn.
  ```

  ### 5.2. Bộ 8 Icon 3D Mini Cho Thẻ Dashboard (`assets/icon/3d-features/`)
  - **Kích thước xuất bản:** `256 × 256 px` PNG trong suốt (Alpha channel).
  - **Đặc điểm:** Là phiên bản thu nhỏ tinh xảo của 8 tranh 3D ở Phần 4, góc phối cảnh isometric 30°, dùng để gắn vào góc trên bên phải của các thẻ KPI và nhóm tính năng trên Web Dashboard.

  ---

  ## 🏁 PHẦN 6: DANH MỤC XUẤT TỆP & TÊN TỆP CHUẨN (EXPORT CHECKLIST)

  Khi thiết kế hoàn tất, Designer bàn giao đầy đủ toàn bộ tệp theo **đúng định dạng, kích thước và tên tệp chuẩn tiếng Việt bên dưới**:

  ### 📁 Thư mục `assets/brand/`:
  - `bang_tong_quan_nhan_dien_thuong_hieu.png` (1448 × 1086 px)
  - `poster_cam_nang_thuong_hieu_mini.png` (1448 × 1086 px)
  - `bang_quy_chuan_kich_thuoc_favicon.png` (1448 × 1086 px)
  - `he_thong_hoa_van_nen_thuong_hieu.png` (1448 × 1086 px)
  - `huong_dan_chuyen_dong_motion.png` (1672 × 941 px)
  - `bieu_tuong_ung_dung_squircle_3d.png` (1254 × 1254 px)
  - `bieu_tuong_logo_vitality_spark_3d.png` (1254 × 1254 px)
  - `logo_ngang_thuong_hieu_3d.png` (1448 × 1086 px)
  - `logo_ngang_slogan_nen_toi_3d.png` (1448 × 1086 px)
  - `logo_ngang_slogan_nen_sang_3d.png` (1448 × 1086 px)
  - `logo_ngang_nen_sang.png` (1406 × 451 px, PNG-24 transparent)
  - `logo_ngang_kem_slogan_nen_sang.png` (1448 × 481 px, PNG-24 transparent)
  - `logo_ngang_kem_slogan_nen_toi.png` (1442 × 469 px, PNG-24 transparent)
  - `bieu_tuong_logo_vitality_spark.png` (1024 × 1024 px, PNG-24 transparent)
  - `bieu_tuong_goc_master.png` (2048 × 2048 px)
  - `bieu_tuong_ung_dung_pwa.png` (1024 × 1024 px)
  - `anh_chia_se_mang_xa_hoi_og.png` (1200 × 630 px)
  - `apple-touch-icon.png` (180 × 180 px)
  - `favicon.ico` (Multi-size 16, 32, 48)
  - `favicon-16.png`, `favicon-32.png`, `favicon-48.png`, `favicon-192.png`, `favicon-512.png`

  ### 📁 Thư mục `assets/3d-illustrations/`:
  - `01_minh_hoa_hero_quy_dao_the_trang_da_tac_tu_3d.png` (1672 × 941 px)
  - `02_minh_hoa_boc_tach_phieu_inbody_ocr_3d.png` (1254 × 1254 px)
  - `03_minh_hoa_thuoc_do_the_trang_who_chau_a_3d.png` (1448 × 1086 px)
  - `04_minh_hoa_khien_an_toan_y_te_guardrail_3d.png` (1254 × 1254 px)
  - `05_minh_hoa_dia_dinh_duong_can_bang_macros_3d.png` (1448 × 1086 px)
  - `06_minh_hoa_lo_trinh_tap_luyen_tai_tao_co_bap_3d.png` (1448 × 1086 px)
  - `07_minh_hoa_truc_tri_thuc_y_khoa_rag_3d.png` (1448 × 1086 px)
  - `08_minh_hoa_minh_bach_ky_uc_ca_nhan_hoa_3d.png` (1448 × 1086 px)

  ### 📁 Thư mục `assets/icon/`:
  - `3d-features/`: 8 tệp PNG trong suốt 256 × 256 px.
  - `2d-entities/`: 12 tệp SVG vector chuẩn mã sạch (minified).
  - `assets.json`: Tệp từ điển định nghĩa metadata icon.

  ---
  *Tài liệu này là cẩm nang chính thức của BodyWise Platform. Mọi thắc mắc về vật liệu PBR, thông số camera hoặc ánh sáng vui lòng đối chiếu trực tiếp với bộ tokens tại [`BRAND_GUIDELINES.md`](BRAND_GUIDELINES.md).*

