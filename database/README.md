# Database Schema - Health/InBody Agent RAG

Thư mục này chứa schema PostgreSQL cho backend Health/InBody Agent RAG.

File chính:

```text
database/init.sql
```

File này được mount vào PostgreSQL container trong `backend/docker-compose.yml`:

```text
../database/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
```

Khi PostgreSQL khởi tạo database lần đầu, script sẽ tạo extension, tables và indexes cần thiết.

---

# 1. Tổng Quan

Database lưu dữ liệu nghiệp vụ của hệ thống:

* Hồ sơ người dùng.
* Lịch sử đo InBody.
* Phiên chat và tin nhắn.
* Metadata tài liệu RAG.
* Chunk tài liệu có liên kết với Qdrant.
* File upload và kết quả OCR/parser.

Qdrant vẫn là nơi lưu vector embedding chính. PostgreSQL giữ dữ liệu có cấu trúc và metadata để backend có thể truy vết, hiển thị lịch sử và liên kết với người dùng.

---

# 2. Sơ Đồ Quan Hệ

```text
users
  ├── inbody_measurements
  ├── chat_sessions
  │     └── chat_messages
  └── uploaded_files

documents
  └── document_chunks
          └── qdrant_point_id -> Qdrant point
```

---

# 3. Extension

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

`pgcrypto` được dùng để tạo UUID bằng `gen_random_uuid()`.

---

# 4. Bảng `users`

Lưu hồ sơ người dùng.

| Cột                  | Kiểu         | Ý nghĩa                                      |
| -------------------- | ------------ | -------------------------------------------- |
| `id`                 | UUID         | Khóa chính                                   |
| `external_id`        | VARCHAR(128) | ID người dùng từ frontend/hệ thống ngoài     |
| `full_name`          | VARCHAR(255) | Họ tên                                       |
| `email`              | VARCHAR(255) | Email, unique                                |
| `sex`                | VARCHAR(32)  | Giới tính                                    |
| `birth_year`         | INTEGER      | Năm sinh                                     |
| `height_cm`          | NUMERIC(6,2) | Chiều cao mặc định                           |
| `activity_level`     | VARCHAR(64)  | Mức độ vận động                              |
| `goal`               | VARCHAR(64)  | Mục tiêu: fat_loss, muscle_gain, maintain... |
| `medical_conditions` | TEXT         | Bệnh nền/lưu ý sức khỏe                      |
| `created_at`         | TIMESTAMPTZ  | Thời điểm tạo                                |
| `updated_at`         | TIMESTAMPTZ  | Thời điểm cập nhật                           |

Quan hệ:

* 1 user có nhiều `inbody_measurements`.
* 1 user có nhiều `chat_sessions`.
* 1 user có nhiều `uploaded_files`.

---

# 5. Bảng `inbody_measurements`

Lưu từng lần đo InBody của người dùng.

| Cột                   | Kiểu         | Ý nghĩa                              |
| --------------------- | ------------ | ------------------------------------ |
| `id`                  | UUID         | Khóa chính                           |
| `user_id`             | UUID         | Khóa ngoại đến `users.id`            |
| `measurement_date`    | DATE         | Ngày đo                              |
| `height_cm`           | NUMERIC(6,2) | Chiều cao tại thời điểm đo           |
| `weight_kg`           | NUMERIC(6,2) | Cân nặng                             |
| `bmi`                 | NUMERIC(5,2) | Body Mass Index                      |
| `smm_kg`              | NUMERIC(6,2) | Skeletal Muscle Mass                 |
| `bfm_kg`              | NUMERIC(6,2) | Body Fat Mass                        |
| `pbf_percent`         | NUMERIC(5,2) | Percent Body Fat                     |
| `visceral_fat_level`  | NUMERIC(5,2) | Mức mỡ nội tạng                      |
| `body_water_l`        | NUMERIC(6,2) | Lượng nước cơ thể                    |
| `recommendation_goal` | VARCHAR(64)  | Mục tiêu gợi ý sau khi phân tích     |
| `source_file`         | VARCHAR(512) | File nguồn nếu dữ liệu đến từ upload |
| `raw_payload`         | JSONB        | Kết quả parse/OCR gốc                |
| `created_at`          | TIMESTAMPTZ  | Thời điểm tạo                        |
| `updated_at`          | TIMESTAMPTZ  | Thời điểm cập nhật                   |

Ràng buộc:

```sql
user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
```

Nếu xóa user, các lần đo InBody của user đó cũng bị xóa.

---

# 6. Bảng `chat_sessions`

Lưu phiên chat.

| Cột                | Kiểu         | Ý nghĩa                                         |
| ------------------ | ------------ | ----------------------------------------------- |
| `id`               | UUID         | Khóa chính                                      |
| `bot_id`           | VARCHAR(128) | Mặc định `health-inbody-agent`                  |
| `user_id`          | UUID         | Khóa ngoại đến `users.id`, có thể null          |
| `external_user_id` | VARCHAR(128) | ID user từ client khi chưa có row trong `users` |
| `title`            | VARCHAR(255) | Tiêu đề phiên chat                              |
| `created_at`       | TIMESTAMPTZ  | Thời điểm tạo                                   |
| `updated_at`       | TIMESTAMPTZ  | Thời điểm cập nhật                              |

---

# 7. Bảng `chat_messages`

Lưu tin nhắn trong một phiên chat.

| Cột          | Kiểu        | Ý nghĩa                           |
| ------------ | ----------- | --------------------------------- |
| `id`         | UUID        | Khóa chính                        |
| `session_id` | UUID        | Khóa ngoại đến `chat_sessions.id` |
| `role`       | VARCHAR(32) | `user`, `assistant`               |
| `content`    | TEXT        | Nội dung tin nhắn                 |
| `route`      | VARCHAR(64) | Route xử lý                       |
| `metadata`   | JSONB       | Metadata bổ sung                  |
| `created_at` | TIMESTAMPTZ | Thời điểm tạo                     |

---

# 8. Bảng `documents`

Lưu tài liệu nguồn cho RAG.

| Cột             | Kiểu         | Ý nghĩa                  |
| --------------- | ------------ | ------------------------ |
| `id`            | UUID         | Khóa chính               |
| `external_id`   | VARCHAR(128) | ID từ data pipeline      |
| `title`         | VARCHAR(512) | Tiêu đề tài liệu         |
| `content`       | TEXT         | Nội dung gốc             |
| `source`        | VARCHAR(512) | Nguồn dữ liệu            |
| `document_type` | VARCHAR(128) | Loại tài liệu            |
| `content_type`  | VARCHAR(128) | Nhóm nội dung            |
| `domain`        | VARCHAR(128) | Mặc định `health_inbody` |
| `metadata`      | JSONB        | Metadata bổ sung         |
| `created_at`    | TIMESTAMPTZ  | Thời điểm tạo            |
| `updated_at`    | TIMESTAMPTZ  | Thời điểm cập nhật       |

---

# 9. Bảng `document_chunks`

Lưu các chunk đã tách từ `documents`.

| Cột               | Kiểu         | Ý nghĩa                         |
| ----------------- | ------------ | ------------------------------- |
| `id`              | UUID         | Khóa chính                      |
| `document_id`     | UUID         | Khóa ngoại đến `documents.id`   |
| `qdrant_point_id` | VARCHAR(128) | ID point tương ứng trong Qdrant |
| `chunk_index`     | INTEGER      | Thứ tự chunk                    |
| `content`         | TEXT         | Nội dung chunk                  |
| `content_type`    | VARCHAR(128) | Nhóm nội dung                   |
| `token_count`     | INTEGER      | Số token                        |
| `metadata`        | JSONB        | Metadata bổ sung                |
| `created_at`      | TIMESTAMPTZ  | Thời điểm tạo                   |

---

# 10. Bảng `uploaded_files`

Lưu thông tin file người dùng upload.

| Cột                 | Kiểu          | Ý nghĩa                   |
| ------------------- | ------------- | ------------------------- |
| `id`                | UUID          | Khóa chính                |
| `user_id`           | UUID          | Khóa ngoại đến `users.id` |
| `original_filename` | VARCHAR(512)  | Tên file gốc              |
| `storage_path`      | VARCHAR(1024) | Đường dẫn file            |
| `mime_type`         | VARCHAR(128)  | MIME type                 |
| `file_size_bytes`   | BIGINT        | Kích thước file           |
| `processing_status` | VARCHAR(64)   | pending/processing/done   |
| `extracted_text`    | TEXT          | Text OCR                  |
| `parsed_payload`    | JSONB         | Kết quả parser            |
| `created_at`        | TIMESTAMPTZ   | Thời điểm tạo             |
| `updated_at`        | TIMESTAMPTZ   | Thời điểm cập nhật        |

---

# 11. Quan Hệ Với Backend ORM

Schema SQL này tương ứng với các class trong:

```text
backend/src/models.py
```

| SQL Table             | ORM Class           |
| --------------------- | ------------------- |
| `users`               | `User`              |
| `inbody_measurements` | `InBodyMeasurement` |
| `chat_sessions`       | `ChatSession`       |
| `chat_messages`       | `ChatMessage`       |
| `documents`           | `Document`          |
| `document_chunks`     | `DocumentChunk`     |
| `uploaded_files`      | `UploadedFile`      |

---

# 12. Kết Luận

PostgreSQL đóng vai trò là database nghiệp vụ chính của hệ thống Health/InBody Agent RAG.

Database này hỗ trợ:

* Quản lý dữ liệu người dùng.
* Lưu lịch sử InBody.
* Lưu lịch sử chat AI.
* Quản lý metadata tài liệu RAG.
* Liên kết với Qdrant Vector Database.
* Hỗ trợ OCR/parser cho file upload.

Kiến trúc này giúp hệ thống dễ mở rộng cho AI Agent, Health Analytics và Retrieval-Augmented Generation (RAG).
