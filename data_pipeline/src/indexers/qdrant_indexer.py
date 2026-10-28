"""Module Nạp và Quản lý Chỉ mục Cơ sở dữ liệu Vector Qdrant (Qdrant Indexer).

Vai trò:
    Chịu trách nhiệm kết nối trực tiếp đến Qdrant Vector Database, tự động khởi tạo collection
    với tham số khoảng cách Cosine (1024 chiều), tạo Keyword Payload Indexes phục vụ lọc hybrid,
    sinh Point ID bất biến qua UUID5(chunk_id), và thực hiện nạp vector hàng loạt (batch upsert)
    có hỗ trợ dry-run và khôi phục nạp tiếp (resumable import).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

INDEX_KEYWORD_FIELDS = ["content_type", "domain", "source", "parent_id"]


class QdrantIndexer:
    """Quản trị viên kết nối và nạp vector vào Qdrant Collection."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        timeout: float = 30.0,
        vector_size: int = 1024,
    ) -> None:
        """Khởi tạo cấu hình kết nối tới cụm Qdrant.

        Vai trò:
            Lưu trữ cấu hình endpoint URL, timeout kết nối và số chiều vector mặc định (1024 cho BGE-M3).

        Args:
            url: Đường dẫn URL tới Qdrant server (ví dụ: `http://localhost:6333`).
            timeout: Thời gian chờ tối đa cho mỗi request mạng (giây).
            vector_size: Số chiều của vector embedding (mặc định 1024).
        """
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.vector_size = vector_size
        self._client: Optional[QdrantClient] = None

    @property
    def client(self) -> QdrantClient:
        """Tạo hoặc tái sử dụng instance QdrantClient kết nối tới server."""
        if self._client is None:
            self._client = QdrantClient(url=self.url, timeout=self.timeout)
        return self._client

    def is_available(self) -> bool:
        """Kiểm tra trạng thái sẵn sàng của Qdrant server.

        Vai trò:
            Gửi yêu cầu ping nhẹ để xác định Qdrant có đang online và phản hồi hay không,
            từ đó quyết định pipeline có thể nạp thật hay chuyển sang chế độ dry-run.

        Returns:
            True nếu server sẵn sàng, False nếu bị từ chối kết nối hoặc timeout.
        """
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def create_collection_if_missing(
        self,
        collection_name: str,
        vector_size: Optional[int] = None,
    ) -> bool:
        """Tự động tạo mới collection trong Qdrant nếu collection chưa tồn tại.

        Vai trò:
            Đảm bảo collection mục tiêu được cấu hình đúng chuẩn: khoảng cách Cosine,
            vector dimension 1024 chiều, và tự động gọi tạo các trường chỉ mục payload.

        Args:
            collection_name: Tên collection (ví dụ: `nmk_chatbot_active`).
            vector_size: Số chiều vector (tùy chọn, mặc định lấy từ self.vector_size).

        Returns:
            True nếu collection mới được tạo, False nếu collection đã tồn tại sẵn.

        Raises:
            Exception: Khi gặp lỗi kết nối hoặc quyền truy cập Qdrant.
        """
        size = vector_size or self.vector_size
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if collection_name in collections:
                logger.info("Qdrant collection '%s' already exists", collection_name)
                return False

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s' (dim=%s, metric=Cosine)", collection_name, size)
            self.ensure_payload_indexes(collection_name)
            return True
        except Exception as exc:
            logger.error("Failed to create collection '%s': %s", collection_name, exc)
            raise

    def ensure_payload_indexes(self, collection_name: str) -> Dict[str, str]:
        """Tạo các Keyword Payload Indexes để tăng tốc độ lọc kết hợp (Hybrid Filtering).

        Vai trò:
            Tạo index riêng biệt trên các trường khóa: `content_type`, `domain`, `source`, `parent_id`.
            Giúp Qdrant thực hiện lọc chính xác cực nhanh (O(1)) trước khi quét HNSW vector,
            đặc biệt quan trọng cho việc lọc an toàn y tế (medical safety filter) của dự án.

        Args:
            collection_name: Tên collection cần tạo index.

        Returns:
            Dictionary ghi nhận trạng thái tạo index cho từng trường ('exists', 'created', 'error:...').
        """
        results = {}
        try:
            collection_info = self.client.get_collection(collection_name)
            existing_fields = set((collection_info.payload_schema or {}).keys())
        except Exception:
            existing_fields = set()

        for field in INDEX_KEYWORD_FIELDS:
            if field in existing_fields:
                results[field] = "exists"
                continue
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                    wait=True,
                )
                results[field] = "created"
            except Exception as exc:
                results[field] = f"error: {exc}"
        return results

    def get_existing_point_ids(self, collection_name: str) -> Set[str]:
        """Cuộn (scroll) toàn bộ ID điểm dữ liệu đã có trong collection để hỗ trợ nạp nối tiếp (resumable).

        Vai trò:
            Lấy danh sách các point ID đã tồn tại trong Qdrant. Nhờ đó pipeline có thể bỏ qua
            các chunk đã nạp trong các lần chạy trước, giảm tối đa thời gian và chi phí embedding.

        Args:
            collection_name: Tên collection cần quét.

        Returns:
            Tập hợp (Set) chứa các chuỗi ID điểm dữ liệu đã có.
        """
        point_ids: Set[str] = set()
        next_offset = None
        while True:
            try:
                page, next_offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=500,
                    offset=next_offset,
                    with_payload=False,
                    with_vectors=False,
                )
                for point in page or []:
                    point_ids.add(str(point.id))
                if next_offset is None or not page:
                    break
            except Exception as exc:
                logger.warning("Could not scroll existing points: %s", exc)
                break
        return point_ids

    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embedder: Any,
        collection_name: str = "nmk_chatbot_active",
        batch_size: int = 50,
        skip_existing: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Tạo vector embedding và nạp batch các chunk vào Qdrant với UUID5 tất định.

        Vai trò:
            Quy trình nạp chính:
            1. Băm `chunk_id` thành UUID5 để đảm bảo tính bất biến (idempotent): nếu chạy lại nhiều lần
               dữ liệu chỉ ghi đè chứ không bị trùng lặp point.
            2. Gọi service embedding BGE-M3 theo batch (`batch_size`).
            3. Đóng gói payload giàu ngữ cảnh: đính kèm cả metadata nguồn, breadcrumbs, và Parent-Child fields.
            4. Thực hiện batch upsert vào Qdrant.
            5. Hỗ trợ chế độ dry-run để kiểm thử cấu trúc payload khi Qdrant/Embedding offline.

        Args:
            chunks: Danh sách các chunk cần nạp.
            embedder: Instance EmbeddingClient để sinh vector.
            collection_name: Tên collection đích.
            batch_size: Kích thước lô xử lý (mặc định 50 chunks/lô).
            skip_existing: Bỏ qua các point ID đã có trong DB.
            dry_run: Nếu True, chỉ giả lập vector và kiểm tra payload, không ghi vào DB.

        Returns:
            Dictionary báo cáo kết quả nạp (status, total_chunks, indexed_points, skipped_points...).
        """
        if not chunks:
            return {"status": "empty", "total_chunks": 0, "indexed_points": 0}

        existing_ids: Set[str] = set()
        if not dry_run and skip_existing and self.is_available():
            existing_ids = self.get_existing_point_ids(collection_name)

        points_to_index: List[Dict[str, Any]] = []
        skipped_count = 0

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
            if point_id in existing_ids:
                skipped_count += 1
                continue
            points_to_index.append(
                {
                    "point_id": point_id,
                    "chunk": chunk,
                    "text": chunk["content"],
                }
            )

        if not points_to_index:
            return {
                "status": "up_to_date",
                "total_chunks": len(chunks),
                "indexed_points": 0,
                "skipped_points": skipped_count,
            }

        logger.info(
            "Indexing %s chunks into '%s' (skipped %s existing)",
            len(points_to_index),
            collection_name,
            skipped_count,
        )

        indexed_count = 0
        total_batches = (len(points_to_index) + batch_size - 1) // batch_size

        for b_idx in range(0, len(points_to_index), batch_size):
            batch_items = points_to_index[b_idx : b_idx + batch_size]
            batch_texts = [item["text"] for item in batch_items]

            # Sinh vector embedding
            embeddings = embedder.embed_texts(batch_texts, dry_run=dry_run)

            # Xây dựng cấu trúc PointStruct
            qdrant_points: List[PointStruct] = []
            for item, vector in zip(batch_items, embeddings):
                chunk = item["chunk"]
                payload = {
                    **chunk["metadata"],
                    "doc_id": chunk["doc_id"],
                    "chunk_id": chunk["chunk_id"],
                    "parent_id": chunk.get("parent_id"),
                    "parent_title": chunk.get("parent_title"),
                    "parent_content": chunk.get("parent_content"),
                    "has_parent": chunk.get("has_parent", False),
                    "title": chunk["title"],
                    "question": chunk["title"],
                    "content": chunk["content"],
                    "text": chunk["content"],
                    "source": chunk["source"],
                    "content_type": chunk["content_type"],
                    "domain": chunk["domain"],
                    "breadcrumb": chunk["breadcrumb"],
                    "content_hash": chunk["content_hash"],
                    "qdrant_point_id": item["point_id"],
                }
                qdrant_points.append(
                    PointStruct(
                        id=item["point_id"],
                        vector=vector,
                        payload=payload,
                    )
                )

            if not dry_run:
                self.client.upsert(
                    collection_name=collection_name,
                    points=qdrant_points,
                    wait=True,
                )
            indexed_count += len(qdrant_points)

        return {
            "status": "ok",
            "dry_run": dry_run,
            "collection_name": collection_name,
            "total_chunks": len(chunks),
            "indexed_points": indexed_count,
            "skipped_points": skipped_count,
            "batch_count": total_batches,
        }
