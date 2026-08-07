"""Các thao tác với vector database Qdrant."""
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Range,
    VectorParams,
)

from core.config import (
    DEFAULT_QDRANT_SEARCH_TIMEOUT,
    DEFAULT_QDRANT_TIMEOUT,
    DEFAULT_QDRANT_URL,
    DEFAULT_VECTOR_SIZE,
)
from rag.vector_metadata import (
    PAYLOAD_KEYWORD_INDEX_FIELDS,
    detect_content_type,
    prepare_vector_payload,
)

logger = logging.getLogger(__name__)
client = QdrantClient(
    url=DEFAULT_QDRANT_URL,
    timeout=DEFAULT_QDRANT_TIMEOUT,
)
search_client = QdrantClient(
    url=DEFAULT_QDRANT_URL,
    timeout=DEFAULT_QDRANT_SEARCH_TIMEOUT,
)


def create_collection(name, vector_size=DEFAULT_VECTOR_SIZE):
    """
    Tạo collection mới trong Qdrant để lưu embedding/vector.

    Collection giống như một "bảng" trong vector database. Mỗi vector được lưu
    trong collection này sẽ có cùng kích thước `vector_size` và được so khớp
    bằng cosine similarity để phục vụ tìm kiếm tương đồng trong hệ thống RAG.
    """
    result = client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    ensure_payload_indexes(name, raise_on_error=True)
    return result


def ensure_payload_indexes(collection_name, raise_on_error=False):
    """Ensure fields used by retrieval filters have Qdrant keyword indexes."""
    results = {}
    errors = {}

    try:
        collection_info = client.get_collection(collection_name)
        existing_fields = set((collection_info.payload_schema or {}).keys())
    except Exception as exc:
        if raise_on_error:
            raise RuntimeError(
                f"Could not inspect Qdrant collection {collection_name}: {exc}"
            ) from exc
        logger.warning("Could not inspect collection %s: %s", collection_name, exc)
        existing_fields = set()

    for field_name in PAYLOAD_KEYWORD_INDEX_FIELDS:
        if field_name in existing_fields:
            results[field_name] = "existing"
            continue
        try:
            results[field_name] = client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
        except Exception as exc:
            errors[field_name] = str(exc)
            logger.warning(
                "Could not ensure payload index %s.%s: %s",
                collection_name,
                field_name,
                exc,
            )

    if errors and raise_on_error:
        raise RuntimeError(
            f"Could not create required Qdrant payload indexes: {errors}"
        )

    return {"created_or_existing": results, "errors": errors}


def add_vector(
    collection_name,
    vectors=None,
    batch_size=100,
    raise_on_error=False,
):
    """
    Thêm hoặc cập nhật nhiều vector vào một collection.

    Hàm này nhận dữ liệu embedding kèm payload, bổ sung thêm metadata hỗ trợ
    lọc/tìm kiếm, chuyển dữ liệu thành PointStruct của Qdrant rồi upsert theo
    từng batch để tránh gửi quá nhiều điểm trong một request.

    Args:
        collection_name: Tên collection cần ghi dữ liệu.
        vectors: Dict có dạng {id: {"vector": [...], "payload": {...}}}.
        batch_size: Số lượng vector xử lý trong mỗi batch.
        raise_on_error: Dừng import nếu bất kỳ batch nào ghi thất bại.
    """
    if not vectors:
        return {"status": "no_vectors_provided"}
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    # Chuyển dữ liệu đầu vào sang định dạng point mà Qdrant yêu cầu.
    points = [
        PointStruct(
            id=point_id,
            vector=value["vector"],
            payload=prepare_vector_payload(value["payload"]),
        )
        for point_id, value in vectors.items()
    ]

    # Gửi dữ liệu theo batch để giảm tải request và dễ log lỗi từng phần.
    results = []
    errors = []
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        try:
            result = client.upsert(
                collection_name=collection_name,
                wait=True,
                points=batch,
            )
            results.append(result)
            logger.info(
                f"Processed batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1}"
            )
        except Exception as e:
            logger.error(f"Failed to process batch {i//batch_size + 1}: {e}")
            error = {
                "batch": i // batch_size + 1,
                "point_count": len(batch),
                "error": str(e),
            }
            errors.append(error)
            results.append(error)

    if errors and raise_on_error:
        raise RuntimeError(
            f"Qdrant upsert failed for {len(errors)} batch(es): {errors}"
        )

    return results


def search_vector(collection_name, vector, limit=4, filters=None, score_threshold=0.0):
    """
    Tìm kiếm các tài liệu gần nhất với query vector trong Qdrant.

    Hàm này có vai trò chính trong bước retrieval của RAG: nhận embedding của
    câu hỏi, tìm các vector tương đồng, áp dụng filter nếu có và trả về payload
    tài liệu kèm điểm tương đồng để tầng trả lời sử dụng.

    Args:
        collection_name: Tên collection cần tìm kiếm.
        vector: Query vector/embedding của câu hỏi.
        limit: Số kết quả tối đa.
        filters: Bộ lọc tùy chọn dạng {"field": "value"} hoặc {"field": {"gte": value}}.
        score_threshold: Điểm tương đồng tối thiểu.

    Returns:
        Danh sách tài liệu đã được gắn score và metadata tìm kiếm.
    """
    try:
        # Xây dựng điều kiện filter của Qdrant từ dict filters truyền vào.
        filter_conditions = None
        if filters:
            conditions = []

            for field, value in filters.items():
                if isinstance(value, dict):
                    # Filter theo khoảng giá trị, ví dụ doc_length >= 100.
                    if (
                        "gte" in value
                        or "lte" in value
                        or "gt" in value
                        or "lt" in value
                    ):
                        range_filter = Range()
                        if "gte" in value:
                            range_filter.gte = value["gte"]
                        if "lte" in value:
                            range_filter.lte = value["lte"]
                        if "gt" in value:
                            range_filter.gt = value["gt"]
                        if "lt" in value:
                            range_filter.lt = value["lt"]

                        conditions.append(FieldCondition(key=field, range=range_filter))
                else:
                    # Filter khớp chính xác, ví dụ content_type == "nutrition".
                    conditions.append(
                        FieldCondition(key=field, match=MatchValue(value=value))
                    )

            if conditions:
                filter_conditions = Filter(must=conditions)

        # Thực hiện tìm kiếm vector trong Qdrant.
        results = search_client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=filter_conditions,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,  # Không trả vector gốc để giảm dung lượng response.
        )

        # Chuẩn hóa kết quả để caller nhận payload kèm similarity_score và rank.
        processed_results = []
        for result in results:
            doc = dict(result.payload or {})
            doc["similarity_score"] = result.score
            doc["search_rank"] = len(processed_results) + 1
            processed_results.append(doc)

        logger.info(
            f"Vector search returned {len(processed_results)} results "
            f"(filtered from {len(results)} candidates)"
        )

        return processed_results

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


def search_with_multiple_vectors(collection_name, vectors, limit=4, filters=None):
    """
    Tìm kiếm bằng nhiều query vector và gộp kết quả.

    Dùng cho query expansion hoặc khi một câu hỏi được biểu diễn bằng nhiều
    embedding khác nhau. Hàm gọi search_vector cho từng vector, loại bỏ kết quả
    trùng theo content, rồi sắp xếp lại theo similarity_score tốt nhất.

    Args:
        collection_name: Tên collection cần tìm kiếm.
        vectors: Danh sách query vector.
        limit: Số kết quả tối đa sau khi gộp.
        filters: Bộ lọc tùy chọn truyền xuống search_vector.

    Returns:
        Danh sách kết quả đã gộp, khử trùng lặp và sắp xếp theo score.
    """
    all_results = []
    seen_content_keys = set()

    for i, vector in enumerate(vectors):
        try:
            results = search_vector(collection_name, vector, limit, filters)

            for result in results:
                content_key = result.get("content", "").strip().lower()
                if content_key not in seen_content_keys:
                    seen_content_keys.add(content_key)
                    result["query_vector_index"] = i
                    all_results.append(result)

        except Exception as e:
            logger.error(f"Search with vector {i} failed: {e}")
            continue

    # Ưu tiên các kết quả có điểm tương đồng cao nhất sau khi gộp.
    all_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

    return all_results[:limit]


def get_collection_stats(collection_name):
    """
    Lấy thông tin thống kê/trạng thái của một collection trong Qdrant.

    Hàm này thường dùng để kiểm tra collection đã có bao nhiêu vector/point,
    trạng thái index và optimizer trước hoặc sau khi ingest dữ liệu.
    """
    try:
        info = client.get_collection(collection_name)
        vectors_config = info.config.params.vectors
        return {
            "name": collection_name,
            "vector_size": getattr(vectors_config, "size", None),
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": info.status,
            "optimizer_status": info.optimizer_status,
            "payload_indexes": sorted((info.payload_schema or {}).keys()),
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


def get_collection_point_ids(collection_name, batch_size=1000):
    """Load every point ID from a collection without transferring payload/vector data."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    point_ids = set()
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        point_ids.update(str(point.id) for point in points)
        if next_offset is None:
            break
        offset = next_offset

    return point_ids


def get_alias_target(alias_name):
    """Return the collection currently targeted by an alias, if any."""
    aliases = client.get_aliases()
    for item in aliases.aliases:
        if item.alias_name == alias_name:
            return item.collection_name
    return None


def activate_collection_alias(collection_name, alias_name, expected_points=None):
    """
    Atomically move the stable runtime alias to a verified collection.

    The previous alias target is not deleted, so rollback remains possible.
    """
    if not alias_name or alias_name == collection_name:
        raise ValueError("Alias must be non-empty and differ from collection name")

    physical_collections = {
        item.name for item in client.get_collections().collections
    }
    if alias_name in physical_collections:
        raise ValueError(
            f"Alias {alias_name!r} conflicts with an existing physical collection. "
            "Choose a separate stable alias, for example 'nmk_chatbot_active'."
        )

    info = client.get_collection(collection_name)
    points_count = int(info.points_count or 0)
    if expected_points is not None and points_count != int(expected_points):
        raise ValueError(
            f"Refusing alias switch: expected {expected_points} points, "
            f"collection has {points_count}"
        )

    ensure_payload_indexes(collection_name, raise_on_error=True)

    current_target = get_alias_target(alias_name)
    operations = []
    if current_target:
        operations.append(
            DeleteAliasOperation(
                delete_alias=DeleteAlias(alias_name=alias_name),
            )
        )
    operations.append(
        CreateAliasOperation(
            create_alias=CreateAlias(
                collection_name=collection_name,
                alias_name=alias_name,
            )
        )
    )

    result = client.update_collection_aliases(
        change_aliases_operations=operations,
    )
    logger.info(
        "Activated Qdrant alias %s: %s -> %s",
        alias_name,
        current_target or "none",
        collection_name,
    )
    return {
        "status": bool(result),
        "alias": alias_name,
        "previous_collection": current_target,
        "active_collection": collection_name,
        "points_count": points_count,
    }


def delete_vectors(collection_name, point_ids):
    """
    Xóa các vector khỏi collection theo danh sách point ID.

    Dùng khi cần remove tài liệu cũ, dữ liệu sai hoặc đồng bộ lại index sau khi
    nguồn dữ liệu thay đổi.
    """
    try:
        result = client.delete(
            collection_name=collection_name, points_selector=point_ids, wait=True
        )
        logger.info(f"Deleted {len(point_ids)} vectors from {collection_name}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete vectors: {e}")
        return {"error": str(e)}
