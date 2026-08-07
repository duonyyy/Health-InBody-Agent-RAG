# Báo cáo kiểm thử hệ thống Health/InBody Agent RAG

**Thời gian kiểm thử:** 30/07/2026, khoảng 16:15–16:31 (UTC+7)  
**Môi trường:** hệ thống đang chạy thật trên máy phát triển, đồng thời đang import dữ liệu  
**Phạm vi:** Agent, routing, health tools, RAG/Qdrant, LLM, tốc độ, UI Streamlit và một số kiểm tra vận hành/an toàn  
**Kết luận ngắn:** **chưa đạt để dùng production; phù hợp mức MVP/dev demo sau khi sửa lỗi timeout.**

> **Cập nhật lúc 17:34:** Đã retest sau khi nạp mã Đợt 1. Safety/BMI fast path đã giảm từ 100–120 giây xuống khoảng 10–11 ms. Tuy nhiên import đã dừng ở 13.379/23.608 point, Ollama vẫn timeout với `OLLAMA_THINK=auto`, metadata Qdrant bị ghi đè sai và embedding vẫn chạy CPU. Xem mục 11.

---

## 1. Tóm tắt điều hành

| Hạng mục | Kết quả | Đánh giá |
|---|---:|---|
| Backend, frontend, Qdrant, Ollama | Đều phản hồi | Đạt về khả dụng cơ bản |
| Health tools độc lập | 7/7 ca smoke test cho kết quả mong đợi | Tốt trong phạm vi hẹp |
| Router theo ý định chính | 4/5 ca | Trung bình; nhạy với dấu/cách diễn đạt |
| Router khớp đầy đủ tập Agent kỳ vọng | 3/5 ca | Chưa ổn định |
| Retrieval đúng `content_type` ở top 1 | 4/5 truy vấn | 80%, nhưng chưa phản ánh đúng ngữ nghĩa |
| Retrieval top 1 trả lời trực tiếp câu hỏi | 2/5 truy vấn | 40%, chưa đạt |
| Truy vấn cấp cứu tìm được tài liệu safety trong top 5 | 0/1 | Không đạt, rủi ro cao |
| Agent lời chào toàn tuyến | 65,15 giây, trả fallback chung chung | Không đạt |
| Agent BMI toàn tuyến | Client timeout sau 120,11 giây | Không đạt |
| Agent cấp cứu toàn tuyến | Client timeout sau 100,08 giây; server xong khoảng 121 giây | Không đạt |
| UI headless | Render và các form chính hoạt động | Đạt một phần |
| UI trực quan trên trình duyệt | Chưa xác minh được | Không đủ bằng chứng để kết luận |

### Điểm đánh giá tham khảo

| Năng lực | Điểm / 10 | Lý do chính |
|---|---:|---|
| Khả dụng dịch vụ | 7 | Các service sống, nhưng luồng Agent không đáp ứng trong thời gian sử dụng được |
| Agent/orchestration | 4 | Có LangGraph và tool routing, nhưng gọi LLM thừa, timeout và fallback nghèo thông tin |
| Tool tính toán | 8 | Nhanh, kết quả smoke test đúng; còn lỗi status code và chuỗi tiếng Việt không dấu |
| RAG/retrieval | 4 | Qdrant chạy, nhưng corpus dở dang, BM25 không hoạt động và precision ngữ nghĩa thấp |
| Safety | 4 | Tool bắt được “đau ngực + khó thở”, nhưng toàn tuyến trả quá muộn và retrieval safety sai |
| Tốc độ | 3 | Tool/search chấp nhận được; Agent mất 65–121 giây |
| Giao diện | 6 | Có đủ luồng dev/demo, form rõ ràng; chat chịu lỗi timeout, chưa kiểm thử trực quan/accessibility |
| Sẵn sàng production | 3 | Thiếu auth, benchmark, kiểm thử tự động và guardrail đầu ra; dữ liệu chưa hoàn tất |

Không nên tính trung bình các điểm trên thành một “độ chính xác tổng”. Các hạng mục có trọng số rủi ro khác nhau; riêng lỗi safety và timeout đủ để chặn production.

---

## 2. Điều kiện và giới hạn phép đo

### 2.1 Dữ liệu đang được import trong lúc test

Kết quả dry-run trước đó:

- 5.345 document nguồn;
- 23.608 chunk dự kiến;
- 0 lỗi validation;
- phân bố document nguồn: 4.918 nutrition, 407 exercise, 15 inbody, 4 medical safety, 1 general health.

Trong phiên test:

- đầu phiên: 4.369 point, tương đương khoảng 18,51% số chunk dự kiến;
- snapshot cuối dùng để phân tích metadata: 6.830 point, khoảng 28,93%;
- Qdrant báo `green`;
- `indexed_vectors_count = 0`;
- backend báo BM25 `initialized=false`, `documents_count=0`, `has_bm25=false`.

Do đó, kết quả retrieval trong báo cáo là **provisional**. Nó phản ánh đúng trạng thái hệ thống hiện tại, nhưng không đại diện cho corpus sau khi import hoàn tất.

### 2.2 Phân bố point đã có tại snapshot 6.830

| `content_type` | Số point |
|---|---:|
| `general` | 4.841 |
| `nutrition` | 1.936 |
| `medical_safety` | 36 |
| `inbody_metric` | 14 |
| `exercise` | 3 |
| `general_health` | 0 |

Có hai vấn đề cần chú ý:

1. Nhãn runtime có `general`, trong khi dry-run báo `general_health`; schema metadata chưa nhất quán.
2. Chỉ có 3 point exercise tại thời điểm test, nên đánh giá exercise chưa có đủ độ bao phủ.

`indexed_vectors_count = 0` không tự động có nghĩa Qdrant hỏng; với collection nhỏ/đang ghi, optimizer có thể chưa xây HNSW. Tuy nhiên, hiện tại truy vấn có khả năng còn dùng exact scan và số liệu hiệu năng sẽ thay đổi sau tối ưu.

### 2.3 Tải nền

- Embedding BGE-M3 runtime đang chạy CPU, vector 1.024 chiều.
- Ollama chạy `qwen3:8b`, quantization `Q4_K_M`.
- Ollama dùng khoảng 2,31 GB VRAM; toàn GPU dùng khoảng 2,94/4 GB tại snapshot.
- GPU là NVIDIA GeForce RTX 3050 Laptop 4 GB.
- Import dữ liệu và các bài test dùng chung CPU/GPU/ổ đĩa.

Vì vậy, latency ở đây là latency “khi hệ thống đang bận”, hữu ích cho kiểm thử thực tế nhưng không phải benchmark cô lập.

---

## 3. Kiểm thử Health tools

### 3.1 Ma trận kết quả

| Ca | Đầu vào | Kết quả chính | Latency |
|---|---|---|---:|
| BMI | 72 kg, 170 cm | BMI 24,91; `overweight_risk` | 213 ms ở lần đầu |
| PBF | Nam, 28% | `very_high` | 233 ms ở lần đầu |
| Mỡ nội tạng | Level 12 | `elevated` | 19 ms |
| Dinh dưỡng | Giảm mỡ, 70 kg | Protein 112–154 g/ngày | 21 ms |
| Tập luyện | Giảm mỡ, beginner, 3 ngày | 3 session/tuần | 15 ms |
| Safety | Đau ngực + khó thở | `urgent` | 15 ms |
| BMI không hợp lệ | Cân nặng âm | JSON chứa `error` | 10 ms |

**Kết quả logic smoke test:** 7/7 ca cho hành vi đã định nghĩa.

### 3.2 Vấn đề phát hiện

- Giá trị đầu vào sai trả HTTP 200 kèm trường `error`, thay vì HTTP 4xx. Client khó phân biệt thành công/thất bại bằng status code.
- Nội dung trả về phần lớn là tiếng Việt không dấu, ví dụ `Tien thua can...`, làm giảm chất lượng UI.
- 7 ca này chỉ kiểm tra một điểm trên mỗi miền, không chứng minh độ chính xác trên biên, giới tính/tuổi khác nhau hoặc tình huống lâm sàng.

### 3.3 Benchmark ngắn

Mỗi endpoint được gọi tuần tự 10 lần:

| Endpoint | Thành công | P50 | P95 | Trung bình |
|---|---:|---:|---:|---:|
| `GET /health` | 10/10 | 13,4 ms | 202,2 ms | 32,9 ms |
| `POST /tools/bmi` | 10/10 | 13,7 ms | 21,6 ms | 14,5 ms |
| `POST /search`, vector, không rerank | 10/10 | 462,7 ms | 540,4 ms | 469,9 ms |

Tool và retrieval đơn lẻ có tốc độ dùng được. Nút thắt chính không nằm ở phép tính BMI hoặc một lần vector search.

---

## 4. Kiểm thử Agent và routing

### 4.1 Routing độc lập

| Câu hỏi | Agent chọn | Đánh giá |
|---|---|---|
| “Tôi nặng 72kg cao 170cm, BMI của tôi?” | InBody + RAG | Đúng |
| “Tôi nên ăn bao nhiêu protein để giảm mỡ?” | Nutrition + RAG | Đúng |
| “Gợi ý lịch tập kháng lực 3 buổi/tuần” | Training | Đúng Agent chính, thiếu RAG |
| Câu tổng hợp có InBody + ăn uống + tập luyện | InBody + Nutrition + Training + RAG | Đúng |
| “Goi y lich tap khang luc 3 buoi/tuan” không dấu | GeneralChat | Sai |

- Khớp Agent ý định chính: 4/5.
- Khớp đầy đủ tập Agent kỳ vọng: 3/5.

Router dùng danh sách keyword có dấu và các cụm cố định. Nó chưa robust với câu không dấu, typo, từ đồng nghĩa hoặc câu tự nhiên không chứa đúng cụm.

Đáng chú ý, keyword rất rộng `"nên"` làm nhiều câu bị đưa vào RAG (`backend/src/agents/graph.py`, khoảng dòng 190). Câu cấp cứu “có nên tiếp tục tập không?” vì vậy phải chạy query rewrite + retrieval trước khi trả cảnh báo.

### 4.2 Luồng Agent toàn tuyến

#### Ca 1 — lời chào

- Input: “Xin chào, bạn có thể giúp gì cho tôi?”
- Agent chọn: `GeneralChatAgent`.
- Thời gian: 65,148 giây.
- Output thực tế:

> Mình đã xử lý câu hỏi theo luồng Multi-Agent RAG MVP...  
> Lưu ý an toàn: Thong tin chi mang tinh tham khao...

Routing đúng nhưng response không trả lời hữu ích. Đây là fallback sau khi LLM timeout.

#### Ca 2 — tính BMI

- Input: 72 kg, 170 cm.
- Tool nội bộ tính đúng BMI 24,91.
- Query rewrite mất gần 58 giây.
- Sau retrieval, response composer timeout thêm 60 giây.
- Client timeout tại 120,106 giây; server vẫn hoàn tất và ghi HTTP 200 ngay sau đó.

Người dùng không nhận được kết quả dù tool đã có câu trả lời đúng gần như tức thời.

#### Ca 3 — cấp cứu

- Input: “Tôi đau ngực và khó thở khi tập. Tôi có nên tiếp tục tập không?”
- Safety tool xác định `urgent`.
- Hệ thống vẫn chạy query rewrite, ba vector search, rerank và response composer.
- Client timeout sau 100,082 giây.
- Log server cho thấy request hoàn tất sau khoảng 121 giây và dùng fallback.

Đây là lỗi nghiêm trọng: cảnh báo cấp cứu phải được trả bằng fast-path quyết định, không phụ thuộc RAG hoặc LLM.

### 4.3 Nguyên nhân gốc của timeout LLM

`backend/src/brain.py`:

- mặc định `LLM_MAX_TOKENS=1024` ở dòng 20;
- payload Ollama ở khoảng dòng 69–76 chỉ đặt `temperature` và `num_predict`;
- không đặt `think: false`;
- timeout mỗi lần gọi là 60 giây.

Thử trực tiếp cùng `qwen3:8b`:

| Cấu hình | Thời gian | `message.content` | Kết quả |
|---|---:|---|---|
| Giống backend, Qwen3 thinking mặc định, `num_predict=20` | 8,668 giây | rỗng | Hết token trong `message.thinking` |
| Thêm `think=false`, `num_predict=20` | 7,927 giây | `general_chat` | Đúng |

Đây là bằng chứng trực tiếp cho warning trong log: `Invalid LLM route ''`.

Ở response composer, giới hạn 1.024 token cho phép mô hình dành phần lớn thời gian/tokens cho thinking và chạm timeout. Ngoài ra, một câu RAG có thể gọi LLM hai lần: rewrite rồi compose, nên tổng timeout có thể vượt 120 giây.

### 4.4 Hiệu quả orchestration

Hiện tại orchestration có nhiều bước đúng về kiến trúc nhưng chưa hiệu quả:

1. Tool có thể trả BMI trong khoảng 10–20 ms.
2. Agent vẫn gọi query rewrite bằng LLM.
3. Agent chạy ba truy vấn vector.
4. Agent rerank.
5. Agent gọi LLM composer.
6. Nếu LLM lỗi, mới trả fallback.

Với câu hỏi tính toán hoặc cấp cứu, chuỗi này làm tăng latency mà không tăng độ chính xác tương ứng.

---

## 5. Kiểm thử RAG và Qdrant

### 5.1 Retrieval không rerank

| Truy vấn | Loại kỳ vọng | Top 1 | Hit@5 | Đánh giá ngữ nghĩa top 1 |
|---|---|---|---|---|
| BMI, PBF, SMM khác nhau thế nào | `inbody_metric` | `inbody_metric` | Có | Liên quan |
| Mỡ nội tạng level 12 có ý nghĩa gì | `inbody_metric` | `inbody_metric` | Có | Sai trọng tâm: tài liệu BMI |
| Bao nhiêu protein khi giảm mỡ | `nutrition` | `nutrition` | Có | Chỉ nói chung, không trả lượng protein |
| Lịch tập kháng lực 3 buổi cho người mới | `exercise` | `exercise` | Có | Liên quan trực tiếp |
| Đau ngực và khó thở khi tập | `medical_safety` | `nutrition` | Không | Không liên quan/an toàn |

Các chỉ số:

- top-1 đúng `content_type`: 4/5 = 80%;
- Hit@5 theo `content_type`: 4/5 = 80%;
- top-1 trả lời trực tiếp câu hỏi theo chấm strict thủ công: 2/5 = 40%.

Sự khác biệt 80% và 40% cho thấy chỉ đo đúng metadata category sẽ tạo cảm giác độ chính xác cao giả tạo.

### 5.2 Rerank

Với truy vấn cấp cứu, rerank đưa lên đầu:

1. “Lòng Heo Xào Cải Chua”;
2. “Gà Xào Nghệ Cà Ri”;
3. tài liệu chung về mỡ nội tạng.

Không có tài liệu `medical_safety` trong top 5 dù collection đã có 36 point mang nhãn này.

Rerank hiện tại là heuristic local (`backend/src/rerank.py`), không đảm bảo semantic relevance. Trong ca safety, nó làm thứ tự tệ hơn.

### 5.3 “Hybrid search” hiện không thực sự hybrid

Backend health trả:

```json
{
  "initialized": false,
  "documents_count": 0,
  "has_bm25": false
}
```

BM25 được giữ trong biến global RAM (`backend/src/search.py`, dòng 19–21, 163–192). Backend chạy Uvicorn 2 worker (`backend/docker-compose.yml`, dòng 12), nên mỗi worker có một index riêng. Sau restart, index mất; khi import theo batch, việc gọi initialize còn có nguy cơ thay toàn bộ index bằng batch mới.

Trong trạng thái test, kết quả gọi là “hybrid” nhưng thực chất chỉ có vector search.

### 5.4 Chất lượng corpus

- Corpus lệch mạnh về nutrition.
- Kết quả safety bị lẫn công thức món ăn.
- Nguồn `internal_seed` ngắn và không dấu.
- Metadata `general`/`general_health` không thống nhất.
- Chưa thấy version corpus, checksum, ingestion manifest và bộ dữ liệu đánh giá đi kèm.

Không thể kết luận Agent “grounded” chỉ vì có 5 document trong context. Grounded cần kiểm tra answer có bám đúng tài liệu và trích nguồn đúng; hiện full-agent thường timeout trước khi sinh answer.

---

## 6. Kiểm thử giao diện

### 6.1 Kiểm thử cấu trúc và chức năng headless

Streamlit AppTest render thành công, không có exception trong logic app.

Phát hiện được:

- 4 tab: Chat, Dev tool test, Search, System;
- 16 button;
- 5 number input;
- 5 selectbox;
- chat input, text input, textarea, slider và checkbox có nhãn;
- sidebar có backend health, agent capabilities, session và cảnh báo y tế.

Các tương tác đã test:

| Luồng UI | Kết quả |
|---|---|
| Kiểm tra backend | Hiện “Backend đang phản hồi”, nhận JSON health |
| Form BMI 72 kg/170 cm | Hiện BMI 24,91 |
| Form safety với đau ngực | Hiện `urgent` |
| Search mặc định | Hiển thị 5 kết quả |
| Initial render | Không exception |

### 6.2 Chat UI

Chat gọi `/chat/complete` với timeout 120 giây (`frontend/chat_interface_new.py`, dòng 28 và 270). Backend Agent đã mất khoảng 121 giây ở hai ca RAG/safety, nên UI có thể báo lỗi kỹ thuật ngay trước lúc backend hoàn tất.

Giao diện không streaming token; người dùng nhìn spinner trong thời gian dài mà không có tiến độ theo bước.

### 6.3 UX và nội dung

Điểm tốt:

- Phân chia Chat/Dev/Search/System rõ cho demo phát triển.
- Form có giới hạn min/max nên ngăn nhiều đầu vào sai từ UI.
- Có lưu ý y tế thường trực.
- Có agent trace và xuất JSON hội thoại.

Điểm cần sửa:

- Output tool và corpus tiếng Việt không dấu.
- Fallback dùng thuật ngữ kỹ thuật “Multi-Agent RAG MVP”, không hữu ích với người dùng cuối.
- Dev tools và thông tin hệ thống không nên mở cho user production.
- Chưa hiển thị tiến độ import Qdrant hoặc cảnh báo “dữ liệu đang thiếu”.
- Không có citation rõ ràng trong chat khi LLM fallback.
- Timeout 120 giây tạo trải nghiệm rất kém.

### 6.4 Rủi ro render HTML

UI dùng nhiều `unsafe_allow_html=True`. Đặc biệt title/source lấy từ kết quả RAG được chèn vào HTML ở khoảng dòng 594–603 của `frontend/chat_interface_new.py` mà chưa escape. Vì backend có endpoint tạo document, đây là nguy cơ HTML injection/stored XSS nếu endpoint không được bảo vệ. Cần kiểm thử bảo mật riêng trước khi khẳng định có thể thực thi script.

### 6.5 Giới hạn kiểm thử trực quan

Công cụ điều khiển trình duyệt không khởi tạo được do lỗi môi trường:

```text
failed to write kernel assets: The system cannot find the path specified. (os error 3)
```

Vì vậy báo cáo **không khẳng định**:

- bố cục desktop/mobile không vỡ;
- màu sắc/contrast đạt WCAG;
- focus bàn phím và screen reader hoạt động;
- spinner, scroll, chat bubble và agent trace hiển thị đúng trên browser thật.

HTTP frontend vẫn trả 200 trong 335 ms. Response không có Content-Security-Policy hoặc X-Frame-Options tại snapshot.

---

## 7. Các lỗi theo mức độ ưu tiên

### P0 — chặn production

#### P0.1 Agent timeout do Qwen3 thinking

- Router có thể nhận `content=""`.
- Rewrite và composer mỗi bước có thể chờ 60 giây.
- Người dùng chờ 65–121 giây hoặc nhận lỗi timeout.

#### P0.2 Safety không có fast-path

- Tool xác định cấp cứu nhanh nhưng câu trả lời vẫn chờ RAG/LLM.
- Truy vấn cấp cứu retrieval ra món ăn.
- Trong tình huống thật, cảnh báo chậm hơn 100 giây là không chấp nhận được.

#### P0.3 Chưa có lớp bảo vệ dữ liệu/người dùng đủ cho production

Các endpoint đọc/ghi dữ liệu và `user_id` cần auth/authorization. Dữ liệu InBody là dữ liệu sức khỏe nhạy cảm. Không nên triển khai công khai trước khi có xác thực, phân quyền, audit log và chính sách lưu/xóa dữ liệu.

### P1 — nghiêm trọng

#### P1.1 Import chưa hoàn tất và corpus mất cân bằng

Tại snapshot chỉ có 28,93% số chunk dự kiến. Không thể ký duyệt accuracy khi dữ liệu còn thay đổi.

#### P1.2 BM25 không hoạt động

Hệ thống gắn nhãn hybrid nhưng runtime chỉ vector. Thiết kế BM25 global RAM không phù hợp nhiều worker/restart.

#### P1.3 Retrieval/rerank safety sai

Medical query không tìm được safety content trong top 5. Rerank đưa recipe lên đầu.

#### P1.4 Chưa có output guardrail độc lập

Safety hiện kiểm tra input. Cần kiểm tra câu trả lời cuối để chặn chẩn đoán, kê đơn, khẳng định quá mức và hướng dẫn nguy hiểm.

#### P1.5 Nguy cơ HTML injection ở UI

Metadata từ document được đưa vào HTML không escape trong khi endpoint tạo document có thể bị gọi trực tiếp.

### P2 — cần sửa trước beta

- Router nhạy với dấu và cụm từ chính xác.
- Keyword `"nên"` quá rộng, gây gọi RAG thừa.
- API validation trả HTTP 200 cho lỗi domain.
- Response không dấu.
- UI không streaming, không progress.
- Backend trả 200 fallback sau khi client đã timeout.
- Endpoint `/agent/answer` không trả trường `errors`, làm giảm observability.
- Chưa có bộ test/benchmark có ground truth và CI.

---

## 8. Kế hoạch sửa đề xuất

### Giai đoạn 1 — sửa P0, mục tiêu 1–2 ngày

1. Với Ollama/Qwen3, thêm `think: false` vào payload cho router, query rewrite và composer.
2. Giảm token:
   - router: 8–16;
   - rewrite: tối đa 64–128;
   - composer: khoảng 256–400 cho câu trả lời ngắn.
3. Tạo safety fast-path chạy trước supervisor/RAG:
   - nếu `urgent`, trả response quyết định ngay;
   - không gọi rewrite, retrieval hoặc composer.
4. Với phép tính BMI/PBF/visceral fat, cho phép trả template từ tool ngay; LLM chỉ làm đẹp câu khi có ngân sách thời gian.
5. Đặt timeout theo toàn request, không cộng dồn 60 giây cho từng bước.
6. Trả status lỗi đúng chuẩn và dừng xử lý khi client disconnect.

### Giai đoạn 2 — ổn định dữ liệu/RAG

1. Hoàn tất import; xác minh point count bằng manifest và checksum, không chỉ nhìn `green`.
2. Chuẩn hóa `content_type`, source, document/chunk ID và phiên bản corpus.
3. Thay BM25 global RAM bằng:
   - Qdrant sparse vector/hybrid, hoặc
   - search service/index bền vững dùng chung giữa worker.
4. Dùng filter/boost theo intent; ưu tiên `medical_safety` cho triệu chứng nguy hiểm.
5. Loại recipe khỏi candidate set khi query là medical safety.
6. Chỉ rewrite khi thật sự cần; retrieval lần đầu nên dùng câu gốc.
7. Đánh giá reranker trên bộ query có nhãn trước khi bật mặc định.

### Giai đoạn 3 — chất lượng, UI và bảo mật

1. Xây bộ benchmark tối thiểu 100 câu:
   - InBody;
   - nutrition;
   - exercise;
   - safety;
   - follow-up;
   - không dấu, typo, prompt injection.
2. Đo Precision@k, Recall@k, MRR, groundedness, citation accuracy, safety pass rate và latency.
3. Thêm streaming/progress cho chat.
4. Escape mọi metadata trước khi render; hạn chế `unsafe_allow_html`.
5. Ẩn Dev tool test/System trong production.
6. Thêm auth, authorization theo user, rate limit, audit log và chính sách dữ liệu sức khỏe.
7. Chạy visual regression, mobile viewport, keyboard navigation và accessibility audit trên browser thật.

---

## 9. Tiêu chí nghiệm thu đề xuất

Chỉ nên gọi hệ thống “đạt Agent RAG beta” khi thỏa tối thiểu:

| Tiêu chí | Ngưỡng |
|---|---:|
| Safety urgent đúng hành động | 100% trên ít nhất 20 ca chuẩn hóa |
| Safety urgent P95 | < 500 ms |
| Router đúng intent | ≥ 95% trên bộ có dấu/không dấu/typo |
| Retrieval Hit@5 | ≥ 90% trên ít nhất 100 câu có ground truth |
| Semantic top-1 relevance | ≥ 75% |
| Chat thời gian tới token đầu | P95 < 5 giây |
| Chat hoàn tất | P95 < 15 giây |
| Request vượt 60 giây | 0% trong test chuẩn |
| Qdrant | Point count khớp manifest, metadata schema nhất quán |
| BM25/hybrid | Có bằng chứng cả dense và sparse thực sự tham gia |
| UI | Không lỗi chức năng, không lỗi visual/accessibility nghiêm trọng |
| Security | Không còn P0/P1 về auth, data isolation, injection |

---

## 10. Kết luận

Dự án đã có các thành phần đúng hướng của một Agent RAG:

- orchestration bằng LangGraph;
- nhiều Agent chuyên trách;
- tool có tính xác định;
- Qdrant + embedding;
- query rewrite, retrieval và rerank;
- safety tool;
- giao diện chat/dev/search.

Tuy nhiên, **có thành phần Agent RAG không đồng nghĩa hệ thống đã đạt chuẩn vận hành**. Ở trạng thái được kiểm thử:

- Agent toàn tuyến không đạt latency;
- LLM integration sai với chế độ thinking của Qwen3;
- safety end-to-end trả quá chậm;
- retrieval safety sai nghiêm trọng;
- BM25 không hoạt động;
- dữ liệu mới import khoảng 28,93%;
- chưa có benchmark đủ lớn để tuyên bố accuracy;
- UI chỉ được xác nhận headless, chưa có bằng chứng visual/accessibility;
- còn rủi ro auth và injection.

**Quyết định đề xuất:** không release production. Sửa P0 trước, hoàn tất dữ liệu, chạy lại benchmark sau import, sau đó mới đánh giá lại mức “Agent RAG beta”.

---

## 11. Retest sau khi nạp mã Đợt 1

**Thời gian:** khoảng 17:27–17:34, ngày 30/07/2026 (UTC+7)  
**Cách test:** pytest trên source hiện tại và request HTTP thật tới backend, frontend, embedding, Ollama và Qdrant đang chạy.

### 11.1. Trạng thái dịch vụ

| Dịch vụ | Trạng thái |
|---|---|
| Backend API | Up, hai Uvicorn worker khởi động sạch sau restart |
| Celery worker | Up, đã nạp danh sách task mới |
| Qdrant | `green`, optimizer `ok`, update queue bằng 0 |
| PostgreSQL | Up |
| Valkey | Up |
| Frontend | HTTP 200 tại cổng 8051 |
| Embedding API | Healthy tại cổng 5001, model BGE-M3 đã load |
| Ollama | Có `qwen3:8b`, Q4_K_M; model đang dùng một phần VRAM |

Endpoint `/health` xác nhận runtime đã nạp cấu hình Đợt 1:

- router: 16 token, timeout 8 giây;
- normalize: 96 token, timeout 10 giây;
- rewrite: 128 token, timeout 15 giây;
- composer: 400 token, timeout 30 giây;
- response có `fast_path`, `latency_ms`, `errors` và Agent trace.

### 11.2. Import bị dừng trước khi hoàn tất

Sau restart:

- point dự kiến: **23.608**;
- point thực tế: **13.379**;
- tiến độ: **56,67%**;
- Qdrant update queue: **0**;
- log không còn request upsert mới.

Import không còn chạy. Việc restart backend/embedding diễn ra ngay sau batch cuối trong log, nên nhiều khả năng đã làm dừng process import.

Không được coi collection hiện tại là corpus hoàn chỉnh và chưa nên dùng kết quả retrieval này để tuyên bố accuracy cuối cùng.

### 11.3. Kết quả test source

```text
10 passed, 1 skipped, 1 warning in 0.44s
```

Warning còn lại là deprecation giữa Starlette TestClient và phiên bản `httpx`.

### 11.4. HTTP smoke test

| Ca | HTTP | Kết quả | Latency |
|---|---:|---|---:|
| BMI hợp lệ | 200 | BMI = 24,91 | 110 ms ở lần gọi đầu |
| BMI âm | 422 | Validation đúng | 11 ms |
| PBF nữ | 200 | Tool phản hồi | 10 ms |
| Mỡ nội tạng level 12 | 200 | Tool phản hồi | 7 ms |
| Nutrition | 200 | Tool phản hồi | 9 ms |
| Training | 200 | Tool phản hồi | 19 ms |
| Safety đau ngực + khó thở | 200 | `urgent` | 12 ms |
| Agent urgent | 200 | `urgent_safety`, chỉ chọn SafetyAgent | **10 ms** |
| Agent BMI | 200 | `inbody_tools`, BMI = 24,91 | **11 ms** |
| Agent mỡ nội tạng 12 | 200 | `inbody_tools`, đánh giá hơi cao | **10 ms** |
| Search InBody | 200 | 3 kết quả `inbody_metric` | 1.607 ms |
| Frontend | 200 | Trang Streamlit phản hồi | 493 ms |
| Embedding 4 câu | 200 | 4 vector, 1.024 chiều | 522 ms |

Kết luận P0:

- Safety fast path: **đạt mục tiêu dưới 500 ms** ở smoke test này.
- Deterministic InBody fast path: hoạt động đúng và không phụ thuộc LLM.
- Validation lỗi đầu vào: đã trả 422 đúng.
- Đây mới là smoke test vài ca, chưa thay thế benchmark safety tối thiểu 20 ca.

### 11.5. LLM vẫn là nút thắt

Ca giải thích “BMI, PBF và SMM khác nhau như thế nào?”:

- Agent chọn đúng `InBodyAgent` và `RAGAgent`;
- lấy được 5 tài liệu;
- SafetyAgent chạy thành công;
- ResponseComposer timeout sau 30 giây;
- tổng latency HTTP: **46.572 ms**;
- status trả về: `degraded`;
- fallback có nội dung máy móc và không đưa phần giải thích từ tài liệu vào câu trả lời một cách hữu ích.

Test trực tiếp Ollama:

| Cấu hình | Kết quả | Latency |
|---|---|---:|
| `think=false`, 64 token | Có câu trả lời hoàn chỉnh | 8.273 ms |
| Không gửi `think` (`auto`) | Dùng hết 64 token cho thinking, `content` rỗng | 20.122 ms |

Nguyên nhân đã được chứng minh: `qwen3:8b` mặc định dùng thinking khi `OLLAMA_THINK` để `auto`. Token budget có thể bị tiêu hết cho trường `thinking`, hoặc composer vượt timeout trước khi sinh final content.

**Cấu hình cần sửa:** đặt `OLLAMA_THINK=false` cho các task production ngắn. Không hard-code model; đây phải là capability/config theo provider hoặc theo task.

### 11.6. Embedding chưa sử dụng GPU

Host:

- GPU: NVIDIA GeForce RTX 3050 Laptop;
- VRAM: 4.096 MiB;
- GPU nhìn thấy và đang có tải.

Trong embedding container:

- `nvidia-smi` nhìn thấy RTX 3050;
- PyTorch: `2.13.0+cu130`;
- `torch.cuda.device_count() = 1`;
- `torch.cuda.is_available() = false`;
- CUDA lỗi `Error 500: named symbol not found`;
- service fallback sang CPU, `ENCODE_BATCH_SIZE=2`.

Nguyên nhân cấu hình:

- image đang build từ `Dockerfile.cpu-serving`;
- file requirement để `torch>=2.6.0`, không khóa phiên bản/CUDA wheel;
- Compose lại yêu cầu GPU cho image CPU;
- Flask development server đang được dùng.

Do đó, việc thêm GPU reservation chưa đủ để service dùng CUDA. Cần một GPU image được pin rõ phiên bản PyTorch/CUDA tương thích và test `torch.cuda.is_available()` trong CI/smoke startup.

### 11.7. Metadata Qdrant bị ghi đè

Phân bố point thực tế sau restart:

| `content_type` | Số point |
|---|---:|
| `general` | 9.894 |
| `nutrition` | 3.355 |
| `medical_safety` | 110 |
| `inbody_metric` | 14 |
| `exercise` | 6 |
| `general_health` | 0 |
| **Tổng** | **13.379** |

Nguyên nhân nằm trong `vectorize.add_vector()`:

```python
payload={
    **v["payload"],
    ...
    "content_type": detect_content_type(v["payload"].get("content", "")),
}
```

`content_type` đã được pipeline chuẩn hóa bị ghi đè bằng heuristic theo từng chunk. Ví dụ recipe có metadata nguồn thuộc corpus dinh dưỡng nhưng chunk nguyên liệu không chứa từ khóa dinh dưỡng sẽ trở thành `general`.

Hệ quả:

- Dry-run và dữ liệu thực tế trong Qdrant không cùng schema.
- Filter/boost theo intent sai.
- Safety/general query có thể lấy món ăn.
- Một document có thể bị chia thành nhiều `content_type` khác nhau theo từng chunk.

Ngoài ra `payload_schema` của collection đang rỗng. Qdrant từ chối facet theo `content_type` vì chưa có payload index. Filter ở quy mô lớn sẽ không có hiệu năng như mong đợi.

### 11.8. Retrieval smoke test sau restart

| Query group | Top-1 kỳ vọng | Top-1 thực tế | Đúng loại |
|---|---|---|---|
| InBody | `inbody_metric` | `inbody_metric` | Có |
| Nutrition | `nutrition` | `nutrition` | Có, nhưng tài liệu top-1 chưa trả lời trực tiếp câu protein |
| Exercise | `exercise` | `exercise` | Có |
| Medical safety | `medical_safety` | `general` — recipe “Gà Xào Nghệ Cà Ri” | **Không** |
| General health | `general_health` | `nutrition` — recipe “Salad Thịt Bò Xào Chay” | **Không** |

Top-1 type accuracy của 5 smoke query: **3/5 = 60%**. Con số này chỉ có tính phát hiện lỗi vì corpus mới đạt 56,67% và chưa phải golden benchmark.

### 11.9. Kết luận retest

Đợt 1 đã sửa đúng hai lỗi P0 quan trọng:

1. Urgent safety không còn chờ LLM/RAG.
2. BMI/InBody có deterministic fast path rất nhanh.

Nhưng chưa thể đánh dấu Đợt 1 hoàn tất vì còn bốn blocker:

1. Import đã dừng ở 13.379/23.608 point.
2. `OLLAMA_THINK=auto` làm LLM timeout hoặc sinh thinking mà không có final content.
3. `content_type` chuẩn bị từ data pipeline bị ghi đè sai khi upsert.
4. Embedding container chưa dùng GPU do image/PyTorch/CUDA không tương thích.

**Thứ tự sửa an toàn tiếp theo:**

1. Sửa logic giữ nguyên `record.content_type`, chỉ heuristic fallback khi field trống.
2. Đặt `OLLAMA_THINK=false`, recreate riêng API/worker và retest ca RAG.
3. Pin GPU image/PyTorch/CUDA cho embedding, xác nhận `device=cuda`.
4. Tạo collection phiên bản mới cùng payload index.
5. Rerun import idempotent vào collection mới; chỉ đổi alias sau khi đủ 23.608 point và benchmark đạt.

---

## 12. Tiến độ triển khai giai đoạn kế tiếp

### 12.1. Backend P0 đã deploy có kiểm soát

Trước mỗi lần recreate API/worker:

- Qdrant cũ có 13.379 point;
- `update_queue.length=0`;
- không có process `import_data.py`;
- Qdrant và embedding không bị restart.

Sau deploy, `/health` runtime xác nhận:

```text
OLLAMA_THINK=false
AGENT_REQUEST_TIMEOUT_SECONDS=30
RAG_MAX_RETRIEVAL_QUERIES=1
RAG_EMBEDDING_TIMEOUT_SECONDS=10
QDRANT_SEARCH_TIMEOUT_SECONDS=5
LLM_COMPOSER_MAX_TOKENS=160
LLM_COMPOSER_TIMEOUT=20
RAG_COMPOSER_MAX_DOCS=3
RAG_COMPOSER_MAX_CHARS_PER_DOC=700
```

HTTP thật sau deploy:

| Ca | Kết quả | Wall time |
|---|---|---:|
| Urgent đau ngực + khó thở | `ok`, `urgent_safety` | 218 ms |
| BMI 72 kg/170 cm | `ok`, `inbody_tools`, BMI 24,91 | 15 ms |
| Giải thích BMI/PBF/SMM trước deadline | client timeout | >65 giây |
| Giải thích BMI/PBF/SMM sau deadline | `degraded`, fallback an toàn | backend 29,89 giây |
| Sau giảm prompt/token composer | `degraded`, fallback sạch | backend 23,30 giây |

Deadline giải quyết tình trạng request chạy quá lâu, nhưng không làm LLM nhanh
hơn. Qwen3 8B hiện có footprint 6,0 GB và `ollama ps` báo 61% CPU/39% GPU trên
GPU 4 GB. Hai request trực tiếp 64/96 token đều vượt timeout 30 giây khi hàng
đợi Ollama đang bận. LLM composer vì vậy vẫn là blocker chất lượng.

### 12.2. Source dữ liệu/Qdrant v2

Đã triển khai ở source:

- giữ nguyên `content_type` chuẩn hóa, heuristic chỉ dùng khi field trống;
- payload có `document_id`, `corpus_version`, `content_hash`, stable UUID;
- manifest import có SHA-256, dòng xử lý cuối và dòng upsert thành công cuối;
- hỗ trợ `--start-line` để resume;
- lỗi upsert là fatal, không tiếp tục ghi log thành công giả;
- importer không tuyên bố BM25 đã persist vì index hiện chỉ nằm trong RAM;
- CLI Qdrant hỗ trợ create, verify, ensure-indexes và atomic alias switch có
  expected point count.

Đã tạo và nạp đầy đủ collection vật lý:

```text
nmk_chatbot_collection_v20260730_bge_m3_1024
points_count=23608
vector_size=1024
status=green
payload_indexes=10
```

Lệnh create đầu tiên timeout ở client nhưng Qdrant đã tạo collection phía
server. Hệ thống đã kiểm tra trước khi retry, sau đó tạo index idempotent. Client
admin/write được nâng timeout mặc định lên 30 giây; search vẫn dùng client riêng
với timeout 5 giây.

Collection v2 đã hoàn tất import missing-only, `optimizer=ok`, `error_count=0`;
manifest cuối: `backend/artifacts/imports/2026-08-06-v2-cross-batch-import.json`.
Alias `nmk_chatbot_active` đã trỏ vào v2 và backend health xác nhận đang dùng
alias. Collection cũ `nmk_chatbot_collection` đã được xóa theo yêu cầu sau khi
chuyển runtime thành công. Retrieval benchmark chính thức vẫn còn cần chạy.

### 12.3. Kiểm thử source

```text
23 passed
Python compile: đạt
Backend compose config: đạt
Embedding compose config: đạt
git diff --check: đạt
```

Một integration test vẫn được skip khi dependency runtime không có trên host.
HTTP runtime được dùng riêng để kiểm chứng, không lấy TestClient thay thế.

### 12.4. Embedding GPU

Source đã có image CUDA 12.8/PyTorch 2.8 cu128, FP16, one-worker Gunicorn và
fail-fast nếu `EMBEDDING_DEVICE=cuda` nhưng CUDA không khả dụng. Image build
thành công với command Gunicorn mới, nhưng CUDA smoke test trong container tạm
vẫn thất bại:

```text
torch=2.8.0+cu128
nvidia-smi=NVIDIA GeForce RTX 3050 Laptop GPU, driver 591.74
torch CUDA init=Error 500: named symbol not found
```

`cuDriverGetVersion()` gọi được và trả API 13.1, nhưng tensor FP16 đầu tiên vẫn
lỗi ở `cudaGetDeviceCount()`. Workaround
`PYTORCH_NVML_BASED_CUDA_CHECK=1` chỉ làm `torch.cuda.is_available()` trả
`true` giả; tensor thật vẫn lỗi nên đã bị loại bỏ.

Máy đang dùng Docker Desktop 4.26.1 / Engine 24.0.7 build tháng 10/2023. Đây là
lớp runtime quá cũ so với Windows NVIDIA driver hiện tại. PyTorch có issue cùng
triệu chứng trên WSL2 và ghi nhận cập nhật/restart Docker Desktop đã giải quyết
trường hợp tương tự. NVIDIA cũng yêu cầu driver Windows được stub thành
`libcuda.so` trong WSL và không cài Linux GPU driver riêng trong WSL:

- <https://github.com/pytorch/pytorch/issues/124280>
- <https://docs.nvidia.com/cuda/wsl-user-guide/index.html>

Container CPU cũ vẫn tiếp tục phục vụ; image GPU mới chưa được deploy.

Benchmark CPU hiện tại với 32 text, mỗi text 554 ký tự:

```text
wall time=18,50 giây
service inference=18,17 giây
throughput=1,73 text/giây
```

Với 23.608 chunk, riêng embedding ước tính khoảng 13.646 giây, tức 3 giờ
47 phút; tổng import thực tế sẽ dài hơn vì network, JSON và Qdrant upsert. Do đó
chưa bắt đầu import CPU vào collection release.

### 12.5. Dry-run corpus v2

Dry-run đầu tiên lộ thêm bottleneck: `split_document()` compile một LangGraph
mới cho từng document. Sau khi cache splitter graph bằng `lru_cache(maxsize=1)`,
dry-run hoàn tất trong 12,18 giây:

```json
{
  "status": true,
  "processed_docs": 5345,
  "skipped_docs": 0,
  "total_chunks": 23608,
  "error_count": 0,
  "data_file_sha256": "1a474bf5562b8b571eb301f41517d0d2a7739d0e61ef6998fe903365c8665eea",
  "bm25_index_persisted": false
}
```

Manifest được lưu tại
`backend/artifacts/imports/2026-07-30-v2-dry-run.json`. Collection v2 vẫn có
0 point và Qdrant update queue bằng 0 sau dry-run.
