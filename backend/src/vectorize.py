"""Các thao tác với vector database Qdrant."""
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from configs import DEFAULT_QDRANT_URL, DEFAULT_VECTOR_SIZE

logger = logging.getLogger(__name__)
client = QdrantClient(url=DEFAULT_QDRANT_URL)


def create_collection(name, vector_size=DEFAULT_VECTOR_SIZE):
    """
    Tạo collection mới trong Qdrant để lưu embedding/vector.

    Collection giống như một "bảng" trong vector database. Mỗi vector được lưu
    trong collection này sẽ có cùng kích thước `vector_size` và được so khớp
    bằng cosine similarity để phục vụ tìm kiếm tương đồng trong hệ thống RAG.
    """
    return client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def add_vector(collection_name, vectors=None, batch_size=100):
    """
    Thêm hoặc cập nhật nhiều vector vào một collection.

    Hàm này nhận dữ liệu embedding kèm payload, bổ sung thêm metadata hỗ trợ
    lọc/tìm kiếm, chuyển dữ liệu thành PointStruct của Qdrant rồi upsert theo
    từng batch để tránh gửi quá nhiều điểm trong một request.

    Args:
        collection_name: Tên collection cần ghi dữ liệu.
        vectors: Dict có dạng {id: {"vector": [...], "payload": {...}}}.
        batch_size: Số lượng vector xử lý trong mỗi batch.
    """
    if not vectors:
        return {"status": "no_vectors_provided"}

    # Chuyển dữ liệu đầu vào sang định dạng point mà Qdrant yêu cầu.
    points = [
        PointStruct(
            id=k,
            vector=v["vector"],
            payload={
                **v["payload"],
                # Bổ sung metadata để các bước search có thể filter tốt hơn.
                "doc_length": len(v["payload"].get("content", "")),
                "has_question": bool(v["payload"].get("question", "")),
                "content_type": detect_content_type(v["payload"].get("content", "")),
            },
        )
        for k, v in vectors.items()
    ]

    # Gửi dữ liệu theo batch để giảm tải request và dễ log lỗi từng phần.
    results = []
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
            results.append({"error": str(e)})

    return results


def detect_content_type(content: str) -> str:
    """
    Nhận diện nhóm nội dung sức khỏe/InBody dựa trên từ khóa trong văn bản.

    Giá trị trả về được dùng làm metadata `content_type`, giúp search_vector có
    thể lọc theo nhóm tài liệu như chỉ số InBody, dinh dưỡng, luyện tập hoặc
    cảnh báo an toàn y tế.
    """
    content_lower = content.lower()

    if any(
        keyword in content_lower
        for keyword in [
            "inbody",
            "bmi",
            "smm",
            "bfm",
            "pbf",
            "mỡ nội tạng",
            "khối lượng cơ",
            "khối lượng mỡ",
        ]
    ):
        return "inbody_metric"
    elif any(
        keyword in content_lower
        for keyword in [
            "dinh dưỡng",
            "calo",
            "calorie",
            "protein",
            "carb",
            "chất béo",
            "khẩu phần",
            "ăn uống",
        ]
    ):
        return "nutrition"
    elif any(
        keyword in content_lower
        for keyword in [
            "tập luyện",
            "lịch tập",
            "cardio",
            "kháng lực",
            "tăng cơ",
            "giảm mỡ",
            "phục hồi",
        ]
    ):
        return "exercise"
    elif any(
        keyword in content_lower
        for keyword in [
            "bác sĩ",
            "triệu chứng",
            "bệnh nền",
            "thuốc",
            "chẩn đoán",
            "cấp cứu",
            "an toàn",
        ]
    ):
        return "medical_safety"
    else:
        return "general"


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
        results = client.search(
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
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "status": info.status,
            "optimizer_status": info.optimizer_status,
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


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
