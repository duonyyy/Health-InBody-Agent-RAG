# Tóm Tắt Đề Tài Tốt Nghiệp

## Xây dựng hệ thống AI phân tích ảnh InBody và tư vấn cải thiện sức khỏe người dùng

Kết quả đo InBody hiện nay thường được cung cấp dưới dạng ảnh hoặc bản in với nhiều mẫu trình bày khác nhau tùy theo thiết bị và cơ sở đo. Các chỉ số sức khỏe quan trọng như BMI, khối lượng cơ, mỡ cơ thể và phân bố cơ thể được thể hiện dưới dạng văn bản, bảng số hoặc biểu đồ hình người, gây khó khăn cho người dùng phổ thông trong việc hiểu và tự đánh giá tình trạng sức khỏe.

Do đó, chúng em đề xuất xây dựng một hệ thống AI có khả năng tự động phân tích ảnh InBody và đưa ra tư vấn cải thiện sức khỏe cho người dùng. Hệ thống sử dụng các kỹ thuật nhận diện ký tự quang học Optical Character Recognition [1] kết hợp với phân tích bố cục tài liệu Document Layout Analysis [2] nhằm trích xuất chính xác các thông số từ nhiều định dạng phiếu kết quả khác nhau, kể cả trong điều kiện ảnh chụp không đồng nhất.

Sau khi dữ liệu được cấu trúc hóa, hệ thống thực hiện quá trình suy luận Inference Process [3] dựa trên mối tương quan giữa các chỉ số thành phần cơ thể như khối lượng cơ xương (SMM), khối lượng mỡ (BFM) và tỷ lệ mỡ nội tạng, từ đó đánh giá tình trạng sức khỏe của người dùng. Bên cạnh đó, hệ thống còn ứng dụng phân tích dự báo Predictive Analytics [4] trên dữ liệu đo theo thời gian để dự đoán xu hướng thay đổi sức khỏe và hỗ trợ đưa ra các khuyến nghị phù hợp.

Ngoài ra, bằng cách tích hợp các mô hình ngôn ngữ lớn Large Language Models [5] được tinh chỉnh với kiến thức y khoa và dinh dưỡng, hệ thống tư vấn định tính mang tính cá nhân hóa, giúp người dùng dễ dàng tiếp cận và ứng dụng vào quá trình cải thiện sức khỏe.

## Mục Tiêu Dự Án

- Xây dựng một hệ thống AI có khả năng đọc chính xác (>85% accuracy) thông tin từ ảnh hoặc PDF báo cáo InBody.
- Phân tích dữ liệu để đánh giá tình trạng cơ thể (ví dụ: thừa cân, thiếu cơ, rủi ro tim mạch dựa trên mỡ nội tạng).
- Đưa ra lời khuyên cá nhân hóa, bao gồm nhận xét, chế độ dinh dưỡng, và phương pháp luyện tập hiệu quả cho 3-6 tháng tới.
- Đảm bảo hệ thống dễ tiếp cận qua web hoặc ứng dụng di động, hỗ trợ tiếng Việt.
- Tích hợp tính năng lưu lịch sử để theo dõi tiến bộ người dùng (cá nhân hóa).

## Phạm Vi

**Input:** Ảnh/PDF báo cáo InBody.

**Output:** Báo cáo phân tích dạng văn bản/PDF, bao gồm:

- Tóm tắt tình trạng (ví dụ: "BMI 25.5 - Thừa cân nhẹ").
- Nhận xét (ví dụ: "Mỡ nội tạng cao, cần giảm để tránh rủi ro sức khỏe").
- Lời khuyên dinh dưỡng (ví dụ: "Giảm 500kcal/ngày, ưu tiên protein").
- Kế hoạch luyện tập (ví dụ: "Cardio 3 buổi/tuần, weight training 2 buổi").
- Không thay thế bác sĩ, lời khuyên chuyên gia.

## Các Công Nghệ Sử Dụng

- Python (thư viện như Tesseract/Paddle OCR cho OCR, OpenCV cho xử lý hình ảnh, ML models từ Hugging Face/Scikit-learn cho phân tích).
- Web app (Flask/Django) hoặc mobile app (Flutter với backend AI), tùy chọn web để dễ triển khai.
- Dữ liệu: InBody để train/test.

## Luồng Chạy Của Dự Án

## Đo InBody Là Gì?

Đo InBody là phương pháp phân tích thành phần cơ thể (Body Composition Analysis - BCA) dùng công nghệ phân tích trở kháng điện sinh học (BIA - Bio-Electrical Impedance Analysis) để đánh giá các thành phần chính trong cơ thể như mỡ, cơ và nước. Máy InBody có thể đo lường chi tiết lượng mỡ, khối lượng cơ xương, tỷ lệ nước nội và ngoại bào, giúp người đo có cái nhìn chính xác về tình trạng sức khỏe tổng thể của mình.
