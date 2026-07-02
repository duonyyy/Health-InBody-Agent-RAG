import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Health/InBody Agent RAG",
    page_icon="HB",
    layout="wide",
    initial_sidebar_state="expanded",
)


API_BASE_URL = os.getenv("API_BASE_URL", "http://chatbot-api:8000").rstrip("/")
BOT_ID = os.getenv("BOT_ID", "health-inbody-agent")
DEFAULT_USER_ID = os.getenv("USER_ID", "demo-user")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))


st.markdown(
    """
<style>
    :root {
        --hb-primary: #0f766e;
        --hb-primary-soft: #ccfbf1;
        --hb-accent: #2563eb;
        --hb-warn: #b45309;
        --hb-danger: #b91c1c;
        --hb-bg: #f7faf9;
        --hb-surface: #ffffff;
        --hb-muted: #64748b;
        --hb-text: #172033;
        --hb-border: #dbe5e1;
    }

    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1280px;
    }

    .app-title {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        border-bottom: 1px solid var(--hb-border);
        padding-bottom: 1rem;
        margin-bottom: 1rem;
    }

    .app-title h1 {
        color: var(--hb-text);
        font-size: 1.8rem;
        line-height: 1.2;
        margin: 0;
        letter-spacing: 0;
    }

    .app-title p {
        color: var(--hb-muted);
        margin: .35rem 0 0 0;
        max-width: 760px;
    }

    .status-pill {
        border: 1px solid var(--hb-border);
        border-radius: 8px;
        padding: .45rem .7rem;
        color: var(--hb-muted);
        white-space: nowrap;
        background: var(--hb-surface);
        font-size: .9rem;
    }

    .info-panel {
        border: 1px solid var(--hb-border);
        border-left: 4px solid var(--hb-primary);
        border-radius: 8px;
        background: var(--hb-surface);
        padding: .9rem 1rem;
        margin: .75rem 0 1rem 0;
        color: var(--hb-text);
    }

    .warning-panel {
        border-left-color: var(--hb-warn);
        background: #fffbeb;
    }

    .metric-box {
        border: 1px solid var(--hb-border);
        border-radius: 8px;
        background: var(--hb-surface);
        padding: .85rem;
        min-height: 86px;
    }

    .metric-box strong {
        display: block;
        color: var(--hb-text);
        font-size: 1.35rem;
        margin-bottom: .2rem;
    }

    .metric-box span {
        color: var(--hb-muted);
        font-size: .9rem;
    }

    .source-row {
        border: 1px solid var(--hb-border);
        border-radius: 8px;
        padding: .85rem;
        margin-bottom: .7rem;
        background: var(--hb-surface);
    }

    .source-row small {
        color: var(--hb-muted);
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }

    .stChatMessage {
        border-radius: 8px;
        border: 1px solid var(--hb-border);
    }

    .stChatMessage[data-testid="chat-message-assistant"] {
        background: #f8fbfa;
        border-left: 4px solid var(--hb-primary);
    }

    .stChatMessage[data-testid="chat-message-user"] {
        background: #f8fafc;
    }

    @media (max-width: 760px) {
        .app-title {
            flex-direction: column;
        }

        .status-pill {
            white-space: normal;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


def now_label() -> str:
    return datetime.datetime.now().strftime("%H:%M - %d/%m/%Y")


def init_state() -> None:
    defaults = {
        "messages": [],
        "conversation_id": str(int(time.time())),
        "user_id": DEFAULT_USER_ID,
        "last_health": None,
        "last_agent_tools": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def request_json(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    response = requests.request(method, url, json=payload, timeout=timeout)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise requests.RequestException(f"{response.status_code}: {detail}")
    try:
        return response.json()
    except ValueError as exc:
        raise requests.RequestException("Backend returned invalid JSON") from exc


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def get_backend_health() -> Dict[str, Any]:
    return request_json("GET", "/health", timeout=8)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def get_agent_tools() -> Dict[str, Any]:
    return request_json("GET", "/agent/tools", timeout=8)


def build_history() -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    for message in st.session_state.messages[-10:]:
        if message.get("role") in {"user", "assistant"}:
            history.append(
                {
                    "role": message["role"],
                    "content": str(message.get("content", "")),
                }
            )
    return history


def extract_chat_content(data: Dict[str, Any]) -> str:
    if "response" in data:
        response = data["response"]
        if isinstance(response, dict):
            return str(response.get("content") or response.get("answer") or "")
        return str(response)

    if "answer" in data:
        return str(data["answer"])

    task_result = data.get("task_result")
    if isinstance(task_result, dict):
        return str(task_result.get("content") or "")
    if isinstance(task_result, str):
        return task_result

    return ""


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def send_chat_message(user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    payload = {
        "bot_id": BOT_ID,
        "user_id": st.session_state.user_id,
        "user_message": user_message,
        "history": history if history is not None else build_history(),
        "sync_request": True,
    }
    data = request_json("POST", "/chat/complete", payload, timeout=REQUEST_TIMEOUT)
    content = extract_chat_content(data).strip()
    if not content:
        raise requests.RequestException("Backend returned an empty answer")
    return content


def call_tool(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return request_json("POST", path, payload, timeout=30)


def render_json_result(result: Dict[str, Any]) -> None:
    if "error" in result:
        st.error(result["error"])
        return
    st.json(result, expanded=True)


def render_header() -> None:
    status_text = "Backend: not checked"
    if st.session_state.last_health:
        status = st.session_state.last_health.get("status", "unknown")
        service = st.session_state.last_health.get("service", "backend")
        status_text = f"{service}: {status}"

    st.markdown(
        f"""
        <div class="app-title">
            <div>
                <h1>Health/InBody Agent RAG</h1>
                <p>Chatbot giải thích chỉ số InBody, BMI, PBF, mỡ nội tạng, dinh dưỡng và tập luyện ở mức tham khảo.</p>
            </div>
            <div class="status-pill">{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Backend")
        st.caption(API_BASE_URL)

        if st.button("Kiểm tra backend", use_container_width=True):
            try:
                st.session_state.last_health = get_backend_health()
                st.success("Backend đang phản hồi")
            except Exception as exc:
                st.session_state.last_health = None
                st.error(f"Không kết nối được backend: {exc}")

        if st.button("Tải danh sách agent tools", use_container_width=True):
            try:
                st.session_state.last_agent_tools = get_agent_tools()
                st.success("Đã tải tools")
            except Exception as exc:
                st.error(f"Không tải được tools: {exc}")

        if st.session_state.last_agent_tools:
            with st.expander("Agent routes", expanded=False):
                for route in st.session_state.last_agent_tools.get("routes", []):
                    st.write(route)

        st.divider()
        st.subheader("Phiên chat")
        st.text_input("User ID", key="user_id")

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Tin nhắn", len(st.session_state.messages))
        with col_b:
            user_count = len([m for m in st.session_state.messages if m["role"] == "user"])
            st.metric("Câu hỏi", user_count)

        if st.button("Xóa hội thoại", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_id = str(int(time.time()))
            st.rerun()

        if st.session_state.messages:
            export_data = {
                "conversation_id": st.session_state.conversation_id,
                "export_time": datetime.datetime.now().isoformat(),
                "user_id": st.session_state.user_id,
                "messages": st.session_state.messages,
            }
            st.download_button(
                "Xuất JSON",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name=f"health_inbody_chat_{st.session_state.conversation_id}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.divider()
        st.subheader("Lưu ý y tế")
        st.caption(
            "Thông tin chỉ mang tính tham khảo, không thay thế bác sĩ, không dùng để chẩn đoán hoặc kê đơn."
        )


def render_chat_tab() -> None:
    st.markdown(
        """
        <div class="info-panel warning-panel">
            Flow chính của hệ thống là multi-agent chat: bạn nhập câu hỏi tự nhiên, backend tự route và tự gọi tool phù hợp. Backend hiện tại chưa có endpoint upload/parse báo cáo InBody, nên hãy nhập chỉ số bằng văn bản trong chat.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        examples = [
            "BMI và PBF khác nhau như thế nào?",
            "Tôi nặng 72kg, cao 170cm, tính BMI giúp tôi.",
            "PBF của tôi 28%, nam, nên ưu tiên giảm mỡ hay tăng cơ?",
            "Mỡ nội tạng level 12 có đáng lo không?",
            "Gợi ý lịch tập 3 buổi/tuần để giảm mỡ.",
        ]
        st.write("Câu hỏi mẫu:")
        cols = st.columns(2)
        for index, example in enumerate(examples):
            with cols[index % 2]:
                if st.button(example, key=f"example_{index}", use_container_width=True):
                    st.session_state.pending_prompt = example
                    st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("timestamp"):
                st.caption(message["timestamp"])

    prompt = st.session_state.pop("pending_prompt", None)
    chat_input = st.chat_input("Nhập câu hỏi về InBody, dinh dưỡng hoặc tập luyện")
    prompt = prompt or chat_input

    if prompt:
        history_before_turn = build_history()
        user_message = {
            "role": "user",
            "content": prompt,
            "timestamp": now_label(),
        }
        st.session_state.messages.append(user_message)

        with st.chat_message("user"):
            st.markdown(prompt)
            st.caption(user_message["timestamp"])

        with st.chat_message("assistant"):
            with st.spinner("Đang hỏi Health Agent..."):
                try:
                    answer = send_chat_message(prompt, history_before_turn)
                    st.markdown(answer)
                    assistant_message = {
                        "role": "assistant",
                        "content": answer,
                        "timestamp": now_label(),
                    }
                    st.caption(assistant_message["timestamp"])
                    st.session_state.messages.append(assistant_message)
                except Exception as exc:
                    error_text = (
                        "Backend chưa trả lời được yêu cầu này. "
                        f"Chi tiết kỹ thuật: {exc}"
                    )
                    st.error(error_text)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": error_text,
                            "timestamp": now_label(),
                        }
                    )


def render_dev_tools_tab() -> None:
    st.markdown(
        """
        <div class="info-panel warning-panel">
            Khu vực này chỉ để kiểm thử endpoint backend trực tiếp khi dev/debug. Người dùng cuối nên dùng tab Chat để agent tự quyết định cần gọi BMI, PBF, mỡ nội tạng, dinh dưỡng, lịch tập hay safety tool.
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        with st.form("bmi_form"):
            st.subheader("BMI")
            weight = st.number_input("Cân nặng (kg)", min_value=1.0, max_value=300.0, value=70.0, step=0.5)
            height = st.number_input("Chiều cao (cm)", min_value=50.0, max_value=250.0, value=170.0, step=0.5)
            submitted = st.form_submit_button("Tính BMI", use_container_width=True)
            if submitted:
                render_json_result(call_tool("/tools/bmi", {"weight_kg": weight, "height_cm": height}))

        with st.form("pbf_form"):
            st.subheader("PBF")
            pbf = st.number_input("Phần trăm mỡ cơ thể (%)", min_value=0.0, max_value=80.0, value=25.0, step=0.5)
            sex = st.selectbox("Giới tính", ["unknown", "male", "female"], format_func=lambda x: {"unknown": "Chưa rõ", "male": "Nam", "female": "Nữ"}[x])
            submitted = st.form_submit_button("Đánh giá PBF", use_container_width=True)
            if submitted:
                payload: Dict[str, Any] = {"pbf_percent": pbf}
                if sex != "unknown":
                    payload["sex"] = sex
                render_json_result(call_tool("/tools/pbf", payload))

        with st.form("visceral_form"):
            st.subheader("Mỡ nội tạng")
            level = st.number_input("Visceral fat level", min_value=0.0, max_value=40.0, value=9.0, step=1.0)
            submitted = st.form_submit_button("Đánh giá mỡ nội tạng", use_container_width=True)
            if submitted:
                render_json_result(call_tool("/tools/visceral-fat", {"visceral_fat_level": level}))

    with right:
        with st.form("nutrition_form"):
            st.subheader("Dinh dưỡng")
            goal = st.selectbox(
                "Mục tiêu",
                ["fat_loss", "muscle_gain", "maintenance"],
                format_func=lambda x: {
                    "fat_loss": "Giảm mỡ",
                    "muscle_gain": "Tăng cơ",
                    "maintenance": "Duy trì",
                }[x],
            )
            nutrition_weight = st.number_input("Cân nặng hiện tại (kg)", min_value=1.0, max_value=300.0, value=70.0, step=0.5, key="nutrition_weight")
            activity = st.selectbox("Mức vận động", ["low", "moderate", "high"], index=1)
            submitted = st.form_submit_button("Gợi ý dinh dưỡng", use_container_width=True)
            if submitted:
                render_json_result(
                    call_tool(
                        "/tools/nutrition",
                        {
                            "goal": goal,
                            "weight_kg": nutrition_weight,
                            "activity_level": activity,
                        },
                    )
                )

        with st.form("training_form"):
            st.subheader("Lịch tập")
            training_goal = st.selectbox("Mục tiêu tập", ["fat_loss", "muscle_gain", "maintenance"], key="training_goal")
            level = st.selectbox("Trình độ", ["beginner", "intermediate", "advanced"])
            days = st.slider("Số buổi mỗi tuần", min_value=1, max_value=7, value=3)
            submitted = st.form_submit_button("Gợi ý lịch tập", use_container_width=True)
            if submitted:
                render_json_result(
                    call_tool(
                        "/tools/training",
                        {
                            "goal": training_goal,
                            "fitness_level": level,
                            "days_per_week": days,
                        },
                    )
                )

        with st.form("safety_form"):
            st.subheader("Safety guardrail")
            question = st.text_area("Câu hỏi hoặc triệu chứng", value="Tôi bị đau ngực khi tập cardio, nên làm gì?")
            conditions_text = st.text_input("Bệnh nền/hạn chế, phân tách bằng dấu phẩy", value="")
            submitted = st.form_submit_button("Kiểm tra an toàn", use_container_width=True)
            if submitted:
                conditions = [item.strip() for item in conditions_text.split(",") if item.strip()]
                render_json_result(call_tool("/tools/safety", {"question": question, "conditions": conditions}))


def render_search_tab() -> None:
    st.markdown(
        """
        <div class="info-panel">
            Tìm kiếm hybrid trên corpus Health/InBody đã index trong Qdrant/BM25. Nếu kết quả rỗng, cần kiểm tra dữ liệu import, Qdrant và embed_serving.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("search_form"):
        query = st.text_input("Truy vấn", value="mỡ nội tạng cao nên làm gì")
        limit = st.slider("Số kết quả", min_value=1, max_value=20, value=5)
        use_rerank = st.checkbox("Dùng rerank", value=True)
        submitted = st.form_submit_button("Tìm kiếm", use_container_width=True)

    if submitted:
        with st.spinner("Đang tìm trong corpus..."):
            try:
                data = request_json(
                    "POST",
                    "/search",
                    {"query": query, "limit": limit, "use_rerank": use_rerank},
                    timeout=60,
                )
                results = data.get("results", [])
                st.write(f"Tìm thấy {len(results)} kết quả.")
                for index, item in enumerate(results, start=1):
                    title = item.get("question") or item.get("title") or f"Kết quả {index}"
                    source = item.get("source") or item.get("source_file") or "unknown"
                    score = item.get("relevance_score", item.get("hybrid_score", item.get("score", "")))
                    content = item.get("content") or item.get("page_content") or ""
                    st.markdown(
                        f"""
                        <div class="source-row">
                            <strong>{index}. {title}</strong><br>
                            <small>Nguồn: {source} | Điểm: {score}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.write(content[:1200] + ("..." if len(content) > 1200 else ""))
            except Exception as exc:
                st.error(f"Không tìm kiếm được: {exc}")


def render_system_tab() -> None:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
            <div class="metric-box">
                <strong>{BOT_ID}</strong>
                <span>Bot ID</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-box">
                <strong>{st.session_state.user_id}</strong>
                <span>User ID</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="metric-box">
                <strong>{len(st.session_state.messages)}</strong>
                <span>Tin nhắn trong phiên</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Health check")
    if st.button("Làm mới health check", use_container_width=True):
        try:
            st.session_state.last_health = get_backend_health()
        except Exception as exc:
            st.error(f"Health check lỗi: {exc}")

    if st.session_state.last_health:
        st.json(st.session_state.last_health, expanded=True)
    else:
        st.info("Chưa có dữ liệu health check.")


def main() -> None:
    init_state()
    render_header()
    render_sidebar()

    chat_tab, tools_tab, search_tab, system_tab = st.tabs(
        ["Chat", "Dev tool test", "Search", "System"]
    )
    with chat_tab:
        render_chat_tab()
    with tools_tab:
        render_dev_tools_tab()
    with search_tab:
        render_search_tab()
    with system_tab:
        render_system_tab()


if __name__ == "__main__":
    main()
