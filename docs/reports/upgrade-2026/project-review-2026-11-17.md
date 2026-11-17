# Rà soát dự án ngày 2026-11-17

## Phạm vi và kết luận

- Revision kiểm tra: `a024500` (backend gộp, WP-05 ba specialist đã commit). Không còn thư mục core-api/agent-service ở root.
- Chỉ rà soát; không sửa source, nâng dependency, deploy, restart, migrate, commit hoặc push.
- Đã đọc luồng frontend adapter → FastAPI → auth → memory.chat → context → graph → capability/composer; cấu hình retrieval, database và Docker.
- Code hiện có ba specialist: InBodyAgent, LifestyleAgent, KnowledgeAgent. Các capability cũ được nhóm trong ba graph node; không phải ba LLM chạy song song. Router, safety và composer vẫn là workflow chung.
- Backend test đạt nhưng còn lỗi hành vi tái hiện được. Chưa đủ bằng chứng nghiệm thu hệ thống đang chạy hoặc production.

## Kết quả đã chạy

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Backend unit | 158 passed, 2 cảnh báo FastAPI on_event deprecated; Python host 3.13, SQLite, LLM_PROVIDER=none, embedding tắt |
| API integration fast paths | 3 passed; TestClient trong process, không phải HTTP runtime/PostgreSQL |
| Frontend ESLint | exit 0, không có lỗi/cảnh báo |
| Frontend production build | Compile, TypeScript, prerender 4/4 đạt; command cuối cùng exit 1 bởi SecurityFatalError yêu cầu nâng Next.js |
| npm audit | 8 dependency entries mức moderate, không high/critical; gồm Next.js và chuỗi minimatch/typescript-eslint; không đồng nghĩa 8 lỗi độc lập có thể khai thác |
| Compose | infra, backend, embedding serving, frontend: cả bốn config --quiet exit 0; không chứng minh runtime kết nối được |
| Syntax | graph.py đạt; lệnh trong AGENTS còn trỏ brain.py và app.py đã không tồn tại ở backend/src |
| Docker/listener | Docker Engine không truy cập được, pipe docker_engine không tồn tại; không có listener trên 8000/8001/3000/5432/6333/6379 |

## Phát hiện cần xử lý

### F1 — P1: Chat biến cân nặng âm thành số dương

- Nguồn: `backend/src/agents/parsing.py:34–40`; regex bắt dãy số không giữ dấu và không chặn số đứng sau dấu âm.
- Tái hiện bằng TestClient, development identity tổng hợp, SQLite in-memory: POST `/agent/answer` với `{"question":"Tính BMI giúp tôi: -72kg, 170cm"}`.
- Thực tế: HTTP 200, fast_path=inbody_tools, tool_result.weight_kg=72.0, BMI=24.91.
- `/tools/bmi` có validation số âm và test đạt; gate đó chưa bảo vệ đường nhập ngôn ngữ tự nhiên.
- Cần: giữ/nhận biết dấu, từ chối giá trị sai và hỏi lại; không sửa ý nghĩa dữ liệu để tạo kết quả hợp lệ. Test cả kg/cm/PBF và giá trị ngoài phạm vi.

### F2 — P1: Lời chào lấn át yêu cầu chính, kể cả medical_caution

- Nguồn: `backend/src/agents/fast_paths.py:65–105`; match substring lời chào rồi trả ngay; graph gọi bước này trước InBody/router.
- `Xin chào, tính BMI giúp tôi: 72 kg, 170 cm` → HTTP 200, fast_path=general_chat, tool_results=[]; không tính BMI.
- `Xin chào, tôi bị tiểu đường và muốn hỏi về liều thuốc` → graph nhận medical_caution nhưng trả lời chào; trace ghi sai `Safety risk level: low.`
- `Tôi bị huyết áp, cao 170cm nặng 72kg, tính BMI` cũng có safety_result=medical_caution nhưng trace fast path ghi low.
- Urgent hiện vẫn đi trước lời chào và test bypass đạt. Phát hiện này không chứng minh urgent bị bypass hay hệ thống đã kê đơn.
- Cần: chỉ dùng greeting fast path cho lời chào thuần; giữ cảnh báo/thực tế risk trong mọi fast path, thêm test câu hỗn hợp.

### F3 — P1: Frontend Compose không cấu hình API URL đúng giai đoạn

- `frontend/docker-compose.yml:15` đặt NEXT_PUBLIC_API_URL=http://chatbot-api:8000 trong runtime environment.
- `frontend/Dockerfile:11–17` build không nhận build ARG/ENV cho URL này; client `frontend/src/lib/api.ts` mặc định localhost:8000.
- Bundle build local đã chứa localhost:8000. Điều này xác nhận giá trị local; chưa build image Docker do daemon offline.
- NEXT_PUBLIC_* bị inline lúc next build; thay runtime env không đổi bundle. Tên chatbot-api thuộc Docker DNS, trình duyệt người dùng thông thường không phân giải được.
- Cần: build-time public URL truy cập được từ browser, hoặc proxy cùng origin/runtime config có chủ đích. Nghiệm thu từ browser trên máy khác host.
- Nguồn chính thức: https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser

### F4 — P1 khi chạy cấu hình mẫu: Production CORS chặn đăng nhập từ UI

- `backend/.env.example` chọn AUTH_MODE=production, CORS_ALLOWED_ORIGINS trống. `backend/src/api/app.py:80–86` chỉ thêm localhost mặc định cho development.
- Tái hiện process production với allowlist trống: OPTIONS `/auth/login`, Origin=http://localhost:3000 → HTTP 400, `Disallowed CORS origin`, không có Access-Control-Allow-Origin.
- Đây là cấu hình fail closed đúng về bảo mật; điểm thiếu là hướng dẫn SETUP không chỉ cách cấu hình CORS/JWT để chạy UI production mẫu thành công. Chưa khẳng định .env riêng của người dùng có cùng lỗi.
- Cần: hướng dẫn origin frontend thực tế, issuer/audience/signing key và kiểm thử preflight + login trên cấu hình triển khai đã chọn.

### F5 — P2: Dependency Next.js thuộc dải advisory và build đang bị chặn

- `frontend/package.json:14` pin Next.js 16.4.3; npm audit xác nhận GHSA-mfr8-8qww-v76h (moderate), dải 16.3.0–16.4.4; bản vá từ 16.4.5. Audit đề xuất 16.4.6.
- Build command exit 1 vì SecurityFatalError dù compile/TypeScript/prerender đã đạt. Không ghi kết quả này là build pass.
- Advisory yêu cầu cách dùng kết hợp use cache/unstable_cache và root params. Tìm trong frontend/src chưa thấy các lời gọi đó; chưa chứng minh ứng dụng có đường khai thác này.
- Cần nâng Next.js và eslint-config-next đồng bộ lên phiên bản đã vá tương thích, cập nhật lockfile, kiểm tra lại build/audit. Không tự động chạy npm audit fix trong đợt rà soát.
- Nguồn nhà cung cấp: https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h

### F6 — P2: Cấu hình infra mở cổng dữ liệu ra mọi interface

- `infra/docker-compose.infra.yml` publish Postgres 5432, Qdrant 6333/6334, Valkey 6379 bằng host-port không giới hạn 127.0.0.1.
- Qdrant production.yaml chỉ đặt log_level; Valkey command không cấu hình auth. Mật khẩu Postgres có fallback cố định trong Compose.
- Source chứng minh mặc định publish rộng; chưa kiểm chứng khả năng truy cập từ LAN/Internet do daemon offline và chưa đánh giá firewall.
- Cần xác định môi trường: local bind localhost hoặc bỏ publish cho dịch vụ chỉ dùng nội bộ; triển khai chia sẻ cần credentials và network policy phù hợp.

## Khoảng trống bằng chứng

- Chưa chạy HTTP runtime sau WP-05; chưa kiểm PostgreSQL/Qdrant/Redis/OCR/provider thật trên revision hiện tại.
- Chưa browser E2E đăng nhập → consent → số đo → chat → trích dẫn; chưa kiểm responsive/accessibility trực quan trong đợt này.
- Chưa benchmark corpus thật Recall@5/Safety Hit@5/citation precision, HTTP P50/P95 hoặc soak. Unit test đạt không thay cho các gate đó.
- Chưa audit sâu pipeline import, OCR worker, backup/restore và toàn bộ route family; đây không phải kiểm toán bảo mật đầy đủ.
- Trong lúc kiểm tra, README.md xuất hiện thay đổi 41 dòng xóa từ bên ngoài tác vụ; giữ nguyên. git diff --check báo dòng trắng cuối README. Không quy thay đổi này cho đợt rà soát.

## Thứ tự đề nghị

1. Sửa F1/F2 bằng regression tests cho đầu vào tự nhiên và câu hỗn hợp.
2. Sửa cấu hình browser/API/CORS ở F3/F4, nâng dependency ở F5.
3. Giới hạn exposure infra theo F6, bật Docker và kiểm tra import/Qdrant trước mọi restart.
4. Nghiệm thu HTTP + browser trên cùng revision/config, sau đó mới chạy eval RAG và latency.
