# Chuyển ý tưởng Day16 AgentArena vào harness Health/InBody

**Trạng thái:** source-ready, chưa deploy. **Nguồn tham khảo:**
`C:\Users\Admin\Desktop\KLTN\VinAI\Track_Shared_Competitions\Day16-AgentArena-Student-main`.

Đã đối chiếu `harness/middleware.py`, năm lớp `layers/`, `arena/model.py`,
`arena/trace.py` và agent loop. Chỉ chuyển các ranh giới có tác dụng trong graph
hiện tại: admission/sanitization trước prompt, citation sau admission, critic
cho mâu thuẫn/claim/cảnh báo, nhận diện quan sát degraded và budget có reserve.
Các lớp mới ở `backend/src/harness/layers/` được gọi thật từ `agents/graph.py`.

Không mang ReAct/submit-call, trace chứa raw nội dung, bộ chấm/trường hợp thi,
hay citation đối chiếu một dòng nguyên văn. Một heuristic overlap có thể bỏ sót
diễn giải sai hoặc từ chối diễn giải đúng; không được xem là kiểm định y khoa.
Các marker tấn công chỉ chặn các mẫu đã biết, không phải phòng vệ đầy đủ.

Kiểm tra: `backend/tests/unit/test_agent_harness_guards.py` có ca mixed chunk,
khối chỉ thị không đóng, kết quả tool bị cắt dù `ok=True`, và reserve composer.
Lệnh `python -B -m pytest backend/tests/unit backend/tests/integration/test_api_fast_paths.py -q -p no:cacheprovider`
đạt **82 passed, 2 warnings** trên source hiện tại. Lượt đầu trong sandbox
gặp `WinError 5` do thư mục tạm pytest, sau đó chạy lại với quyền truy cập
thư mục tạm và đạt; không phải lỗi logic của harness. Chưa chạy HTTP runtime
sau deploy; corpus chưa được chuyên gia y khoa duyệt.
