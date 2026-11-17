# FIX-02 — Lời chào không che yêu cầu và không hạ mức safety

Ngày: 2026-11-17. Base revision: `221b649` + patch working tree.

**SOURCE_READY, VERIFIED_TEST; HTTP biệt lập đã kiểm fast-path, chưa deploy container sản phẩm.**

## Lỗi và bản sửa

- RED tái hiện: `Xin chào, tính BMI 72kg 170cm` trả `general_chat` thay vì BMI; cảm ơn kèm yêu cầu dinh dưỡng bị nuốt; bệnh nền/thuốc có thể đi qua greeting/InBody template; thiếu evidence mất `recommended_action`; graph lỗi kiểm lại riêng text làm mất caution từ hồ sơ.
- `backend/src/agents/fast_paths.py`: thay tìm chuỗi con bằng matcher toàn câu cho lời chào/cảm ơn/hỏi khả năng thuần. Phần không khớp đi vào routing hiện có; không xóa tiền tố hay viết lại câu hỏi gốc. Hai fast-path chỉ nhận `safety_result.risk_level=low`; thiếu kết quả precheck cũng không được đi tắt.
- `backend/src/agents/graph.py`: ghi trace precheck từ risk thực cho mọi nhánh; bỏ trace ghi cứng low trong fast-path. Fallback khi graph lỗi giữ kết quả precheck gồm bệnh nền đã xác nhận.
- `backend/src/agents/nodes/supervisor.py`: medical caution chọn duy nhất RAG trước fallback route classifier, không gọi classifier để rồi bỏ kết quả. Giữ công khai KnowledgeAgent và capability truy xuất an toàn; không chạy kế hoạch dinh dưỡng/tập luyện hoặc web.
- `backend/src/agents/composer.py`: nhánh thiếu bằng chứng giữ disclaimer và recommended_action. Nhánh deadline/provider lỗi vẫn dùng fallback có cảnh báo; output guard hiện có tiếp tục chặn câu trả lời thiếu hành động thận trọng hoặc khuyên đổi thuốc.
- Giữ nguyên ba specialist, validation FIX-01, auth, DB schema, provider config, corpus và citation/cache contract.

## Kiểm thử

`backend/tests/unit/test_greeting_safety_regression.py`: **33 ca mới**, gồm lời chào thuần; lời chào + BMI/dinh dưỡng/tập luyện; thuốc/bệnh nền từ text hoặc hồ sơ; trace đúng risk; truy xuất lọc medical_safety; lỗi retrieval/provider/graph; evidence rỗng/deadline/output không an toàn; contract hai API; urgent kèm lời chào và số đo sai trước DB/queue/provider/normalizer.

Test dùng input tổng hợp, fixture retrieval/provider trong process và hàm gây lỗi khi có lời gọi bị cấm. Provider failure có xác nhận stub thực sự được gọi. Đây không phải bằng chứng chất lượng LLM hay corpus thật.

```powershell
$env:PYTHONPATH=(Resolve-Path backend/src).Path
$env:DATABASE_URL='sqlite://'
$env:LLM_PROVIDER='none'
$env:CUSTOM_EMBEDDING_ENABLED='false'
python -B -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider
```

Kết quả: **250 unit + 3 integration = 253 passed**, 2 cảnh báo FastAPI `on_event` deprecated có sẵn. Host Python 3.13, SQLite/in-process; chưa chạy interpreter/image Python 3.10. AST với feature_version 3.10 của 5 file Python thay đổi/thêm và diff whitespace đạt.

## HTTP thật biệt lập

Uvicorn process mới trên 127.0.0.1/cổng động, SQLite in-memory, identity development tổng hợp, LLM none; BM25 autoload/embedding/Zep/observability tắt. Không stub provider/retrieval trong process HTTP. `GET /` xác nhận server sẵn sàng. Process đã terminate + wait sau kiểm tra; không sửa container/volume/collection.

| Yêu cầu | /agent/answer | /chat/complete |
|---|---|---|
| Lời chào thuần | 200 general_chat | 200 general_chat |
| Lời chào + BMI 72kg/170cm | 200 inbody_tools, BMI 24.91 | 200 inbody_tools, BMI 24.91 |
| Lời chào + đau ngực/khó thở + số âm | 200 urgent_safety | 200 urgent_safety dù sync_request=false |
| Lời chào + BMI số âm | 422 invalid_health_input | 422 invalid_health_input |

Thêm `/agent/answer` không auth → 401: **9/9 HTTP checks đạt**. Medical-caution retrieval/provider mới kiểm bằng fixture trong process, chưa nghiệm thu qua HTTP với Qdrant/provider thật.

Probe `/health` trong harness ban đầu timeout sau 8 giây; thử cấu hình cache localhost cũng timeout sau 6 giây. Không tính hai probe này là pass và không thay đổi endpoint/cache trong FIX-02. Bộ kiểm tra sau dùng `GET /` để tách readiness của server biệt lập khỏi dependency health. Cần kiểm lại `/health` và dependency trong FIX-05.

## Giới hạn và bàn giao

- Docker Engine kiểm lại trả Internal Server Error tại `/v1.24/version`. Container/PostgreSQL/Qdrant/broker/provider thật: **NOT_RUN**; chưa restart/deploy sản phẩm.
- Matcher lời chào dùng tập mẫu xác định; lời chào lạ sẽ đi routing bình thường, không cam kết hiểu mọi cách diễn đạt tiếng Việt. Không thay đổi taxonomy/keyword detector y tế trong đợt này.
- Chưa đo P95/soak/router accuracy; số test và HTTP smoke không chứng minh các quality gate đó.
- README.md sửa sẵn được giữ nguyên. Không stage/commit/push/migrate trong đợt FIX-02.
- Rollback chỉ patch bốn source file, file regression mới và dòng tiến độ của FIX-02; không reset working tree. Không có migration dữ liệu. Đợt tiếp theo: FIX-03 dependency frontend khi được giao.
