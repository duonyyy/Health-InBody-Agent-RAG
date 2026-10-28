"""Corpus Processor and Quality Gatekeeper Module (Stage 2 / Processing Layer).

Vai trò:
    Lọc bỏ các nguồn dữ liệu nhiễu (công thức nấu ăn, bản ghi tương tác rating người dùng),
    chuẩn hóa chuỗi văn bản về Unicode NFC, loại bỏ ký tự điều khiển ẩn và tích hợp các tài liệu
    hạt giống chuẩn y tế (Medical Seeds) nhằm tạo ra tập corpus chuẩn hóa `embedding_documents.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ALLOWED_CONTENT_TYPES = {
    "nutrition",
    "exercise",
    "inbody_metric",
    "medical_safety",
    "general_health",
}

SKIP_CONTENT_TYPES = {
    "recommender_interaction",
}

SKIP_PIPELINE_ROLES = {
    "recommender_interaction",
    "collaborative_filtering",
    "recommender_catalog",
    "recommender_content_catalog",
    "nutrition_reference_excluded",
    "nutrition_reference_raw",
    "excluded_from_rag",
}

SKIP_SOURCES = {
    "foodrecordfinal_foods",
    "foodrecordfinal_ratings",
    "usda_fooddata_foundation",
}

EMBEDDING_DATASET_NAME = "health_inbody_embedding_v1"

SEED_DOCUMENTS = [
    {
        "doc_id": "internal_inbody_bmi_001",
        "title": "BMI trong báo cáo InBody",
        "content_type": "inbody_metric",
        "source_name": "CDC Adult BMI Categories; WHO Obesity and Overweight",
        "source_url": "https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html; https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "BMI là chỉ số khối cơ thể, được tính bằng cân nặng chia cho bình phương "
            "chiều cao. BMI giúp sàng lọc tình trạng thiếu cân, bình thường, thừa cân "
            "hoặc béo phì, nhưng không phân biệt được khối lượng cơ và khối lượng mỡ. "
            "Khi đọc báo cáo InBody, BMI nên được xem cùng PBF, SMM, BFM và mức mỡ nội tạng."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_001",
        "title": "PBF và phần trăm mỡ cơ thể",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "PBF là phần trăm mỡ cơ thể. PBF cao cho thấy tỷ lệ mỡ trong cơ thể cao, "
            "có thể liên quan đến nguy cơ sức khỏe nếu đi kèm vòng eo lớn, mỡ nội tạng cao "
            "hoặc lối sống ít vận động. PBF cần đánh giá theo giới tính, tuổi, mục tiêu "
            "tập luyện và các chỉ số khác trong báo cáo InBody."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_001",
        "title": "SMM và khối lượng cơ xương",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "SMM là khối lượng cơ xương, phản ánh lượng cơ tham gia vận động và hỗ trợ "
            "trao đổi chất. SMM thấp có thể gợi ý cần tăng tập kháng lực, ăn đủ protein "
            "và ngủ phục hồi tốt hơn. Khi giảm cân, nên cố gắng giữ SMM thay vì chỉ tập "
            "trung giảm cân nặng."
        ),
    },
    {
        "doc_id": "internal_inbody_bfm_001",
        "title": "BFM và khối lượng mỡ cơ thể",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet; CDC BMI limitations",
        "source_url": "https://inbodyusa.com/general/result-sheet/; https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html",
        "content": (
            "BFM là khối lượng mỡ cơ thể tính theo kg. BFM giúp người dùng hiểu rõ cần "
            "giảm bao nhiêu mỡ thay vì chỉ nhìn cân nặng. Khi BFM cao, chiến lược tham "
            "khảo thường là tạo thiếu hụt năng lượng vừa phải, tăng protein, tập kháng lực "
            "và duy trì cardio phù hợp."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_001",
        "title": "Mỡ nội tạng trong báo cáo InBody",
        "content_type": "inbody_metric",
        "source_name": "Cleveland Clinic Visceral Fat",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
        "content": (
            "Mỡ nội tạng là lượng mỡ quanh các cơ quan trong ổ bụng. Mức mỡ nội tạng cao "
            "có thể liên quan đến nguy cơ chuyển hóa và tim mạch. Nếu chỉ số mỡ nội tạng "
            "cao, người dùng nên ưu tiên giảm mỡ bền vững bằng ăn uống cân bằng, vận động "
            "thường xuyên, ngủ đủ và tham khảo bác sĩ nếu có bệnh nền."
        ),
    },
    {
        "doc_id": "internal_nutrition_fat_loss_001",
        "title": "Nguyên tắc dinh dưỡng khi giảm mỡ",
        "content_type": "nutrition",
        "source_name": "WHO obesity prevention; Cleveland Clinic visceral fat care",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight; https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
        "content": (
            "Giảm mỡ nên bắt đầu bằng thiếu hụt năng lượng vừa phải, thường khoảng "
            "300-500 kcal mỗi ngày tùy thể trạng và mức vận động. Nên ưu tiên protein "
            "đủ, rau củ, nguồn tinh bột phức hợp, chất béo tốt và hạn chế đồ uống có đường. "
            "Không nên nhịn ăn cực đoan hoặc giảm cân quá nhanh."
        ),
    },
    {
        "doc_id": "internal_nutrition_muscle_gain_001",
        "title": "Nguyên tắc dinh dưỡng khi tăng cơ",
        "content_type": "nutrition",
        "source_name": "Sports nutrition principles",
        "source_url": "internal_curated",
        "content": (
            "Tăng cơ cần tập kháng lực đều đặn, ăn đủ năng lượng và đủ protein. Người tập "
            "nên phân bổ protein trong ngày, kết hợp tinh bột để có năng lượng tập luyện, "
            "và theo dõi cân nặng, số đo, sức mạnh để điều chỉnh khẩu phần."
        ),
    },
    {
        "doc_id": "internal_exercise_beginner_001",
        "title": "Tập luyện cơ bản cho người mới",
        "content_type": "exercise",
        "source_name": "WHO physical activity and obesity prevention principles",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "Người mới nên bắt đầu với 2-3 buổi tập kháng lực mỗi tuần, mỗi buổi gồm các "
            "động tác đẩy, kéo, squat/hinge và core ở cường độ vừa phải. Cardio có thể "
            "thực hiện 2-3 buổi mỗi tuần. Tăng khối lượng tập từ từ và ưu tiên kỹ thuật đúng."
        ),
    },
    {
        "doc_id": "internal_medical_safety_001",
        "title": "Giới hạn tư vấn y tế của chatbot",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Hệ thống chỉ hỗ trợ thông tin tham khảo về sức khỏe, InBody, dinh dưỡng và "
            "tập luyện. Hệ thống không chẩn đoán bệnh, không kê đơn thuốc và không thay thế "
            "bác sĩ. Nếu người dùng có đau ngực, khó thở, ngất, đau đầu dữ dội, triệu chứng "
            "bất thường, bệnh nền phức tạp, đang mang thai hoặc đang dùng thuốc, nên gặp "
            "chuyên gia y tế."
        ),
    },
    {
        "doc_id": "internal_inbody_bmi_limitations_001",
        "title": "Giới hạn của BMI khi đọc báo cáo InBody",
        "content_type": "inbody_metric",
        "source_name": "CDC Adult BMI Categories; WHO Obesity and Overweight",
        "source_url": "https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html; https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "BMI là công cụ sàng lọc nhanh, không phải chẩn đoán cá nhân. BMI không tách "
            "được khối lượng cơ, mỡ, xương và nước, nên người tập kháng lực có nhiều cơ "
            "có thể có BMI cao nhưng PBF không cao. Khi đọc InBody, nên kết hợp BMI với "
            "PBF, SMM, BFM, vòng eo, mỡ nội tạng, tiền sử bệnh và mục tiêu của người dùng."
        ),
    },
    {
        "doc_id": "internal_inbody_bmi_asian_cutoff_001",
        "title": "BMI và ngưỡng nguy cơ ở người Châu Á",
        "content_type": "inbody_metric",
        "source_name": "WHO BMI public health action points for Asian populations",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "content": (
            "Một số quần thể châu Á có nguy cơ chuyển hóa ở BMI thấp hơn ngưỡng quốc tế. "
            "Trong tư vấn tiếng Việt, BMI từ 23 đến dưới 25 có thể được xem là vùng cần "
            "cảnh báo sớm, nhất là khi PBF, vòng eo hoặc mỡ nội tạng cũng cao. Nên trình bày "
            "đây là ngưỡng tham khảo, không dùng riêng BMI để kết luận bệnh."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_interpretation_001",
        "title": "Cách đọc PBF trong InBody",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet; body composition literature",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "PBF cho biết tỉ lệ khối lượng mỡ trên tổng cân nặng. Hai người có cùng cân "
            "nặng và BMI có thể có PBF rất khác nhau nếu một người có nhiều cơ hơn. PBF "
            "nên được đọc cùng SMM, BFM, giới tính, tuổi, mục tiêu tập luyện và tiền sử sức "
            "khỏe. PBF cao thường ưu tiên giảm mỡ bền vững, không nên ăn kiêng cực đoan."
        ),
    },
    {
        "doc_id": "internal_inbody_pbf_vs_bfm_001",
        "title": "PBF khác BFM như thế nào",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "PBF là phần trăm mỡ cơ thể, còn BFM là khối lượng mỡ tính bằng kg. PBF giúp "
            "so sánh tỉ lệ mỡ giữa những người có cân nặng khác nhau, trong khi BFM giúp "
            "ước tính mức mỡ cần giảm hoặc theo dõi thay đổi theo thời gian. Khi giảm mỡ, "
            "PBF và BFM nên giảm từ từ trong khi SMM được duy trì càng tốt càng tốt."
        ),
    },
    {
        "doc_id": "internal_inbody_bfm_fat_loss_tracking_001",
        "title": "Dùng BFM để theo dõi giảm mỡ",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "BFM phù hợp để theo dõi tiến trình giảm mỡ vì nó biểu diễn khối lượng mỡ bằng "
            "kg. Nếu cân nặng giảm nhưng BFM không giảm, người dùng có thể đang mất nước "
            "hoặc mất cơ. Nếu BFM giảm và SMM giữ ổn định, chiến lược giảm mỡ có khả năng "
            "đang đi đúng hướng. Nên so sánh các lần đo trong điều kiện đo tương tự."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_interpretation_001",
        "title": "Cách đọc SMM và khối lượng cơ xương",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "SMM phản ánh khối lượng cơ xương, là phần cơ quan trọng cho vận động, sức "
            "mạnh và tiêu hao năng lượng. SMM thấp so với cân nặng hoặc giảm nhanh trong "
            "quá trình ăn kiêng là tín hiệu cần tăng protein, tập kháng lực và cải thiện "
            "phục hồi. SMM không nên đọc tách rời khỏi cân nặng, PBF và mức hoạt động."
        ),
    },
    {
        "doc_id": "internal_inbody_smm_gain_strategy_001",
        "title": "Chiến lược tăng hoặc bảo toàn SMM",
        "content_type": "exercise",
        "source_name": "Sports nutrition and resistance training principles",
        "source_url": "internal_curated",
        "content": (
            "Để tăng hoặc bảo toàn SMM, nên tập kháng lực 2-4 buổi mỗi tuần với các động "
            "tác lớn như squat, hinge, đẩy, kéo và core. Tăng khối lượng tập từ từ, ăn đủ "
            "protein, ngủ đủ và tránh thiếu hụt calo quá lớn. Khi đang giảm mỡ, mục tiêu "
            "thực tế là giảm BFM/PBF trong khi SMM giảm ít nhất có thể."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_risk_001",
        "title": "Ý nghĩa sức khỏe của mỡ nội tạng",
        "content_type": "inbody_metric",
        "source_name": "Cleveland Clinic Visceral Fat",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat",
        "content": (
            "Mỡ nội tạng nằm sâu trong ổ bụng và bao quanh nhiều cơ quan nội tạng. Có một "
            "lượng mỡ nội tạng là bình thường, nhưng quá nhiều có thể liên quan đến nguy "
            "cơ tim mạch, tiểu đường, rối loạn lipid máu và các vấn đề chuyển hóa. Chỉ số "
            "mỡ nội tạng cao nên được ưu tiên trong mục tiêu giảm mỡ an toàn."
        ),
    },
    {
        "doc_id": "internal_inbody_visceral_fat_action_001",
        "title": "Nên làm gì khi mỡ nội tạng cao",
        "content_type": "inbody_metric",
        "source_name": "Cleveland Clinic Visceral Fat; Mayo Clinic belly fat guidance",
        "source_url": "https://my.clevelandclinic.org/health/diseases/24147-visceral-fat; https://www.mayoclinic.org/healthy-lifestyle/womens-health/in-depth/belly-fat/art-20045809",
        "content": (
            "Khi mỡ nội tạng cao, chiến lược nên tập trung vào thói quen bền vững: ăn nhiều "
            "thực phẩm ít chế biến, đủ protein và chất xơ, giảm đồ uống có đường và rượu, "
            "tập cardio kết hợp kháng lực, ngủ đủ và quản lý stress. Nếu có bệnh nền tim "
            "mạch, huyết áp, tiểu đường hoặc triệu chứng bất thường, nên gặp bác sĩ."
        ),
    },
    {
        "doc_id": "internal_inbody_bia_preparation_001",
        "title": "Điều kiện đo InBody và BIA để kết quả ổn định",
        "content_type": "inbody_metric",
        "source_name": "InBody Result Sheet FAQ; BIA measurement principles",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "InBody dùng phân tích trở kháng điện sinh học, nên kết quả có thể bị ảnh hưởng "
            "bởi nước trong cơ thể, bữa ăn, tập luyện, nhiệt độ, tư thế, trang phục và tiếp "
            "xúc điện cực. Để so sánh tiến trình, nên đo cùng thời điểm trong ngày, tránh "
            "tập nặng ngay trước khi đo, đi vệ sinh trước khi đo và giữ điều kiện lặp lại."
        ),
    },
    {
        "doc_id": "internal_inbody_bia_limitations_001",
        "title": "Giới hạn của phương pháp BIA",
        "content_type": "inbody_metric",
        "source_name": "BIA body composition literature; InBody educational material",
        "source_url": "https://inbodyusa.com/general/result-sheet/",
        "content": (
            "BIA là phương pháp tiện lợi để ước tính thành phần cơ thể, nhưng không phải "
            "chuẩn vàng như DXA, MRI hoặc các mô hình đa thành phần. Kết quả một lần đo "
            "không nên được xem là chẩn đoán. Giá trị lớn nhất của BIA trong ứng dụng cá "
            "nhân là theo dõi xu hướng qua nhiều lần đo trong điều kiện nhất quán."
        ),
    },
    {
        "doc_id": "internal_inbody_recomposition_001",
        "title": "Tái cấu trúc cơ thể: giảm mỡ và giữ cơ",
        "content_type": "general_health",
        "source_name": "Project curated body recomposition guidance",
        "source_url": "internal_curated",
        "content": (
            "Tái cấu trúc cơ thể là quá trình giảm BFM/PBF trong khi giữ hoặc tăng SMM. "
            "Người mới tập, người có PBF cao hoặc người quay lại tập sau thời gian nghỉ "
            "có thể thay đổi cả hai hướng cùng lúc. Nên ưu tiên thiếu hụt calo nhẹ, đủ "
            "protein, tập kháng lực đều và theo dõi xu hướng mỗi 2-4 tuần."
        ),
    },
    {
        "doc_id": "internal_safety_red_flags_exercise_001",
        "title": "Dấu hiệu cần dừng tập và tìm hỗ trợ y tế",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Nếu người dùng có đau ngực, khó thở bất thường, ngất, choáng váng, đau đầu dữ "
            "dội, yếu liệt, đau khớp sắc nhọn, chảy máu, hoặc triệu chứng xấu đi khi tập, "
            "hệ thống phải khuyên dừng tập và liên hệ cơ sở y tế. Chatbot không được khẳng "
            "định chẩn đoán hay đưa phác đồ điều trị."
        ),
    },
    {
        "doc_id": "internal_safety_chronic_conditions_001",
        "title": "Tư vấn thận trọng khi có bệnh nền",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Với người có tiểu đường, tăng huyết áp, bệnh tim mạch, bệnh thận, đang mang "
            "thai, người cao tuổi, tiền sử chấn thương hoặc đang dùng thuốc, khuyến nghị "
            "dinh dưỡng và tập luyện cần thận trọng. Hệ thống chỉ nên đưa thông tin tham "
            "khảo, tránh mục tiêu cực đoan và khuyên hỏi bác sĩ/chuyên gia trước khi đổi "
            "chế độ mạnh."
        ),
    },
    {
        "doc_id": "internal_safety_no_extreme_diet_001",
        "title": "Không khuyến nghị ăn kiêng cực đoan",
        "content_type": "medical_safety",
        "source_name": "Project medical safety policy",
        "source_url": "internal_curated",
        "content": (
            "Hệ thống không nên khuyên nhịn ăn cực đoan, cắt calo quá thấp, bỏ cả nhóm "
            "chất dinh dưỡng nếu không có chỉ định y tế, dùng thuốc giảm cân trái phép "
            "hoặc tập quá sức để giảm mỡ nhanh. Khuyến nghị an toàn là thay đổi từ từ, "
            "đủ protein, đủ rau chất xơ, đủ nước, ngủ phục hồi và theo dõi triệu chứng."
        ),
    },
]


def load_jsonl(path: Path):
    """Đọc và giải mã từng dòng tệp JSONL thành đối tượng từ điển.

    Vai trò:
        Cung cấp generator đọc file JSON Lines tuần tự nhằm tiết kiệm bộ nhớ RAM
        khi xử lý tập dữ liệu lớn trong bước lọc corpus.

    Args:
        path: Đường dẫn tới file JSONL.

    Yields:
        Đối tượng dict từ mỗi dòng JSON hợp lệ.
    """
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc


def normalize_document(record: dict[str, Any]) -> dict[str, Any] | None:
    """Lọc và chuẩn hóa tài liệu theo tiêu chí của RAG Corpus.

    Vai trò:
        Áp dụng các cổng kiểm soát chất lượng (Quality Gate): loại bỏ công thức nấu ăn
        nhiễu (recipes), tương tác ratings, bản ghi chờ PDF; chuẩn hóa Unicode NFC và
        chỉ giữ lại các tài liệu có độ dài văn bản đạt chuẩn (>= 40 ký tự).

    Args:
        record: Bản ghi thô từ file all_raw_sources.jsonl.

    Returns:
        Dict tài liệu đã chuẩn hóa hoặc None nếu tài liệu bị loại bỏ.
    """
    content_type = record.get("content_type")
    metadata = dict(record.get("metadata") or {})

    if content_type in SKIP_CONTENT_TYPES:
        return None
    if content_type not in ALLOWED_CONTENT_TYPES:
        return None
    if metadata.get("requires_text_extraction"):
        return None
    if metadata.get("pipeline_role") in SKIP_PIPELINE_ROLES:
        return None
    if str(record.get("source") or "") in SKIP_SOURCES:
        return None

    content = str(record.get("content") or "").strip()
    content = unicodedata.normalize("NFC", content)
    content = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", content)
    if len(content) < 40:
        return None

    title = str(record.get("title") or record.get("question") or "Untitled").strip()
    title = unicodedata.normalize("NFC", title)
    title = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", title)

    return {
        "doc_id": str(record.get("doc_id") or record.get("id")),
        "title": title,
        "content": content,
        "source": str(record.get("source") or "processed_dataset"),
        "content_type": content_type,
        "domain": str(record.get("domain") or "health_inbody"),
        "language": str(record.get("language") or "vi"),
        "metadata": {
            **metadata,
            "embedding_dataset": EMBEDDING_DATASET_NAME,
        },
    }


def seed_document(record: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa tài liệu hạt giống (seed document) tri thức cốt lõi.

    Vai trò:
        Đóng gói các tài liệu tri thức chuẩn mực về InBody và an toàn y tế (medical safety)
        với độ tin cậy cao nhất (tier guideline, review_status approved).

    Args:
        record: Bản ghi hạt giống định nghĩa trước trong SEED_DOCUMENTS.

    Returns:
        Dict tài liệu hạt giống đã chuẩn hóa metadata.
    """
    content = unicodedata.normalize("NFC", record["content"])
    content = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", content)
    title = unicodedata.normalize("NFC", record["title"])
    title = re.sub(r"[\u200B-\u200D\uFEFF\u200E\u200F]", "", title)

    return {
        "doc_id": record["doc_id"],
        "title": title,
        "content": content,
        "source": "internal_seed",
        "content_type": record["content_type"],
        "domain": "health_inbody",
        "language": "vi",
        "metadata": {
            "embedding_dataset": EMBEDDING_DATASET_NAME,
            "review_status": "approved",
            "medical_disclaimer_required": record["content_type"] == "medical_safety",
            "source_name": record.get("source_name", "Health/InBody Clinical Team"),
            "source_url": record.get("source_url", "https://inbodyusa.com/general/result-sheet/"),
            "publisher": record.get("source_name", "Health/InBody Clinical Team"),
            "source_tier": "guideline",
            "published_at": "2024-01-01T00:00:00Z",
            "reviewed_at": "2026-01-15T00:00:00Z",
            "medical_review_status": "approved",
        },
    }


def prepare_dataset(input_path: Path, output_path: Path, report_path: Path) -> None:
    """Tạo tập tài liệu RAG chuẩn hóa và lưu báo cáo kết quả lọc.

    Vai trò:
        Kết hợp bộ tài liệu hạt giống (seed documents) và các tài liệu hợp lệ từ
        nguồn thô, xuất ra file `embedding_documents.jsonl` sẵn sàng cho quá trình chunking.

    Args:
        input_path: Đường dẫn tệp all_raw_sources.jsonl.
        output_path: Đường dẫn tệp embedding_documents.jsonl đầu ra.
        report_path: Đường dẫn tệp lưu báo cáo thống kê embedding_report.json.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    skipped = 0
    written = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for seed in SEED_DOCUMENTS:
            document = seed_document(seed)
            output_file.write(json.dumps(document, ensure_ascii=False) + "\n")
            written += 1
            counts[document["content_type"]] = counts.get(document["content_type"], 0) + 1

        for record in load_jsonl(input_path):
            document = normalize_document(record)
            if document is None:
                skipped += 1
                continue
            output_file.write(json.dumps(document, ensure_ascii=False) + "\n")
            written += 1
            counts[document["content_type"]] = counts.get(document["content_type"], 0) + 1

    report = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "total_documents": written,
        "skipped_records": skipped,
        "counts_by_content_type": counts,
        "ready_for_endpoint": "/documents/index",
        "collection_name": "nmk_chatbot_collection",
        "embedding_dataset": EMBEDDING_DATASET_NAME,
        "notes": [
            "Ratings were excluded because they are recommender interactions, not RAG documents.",
            "PDF placeholders without extracted text were excluded from the RAG corpus.",
            "Internal seed documents were added for InBody metrics, nutrition, exercise, and medical safety.",
        ],
    }
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    """Phân tích tham số dòng lệnh CLI cho kịch bản chuẩn bị dataset.

    Vai trò:
        Hỗ trợ người dùng chỉ định đường dẫn tệp nguồn, tệp đích và báo cáo khi chạy riêng lẻ.

    Returns:
        Đối tượng argparse.Namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--input",
        type=Path,
        default=default_root / "dataset" / "processed" / "all_raw_sources.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_root / "dataset" / "processed" / "embedding_documents.jsonl",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=default_root / "dataset" / "processed" / "embedding_report.json",
    )
    return parser.parse_args()


def main() -> None:
    """Điểm vào thực thi CLI chính của script corpus_processor.

    Vai trò:
        Phân tích tham số và thực thi hàm prepare_dataset.
    """
    args = parse_args()
    prepare_dataset(args.input, args.output, args.report)
    print(f"Wrote embedding dataset: {args.output}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
