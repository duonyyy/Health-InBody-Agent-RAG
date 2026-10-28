"""Prompt asks for transcription only; it never asks for health advice."""

INBODY_OCR_PROMPT = """Đọc đúng các chỉ số trên phiếu InBody trong ảnh. Chỉ trả về một JSON object.
Không suy đoán giá trị bị che/mờ, không tính lại chỉ số, không tư vấn sức khỏe.
Mỗi trường có dạng {"value": số hoặc null, "raw_text": chuỗi ký tự nhìn thấy trên ảnh}.
Nếu không đọc được, đặt value=null và raw_text="". Giữ nguyên dấu thập phân trong raw_text.
Các trường: height_cm (cm), weight_kg (kg), smm_kg (kg), bfm_kg (kg),
pbf_percent (%), visceral_fat_level (level), body_water_l (L).
Không lấy cân nặng mục tiêu thay cho cân nặng hiện tại.
"""
