"""Comprehensive unit regression tests for check_medical_safety precision and recall.

Verifies:
1. Urgent medical emergencies (heart attack, chest pain, seizure, coma, stroke, hemorrhage)
   are ALWAYS classified as 'urgent', never degraded to 'low'.
2. Common fitness and lifestyle phrases (HIIT 'ngắt quãng', stuffy nose 'ngạt mũi', 'thuộc nhóm',
   'tài liệu', 'liệu tôi có thể...') are NOT falsely flagged as urgent or caution.
3. Chronic conditions, prescriptions, and medical caution queries remain properly classified.
"""

import pytest
from health.tools import check_medical_safety


@pytest.mark.parametrize(
    "query",
    [
        "Tôi đang tập thì bị tức ngực dữ dội",
        "Bị ép tim và đau tim khi chạy bộ",
        "Người nhà tôi đang co giật và hôn mê",
        "Tập tạ xong bị nôn ra máu",
        "Bác tôi bị tai biến méo miệng",
        "Toi bi dau nguc va kho tho",
        "Toi bi bat tinh",
        "Toi bi ngat di sau khi chay bo",
        "Tôi bị choáng và lơ mơ sau khi tập",
        "Đang tập gym thì thấy thắt ngực khó thở",
        "Bị ho ra máu khi tập thể lực",
    ],
)
def test_urgent_life_threatening_queries_classified_urgent(query):
    result = check_medical_safety(query)
    assert result["risk_level"] == "urgent"
    assert "cấp cứu" in result["recommended_action"]


@pytest.mark.parametrize(
    "query",
    [
        "Chi so BMI nay thuoc nhom nao?",
        "Chỉ số BMI này thuộc nhóm nào?",
        "Cho toi xin tai lieu ve dinh duong",
        "Cho tôi xin tài liệu về dinh dưỡng",
        "Toi bi ngat mui khi troi lanh",
        "Tôi bị ngạt mũi khi trời lạnh",
        "Tap luyen ngat quang co tot khong?",
        "Tập luyện ngắt quãng có tốt không?",
        "Lieu toi co the giam 2kg trong 1 thang?",
        "Liệu tôi có thể giảm 2kg trong 1 tháng?",
        "Tính BMI 72 kg, cao 170 cm",
        "Chế độ ăn ngắt quãng Intermittent Fasting",
    ],
)
def test_common_fitness_queries_not_falsely_flagged(query):
    result = check_medical_safety(query)
    assert result["risk_level"] == "low"
    assert "tham khảo" in result["recommended_action"]


@pytest.mark.parametrize(
    "query",
    [
        "Tôi đau khớp kéo dài, nên tập thế nào?",
        "Tôi đang dùng thuốc huyết áp",
        "Toi bi tieu duong thi an the nao?",
        "Toi uong thuoc tay hang ngay",
        "Uong qua lieu co sao khong?",
        "Toi co benh nen tim mach",
        "Bác sĩ chẩn đoán tôi bị thoái hóa khớp",
    ],
)
def test_chronic_and_prescription_queries_classified_caution(query):
    result = check_medical_safety(query)
    assert result["risk_level"] == "medical_caution"
    assert "bác sĩ" in result["recommended_action"] or "chuyên gia" in result["recommended_action"]


def test_medical_safety_filters_out_recipes_strictly():
    from rag.search import _matches_filters, is_recipe_document

    clean_medical_doc = {
        "doc_id": "med-01",
        "content_type": "medical_safety",
        "title": "Cảnh báo hạ đường huyết",
        "content": "Bệnh nhân tiểu đường cần đo đường huyết trước khi vận động thể lực.",
    }
    recipe_polluted_doc = {
        "doc_id": "rec-01",
        "content_type": "medical_safety",
        "title": "Công thức nấu súp cho người bệnh",
        "content": "Nguyên liệu: 2 muỗng canh hạt nêm, hầm 45 phút rồi dùng nóng.",
    }
    tagged_recipe_doc = {
        "doc_id": "rec-02",
        "content_type": "medical_safety",
        "is_recipe": True,
        "content": "Món ăn hỗ trợ sức khỏe.",
    }

    assert is_recipe_document(clean_medical_doc) is False
    assert is_recipe_document(recipe_polluted_doc) is True
    assert is_recipe_document(tagged_recipe_doc) is True

    filters = {"content_type": "medical_safety"}
    assert _matches_filters(clean_medical_doc, filters) is True
    assert _matches_filters(recipe_polluted_doc, filters) is False
    assert _matches_filters(tagged_recipe_doc, filters) is False
