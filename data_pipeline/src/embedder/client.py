"""Module Client Gọi Dịch vụ Vector Hóa Văn bản BGE-M3 (Embedding Client).

Vai trò:
    Đảm nhiệm việc kết nối tới service mô hình nhúng BGE-M3 (phục vụ tại endpoint HTTP
    `http://localhost:5001/embed`), chia lô (batching) văn bản tự động, kiểm soát timeout,
    xử lý lỗi mạng và cung cấp cơ chế sinh vector giả lập tất định (deterministic mock vectors)
    khi chạy kiểm thử ở chế độ dry-run mà không cần GPU/server thật.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import List, Union

import requests

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Client kết nối dịch vụ nhúng đa ngữ BGE-M3."""

    def __init__(
        self,
        api_url: str = "http://localhost:5001",
        batch_size: int = 32,
        timeout: float = 30.0,
        vector_size: int = 1024,
    ) -> None:
        """Khởi tạo cấu hình cho EmbeddingClient.

        Vai trò:
            Thiết lập endpoint API, kích thước lô mặc định (32 đoạn văn bản mỗi lượt gọi)
            để tối ưu hóa thông lượng và không gây tràn VRAM trên GPU 4GB, cùng kích thước
            vector mục tiêu (1024 chiều).

        Args:
            api_url: Địa chỉ gốc của service nhúng.
            batch_size: Số lượng đoạn văn bản gửi đi trong mỗi batch HTTP request.
            timeout: Thời gian chờ tối đa cho mỗi lượt tính toán embedding (giây).
            vector_size: Số chiều vector đầu ra (mặc định 1024 cho BGE-M3).
        """
        self.api_url = api_url.rstrip("/")
        self.embed_endpoint = f"{self.api_url}/embed"
        self.health_endpoint = f"{self.api_url}/health"
        self.batch_size = batch_size
        self.timeout = timeout
        self.vector_size = vector_size

    def is_available(self) -> bool:
        """Kiểm tra dịch vụ embedding có đang hoạt động hay không.

        Vai trò:
            Gửi health-check request tới endpoint `/health` để xác định mô hình BGE-M3
            đã được nạp vào bộ nhớ và sẵn sàng nhận request hay chưa.

        Returns:
            True nếu HTTP 200, ngược lại False.
        """
        try:
            res = requests.get(self.health_endpoint, timeout=3.0)
            return res.status_code == 200
        except Exception:
            return False

    def embed_batch(
        self,
        texts: List[str],
        timeout: float | None = None,
    ) -> List[List[float]]:
        """Gửi trực tiếp một danh sách văn bản tới API embedding.

        Vai trò:
            Làm sạch ngắt dòng trong từng đoạn văn, đóng gói payload JSON và gọi
            POST request tới `/embed`. Kiểm tra tính hợp lệ của mảng vector trả về.

        Args:
            texts: Danh sách các chuỗi văn bản cần tính toán embedding.
            timeout: Thời gian chờ tối đa (tùy chọn).

        Returns:
            Danh sách các vector (mỗi vector là một list float 1024 chiều).

        Raises:
            RuntimeError: Nếu HTTP status code khác 200.
            ValueError: Nếu định dạng phản hồi từ service không đúng cấu trúc vector.
        """
        if not texts:
            return []

        cleaned_texts = [t.replace("\n", " ").strip() for t in texts]
        payload = {
            "texts": cleaned_texts,
            "batch_size": len(cleaned_texts),
        }

        response = requests.post(
            self.embed_endpoint,
            json=payload,
            timeout=timeout or self.timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Embedding API error {response.status_code}: {response.text}"
            )

        data = response.json()
        embeddings = data.get("embeddings") or data.get("data")
        if not isinstance(embeddings, list):
            raise ValueError(f"Invalid response from embedding service: {data}")

        return embeddings

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int | None = None,
        dry_run: bool = False,
    ) -> List[List[float]]:
        """Nhúng một danh sách lớn văn bản với cơ chế tự động chia nhỏ lô (sub-batching).

        Vai trò:
            Điều phối việc nhúng toàn bộ kho dữ liệu: Tự động chia `texts` thành các lô nhỏ
            (`batch_size`), gọi tuần tự hoặc chuyển sang chế độ `dry_run` để sinh vector giả lập
            tất định khi kiểm thử offline mà không cần server thực.

        Args:
            texts: Danh sách văn bản cần nhúng.
            batch_size: Kích thước lô tùy biến (mặc định lấy theo self.batch_size).
            dry_run: Cờ bật chế độ chạy giả lập kiểm tra.

        Returns:
            Danh sách toàn bộ các vector embedding tương ứng với từng đoạn văn bản.
        """
        if not texts:
            return []

        if dry_run:
            return [self._mock_vector(t) for t in texts]

        bs = batch_size or self.batch_size
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), bs):
            batch = texts[i : i + bs]
            embeddings = self.embed_batch(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def _mock_vector(self, text: str) -> List[float]:
        """Sinh một vector 1024 chiều tất định và đã chuẩn hóa độ dài L2 dựa trên mã băm SHA-256.

        Vai trò:
            Phục vụ cho các bài kiểm thử đơn vị và dry-run pipeline: Cùng một đoạn text sẽ luôn
            sinh ra cùng một vector giả lập, có chuẩn Euclid bằng 1.0, cho phép kiểm tra khoảng cách
            Cosine và tính hợp lệ của schema Qdrant mà không tốn GPU.

        Args:
            text: Chuỗi văn bản đầu vào.

        Returns:
            Vector 1024 số thực đã chuẩn hóa L2 (chuẩn Cosine = 1.0).
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = []
        for i in range(self.vector_size):
            byte_val = digest[i % len(digest)]
            val = (byte_val / 255.0) * 2.0 - 1.0 + math.sin(i + (byte_val % 7))
            raw.append(val)
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]
