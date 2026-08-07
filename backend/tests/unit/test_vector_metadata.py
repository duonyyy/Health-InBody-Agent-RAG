from rag.vector_metadata import detect_content_type, prepare_vector_payload


def test_curated_content_type_is_not_overwritten_by_chunk_keywords():
    payload = prepare_vector_payload(
        {
            "content_type": "nutrition",
            "content": "Phi thơm hành tỏi rồi cho thịt vào chảo.",
            "question": "Món ăn phù hợp",
        }
    )

    assert payload["content_type"] == "nutrition"
    assert payload["content_type_source"] == "dataset"
    assert payload["has_question"] is True


def test_unlabelled_payload_uses_health_inbody_heuristic():
    payload = prepare_vector_payload(
        {
            "content": "Mức mỡ nội tạng trên báo cáo InBody là 12.",
            "question": "",
        }
    )

    assert payload["content_type"] == "inbody_metric"
    assert payload["content_type_source"] == "heuristic"
    assert payload["has_question"] is False


def test_generic_fallback_uses_schema_content_type():
    assert detect_content_type("Thông tin sức khỏe tổng quát.") == "general_health"
