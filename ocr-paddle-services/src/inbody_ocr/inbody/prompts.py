"""Prompt for structuring InBody measurements from OCR text."""

INBODY_TEXT_EXTRACTION_PROMPT = """\
Dưới đây là văn bản thô đọc được từ phiếu InBody bằng OCR.
Hãy trích xuất đúng các chỉ số đo thực tế của người dùng thành một JSON object duy nhất.
Quy tắc bắt buộc:
1. Chỉ lấy giá trị đo thực tế hiện tại. KHÔNG lấy cân nặng mục tiêu (Target/Ideal Weight), KHÔNG lấy dải chỉ số bình thường (Normal Range).
2. Mỗi trường có dạng: {{"value": số_thực_hoặc_null, "raw_text": "chuỗi_ký_tự_nhìn_thấy"}}
3. Nếu không tìm thấy hoặc bị mờ, đặt value=null và raw_text="".
4. Giữ nguyên số và dấu thập phân trong raw_text đúng như văn bản gốc.
5. Tuyệt đối không suy đoán, không tính toán lại chỉ số, không tư vấn sức khỏe. Chỉ trả về một JSON object, không có markdown phụ hay lời giải thích.

Các trường cần trích xuất:
- height_cm: Chiều cao thực tế (cm)
- weight_kg: Cân nặng thực tế (kg)
- smm_kg: Khối lượng cơ xương (Skeletal Muscle Mass, kg)
- bfm_kg: Khối lượng mỡ cơ thể (Body Fat Mass, kg)
- pbf_percent: Phần trăm mỡ cơ thể (Percent Body Fat, %)
- visceral_fat_level: Mức mỡ nội tạng (Visceral Fat Level, cấp độ)
- body_water_l: Tổng lượng nước cơ thể (Total Body Water, L)

--- VĂN BẢN OCR ---
{ocr_text}
--- HẾT VĂN BẢN ---
"""
