# FIX-04 — Cấu hình browser/API, auth/CORS và cổng hạ tầng local

Ngày: 2026-11-17. Base revision: `1cc6b3a` + patch working tree.

**SOURCE_READY, VERIFIED_TEST; HTTP host biệt lập đạt. Chưa deploy/restart container sản phẩm.**

## Nguyên nhân và thay đổi

- Frontend Compose trước sửa đặt NEXT_PUBLIC_API_URL=http://chatbot-api:8000 ở runtime. Next đóng public env vào browser bundle lúc build, và browser thường không resolve service DNS Docker. Dockerfile/Compose nay truyền API URL, AUTH_MODE và DEV_USER_ID bằng ARG → ENV trước npm run build; mặc định localhost:8000 và production. Không còn public URL đặt ở runtime Compose như thể đổi được bundle.
- Thêm frontend/.dockerignore loại node_modules/.next/.git, env riêng tư, log, key và credentials; chỉ giữ template .env.example. Không đưa backend secret vào build args. Không sửa API client hoặc component.
- backend/.env.example giữ AUTH_MODE=production, cung cấp issuer/audience first-party và allowlist CORS local rõ ràng. Signing key, POSTGRES_PASSWORD và DATABASE_URL để trống bắt buộc người vận hành cấu hình; template không còn mật khẩu DB mẫu dùng chung. Embedding URL mẫu dùng DNS internal-network để khớp stack chính.
- SETUP.md có lệnh tạo secret mới không in/log, từ chối ghi đè file tồn tại; phân biệt cài mới với credential trong volume cũ. Cùng backend/.env cấp nội suy Compose cho infra/backend; frontend/.env cấp build args. Không chỉnh file .env riêng tư hoặc đổi role password.
- Cổng Postgres 5432, Qdrant 6333/6334, Valkey 6379, embedding 5001 trong main infra và standalone embedding bind 127.0.0.1. Service DNS/network/volume names giữ nguyên. GPU override kế thừa loopback binding.
- Backend Compose chỉ bổ sung chú thích về --env-file; test xác nhận AUTH_MODE/LLM_PROVIDER/DATABASE_URL/JWT/CORS từ file tổng hợp đi đến API/worker/scheduler đúng giá trị. Không cần nới auth hoặc sửa middleware CORS vốn đã fail closed.
- Cập nhật SETUP, backend/frontend/infra README và AGENTS.md: ba specialist/workflow stages hiện hành, syntax paths thật, --env-file/config --quiet, auth/CORS, public build env, liveness/readiness và cổng local. Root README.md sửa sẵn không bị chỉnh.

## Regression và toàn bộ tests

RED trước sửa: test_deployment_config.py ban đầu **7 failed, 2 passed**: thiếu build args, publish data/embedding không loopback, thiếu password vẫn được chấp nhận, template credential/CORS thiếu và preflight production từ origin local bị từ chối.

Sau sửa, test_deployment_config.py có 11 ca: render 4 Compose base + GPU override bằng CLI thật với env tổng hợp, xác nhận password bắt buộc, env precedence, CORS production và auth boundary trong process riêng, chạy chính đoạn Python tạo env trong SETUP và xác nhận không output/không ghi đè. File Compose được copy sang fixture để không đọc env riêng tư của deployment. Không cần daemon cho config rendering; CLI thiếu thì các ca Compose được skip, nhưng trong lượt này CLI có sẵn và **không ca nào bị skip**.

Thêm 3 ca vào test_auth_context.py: thiếu từng JWT_SIGNING_KEY/JWT_ISSUER/JWT_AUDIENCE đều từ chối token và không fallback sang dev header. Các test auth/owner có sẵn tiếp tục đạt trên SQLite/fixture, không suy ra cross-user gate production đã nghiệm thu.

```powershell
$env:PYTHONPATH=(Resolve-Path backend/src).Path
$env:DATABASE_URL='sqlite://'
$env:LLM_PROVIDER='none'
$env:CUSTOM_EMBEDDING_ENABLED='false'
python -B -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider --basetemp=backend/artifacts/fix04-pytest
```

Kết quả cuối: **264 unit + 3 integration = 267 passed**, 14 ca mới; 2 cảnh báo FastAPI on_event deprecated có sẵn, 30.57s. Python host 3.13; AST feature_version 3.10 của 4 entrypoint + 2 test file đạt, chưa thay cho image Python 3.10. Diff check đạt. Fixture cuối nằm trong backend/artifacts/fix04-pytest (Git ignore); automatic approval review chặn cleanup với lý do "blocked by policy", kể cả phương án xóa riêng file đã kiểm kê và thư mục rỗng. Vì vậy fixture chưa dọn; không chứa credential deployment thật và không được đưa vào Git.

## Hai build cấu hình frontend

Node 22.23.2, npm 10.9.8, Next 16.4.6; Docker Engine không hoạt động nên đây là **host builds**, không phải docker build.

| Build | Public API URL | Auth mode | Kết quả |
|---|---|---|---|
| A | https://api.fix04-a.invalid | development | npm run build exit 0; client JS chứa URL A và synthetic-build-a, không URL B |
| B | https://api.fix04-b.invalid | production | Exit 0; client JS chứa URL B, không URL A/identity A |
| Khôi phục local | http://localhost:8000 | production mặc định | Exit 0; không còn URL tổng hợp A/B trong client chunks |

`npm run lint` và `npx --no-install tsc --noEmit` đều exit 0. Package manifest/lockfile không đổi sau FIX-03. Không tạo network request tới các domain .invalid; chúng chỉ là sentinel để kiểm bundle.

## HTTP thật biệt lập — 8/8 đạt

Uvicorn production + Next production server trên hai cổng động 127.0.0.1, dữ liệu/identity tổng hợp. Signing key ngẫu nhiên chỉ trong process, không log/lưu vào report; SQLite memory, LLM none, BM25 autoload/embedding/Zep/observability tắt.

1. OPTIONS /auth/login từ frontend origin đã cấu hình → 200, đúng allow-origin.
2. Origin lạ → 400, không allow-origin.
3. Dev header trong production → 401.
4. JWT giả chữ ký → 401.
5. JWT hết hạn → 401.
6. JWT ký hợp lệ + greeting/urgent/số đo sai → 200 urgent_safety trước DB/queue/provider.
7. Next start với runtime AUTH_MODE=development vẫn trả HTML màn hình đăng nhập từ build production.
8. JS chunk được Next phục vụ vẫn chứa URL B dù start với runtime URL khác; không URL A hoặc runtime override.

Cả hai server đã terminate + wait. JWT trong smoke được test harness ký để kiểm verifier, **không phải** bằng chứng đăng ký/đăng nhập qua account database và Valkey thật. Không có browser JavaScript/hydration hoặc luồng người dùng trên máy khác trong đợt này.

## Giới hạn, bước kế tiếp và rollback

- Docker version kiểm lại trả Internal Server Error tại docker_engine /v1.24/version. Docker build/image, bind thực, SELECT 1, Valkey ping, Qdrant health/count và API/worker network connection thật: **NOT_RUN**. Không dùng Compose config để thay bằng chứng này. Chưa kiểm preflight import/alias/manifest vì chưa deploy.
- Không đổi password/volume, không migrate/seed, restart, đổi Qdrant alias/collection hoặc bật auth Qdrant/Valkey trên deployment hiện hữu. Các env local và template infra legacy đang bị ignore không bị ghi đè; runbook mới dùng backend/.env làm nguồn chung.
- Loopback là cấu hình local, không phải shared-production security gate. Engine cũ có ngoại lệ truy cập cùng L2 được Docker ghi rõ; cần kiểm Engine/firewall thật. Monitoring/Ollama tùy chọn nằm ngoài thay đổi bind của stack chính.
- Chưa đóng FIX-05: còn image/runtime/browser, login với PostgreSQL/Valkey, ownership thật, P95/soak và corpus/provider gates. Không commit/push trong lượt FIX-04.
- Rollback source bằng patch các file FIX-04, giữ nguyên README và credential hiện hữu. Không có schema/data migration; rollback compose sau khi đã deploy vẫn cần import/runtime preflight, không reset volume để quay về password cũ.

Nguồn cơ chế: [Next public env](https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser), [Compose env precedence](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/), [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/). Các nguồn giải thích cấu hình; bằng chứng thực thi của dự án là các kiểm tra được phân cấp ở trên.
