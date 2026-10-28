import datetime
import hashlib
import html
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Health/InBody Agent RAG - Trợ lý Sức khỏe & Thể trạng",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


API_BASE_URL = os.getenv("API_BASE_URL", "http://chatbot-api:8000").rstrip("/")
BOT_ID = os.getenv("BOT_ID", "health-inbody-agent")
DEFAULT_USER_ID = os.getenv("USER_ID", "demo-user")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))
API_AUTH_MODE = os.getenv("API_AUTH_MODE", "production").strip().lower()


st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --hb-font: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        --hb-font-mono: 'JetBrains Mono', monospace;
        --hb-primary: #0f766e;
        --hb-primary-hover: #115e59;
        --hb-primary-light: #14b8a6;
        --hb-primary-soft: #f0fdfa;
        --hb-primary-border: #99f6e4;
        --hb-accent: #2563eb;
        --hb-accent-soft: #eff6ff;
        --hb-accent-border: #bfdbfe;
        --hb-warn: #d97706;
        --hb-warn-soft: #fffbeb;
        --hb-warn-border: #fde68a;
        --hb-danger: #dc2626;
        --hb-danger-soft: #fef2f2;
        --hb-danger-border: #fecaca;
        --hb-success: #16a34a;
        --hb-success-soft: #f0fdf4;
        --hb-success-border: #bbf7d0;
        --hb-bg: #f8fafc;
        --hb-surface: #ffffff;
        --hb-muted: #64748b;
        --hb-text: #0f172a;
        --hb-border: #e2e8f0;
        --hb-radius: 12px;
        --hb-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.05);
        --hb-shadow-md: 0 4px 14px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -1px rgba(15, 23, 42, 0.04);
        --hb-shadow-lg: 0 10px 25px -3px rgba(15, 23, 42, 0.08);
    }

    html, body, [class*="css"], .stApp {
        font-family: var(--hb-font);
        color: var(--hb-text);
        background-color: var(--hb-bg);
    }

    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 1320px;
    }

    /* Header styling */
    .hero-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1.5rem;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 253, 250, 0.75) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid var(--hb-border);
        border-top: 4px solid var(--hb-primary);
        border-radius: 16px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.25rem;
        box-shadow: var(--hb-shadow-md);
    }

    .hero-title-group {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .hero-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6rem;
        color: white;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.25);
        flex-shrink: 0;
    }

    .hero-text h1 {
        font-size: 1.65rem;
        font-weight: 800;
        color: var(--hb-text);
        margin: 0;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }

    .hero-text p {
        font-size: 0.9rem;
        color: var(--hb-muted);
        margin: 0.25rem 0 0 0;
    }

    .hero-status-group {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0.4rem;
        flex-shrink: 0;
    }

    .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: #ffffff;
        border: 1px solid var(--hb-border);
        border-radius: 20px;
        padding: 0.35rem 0.85rem;
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--hb-muted);
        box-shadow: var(--hb-shadow-sm);
    }

    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        position: relative;
    }

    .pulse-dot::after {
        content: '';
        position: absolute;
        top: -3px;
        left: -3px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background-color: rgba(16, 185, 129, 0.4);
        animation: pulse-ring 1.8s cubic-bezier(0.24, 0, 0.38, 1) infinite;
    }

    @keyframes pulse-ring {
        0% { transform: scale(0.5); opacity: 1; }
        100% { transform: scale(2.2); opacity: 0; }
    }

    .model-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.78rem;
        font-family: var(--hb-font-mono);
        color: var(--hb-primary);
        background: var(--hb-primary-soft);
        border: 1px solid var(--hb-primary-border);
        border-radius: 6px;
        padding: 0.2rem 0.55rem;
        font-weight: 500;
    }

    /* Chat Messages styling */
    .stChatMessage {
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.85rem;
        border: 1px solid var(--hb-border);
        transition: box-shadow 0.2s ease;
    }

    .stChatMessage[data-testid="chat-message-assistant"] {
        background: #ffffff;
        border-left: 4px solid var(--hb-primary);
        box-shadow: var(--hb-shadow-sm);
    }

    .stChatMessage[data-testid="chat-message-user"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
    }

    /* Meta Chips Bar */
    .meta-chips-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid #f1f5f9;
    }

    .meta-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 9px;
        border-radius: 12px;
        font-size: 0.76rem;
        font-weight: 600;
        line-height: 1.3;
    }

    .meta-chip-fast {
        background: #eef2ff;
        color: #4338ca;
        border: 1px solid #c7d2fe;
    }

    .meta-chip-latency {
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
        font-family: var(--hb-font-mono);
    }

    .meta-chip-agent {
        background: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
    }

    .meta-chip-pers {
        background: #eff6ff;
        color: #1e40af;
        border: 1px solid #bfdbfe;
    }

    /* Safety Alert Cards */
    .alert-card {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: var(--hb-shadow-sm);
    }

    .alert-urgent {
        background: var(--hb-danger-soft);
        border: 1px solid var(--hb-danger-border);
        border-left: 5px solid var(--hb-danger);
        color: #7f1d1d;
    }

    .alert-caution {
        background: var(--hb-warn-soft);
        border: 1px solid var(--hb-warn-border);
        border-left: 5px solid var(--hb-warn);
        color: #78350f;
    }

    .alert-disclaimer {
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        padding: 0.6rem 0.9rem;
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.85rem;
    }

    /* InBody KPI Cards */
    .kpi-card {
        background: #ffffff;
        border: 1px solid var(--hb-border);
        border-radius: 14px;
        padding: 1rem 1.15rem;
        box-shadow: var(--hb-shadow-sm);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        height: 100%;
        position: relative;
        overflow: hidden;
    }

    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--hb-shadow-md);
    }

    .kpi-card-top-accent {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
    }

    .kpi-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--hb-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.35rem;
    }

    .kpi-val-row {
        display: flex;
        align-items: baseline;
        gap: 0.35rem;
        margin-bottom: 0.45rem;
    }

    .kpi-num {
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--hb-text);
        line-height: 1.1;
    }

    .kpi-unit {
        font-size: 0.88rem;
        color: var(--hb-muted);
        font-weight: 500;
    }

    .kpi-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 0.74rem;
        font-weight: 700;
        line-height: 1.3;
    }

    .kpi-delta {
        font-size: 0.78rem;
        font-weight: 600;
        margin-top: 0.4rem;
    }

    /* Progression Delta Comparison Container */
    .progression-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f0fdfa 100%);
        border: 1px solid var(--hb-primary-border);
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        margin: 1.25rem 0;
        box-shadow: var(--hb-shadow-sm);
    }

    /* Stepper Trace Timeline */
    .stepper-container {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 6px;
    }

    .stepper-row {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 8px 12px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }

    .stepper-num {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: var(--hb-primary);
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
    }

    .stepper-content {
        flex-grow: 1;
    }

    .stepper-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.84rem;
        font-weight: 700;
    }

    .stepper-summary {
        font-size: 0.8rem;
        color: var(--hb-muted);
        margin-top: 2px;
    }

    /* Sidebar Profile Card */
    .sidebar-user-card {
        background: #ffffff;
        border: 1px solid var(--hb-border);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: var(--hb-shadow-sm);
        text-align: center;
    }

    .user-avatar-circle {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        background: linear-gradient(135deg, #0f766e 0%, #2563eb 100%);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0 auto 0.6rem auto;
        box-shadow: 0 4px 10px rgba(15, 118, 110, 0.2);
    }

    /* Custom Streamlit Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 16px;
        color: #475569;
        background-color: transparent;
        transition: all 0.2s ease;
    }

    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: var(--hb-primary) !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
    }

    /* General Panel */
    .info-panel {
        border: 1px solid var(--hb-border);
        border-left: 4px solid var(--hb-primary);
        border-radius: 10px;
        background: var(--hb-surface);
        padding: 0.9rem 1.1rem;
        margin: 0.75rem 0 1rem 0;
        color: var(--hb-text);
        box-shadow: var(--hb-shadow-sm);
    }

    .info-panel.warning-panel {
        border-left-color: var(--hb-warn);
        background: var(--hb-warn-soft);
    }

    .metric-box {
        border: 1px solid var(--hb-border);
        border-radius: 10px;
        background: var(--hb-surface);
        padding: 0.85rem;
        min-height: 86px;
        box-shadow: var(--hb-shadow-sm);
    }

    .metric-box strong {
        display: block;
        color: var(--hb-text);
        font-size: 1.35rem;
        margin-bottom: 0.2rem;
    }

    .metric-box span {
        color: var(--hb-muted);
        font-size: 0.85rem;
    }

    .source-row {
        border: 1px solid var(--hb-border);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.7rem;
        background: var(--hb-surface);
        box-shadow: var(--hb-shadow-sm);
    }

    .source-row small {
        color: var(--hb-muted);
    }

    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.15s ease;
    }

    @media (max-width: 760px) {
        .hero-header {
            flex-direction: column;
            align-items: flex-start;
        }

        .hero-status-group {
            align-items: flex-start;
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
        "conversation_id": None,
        "conversation_owner": DEFAULT_USER_ID,
        "user_id": DEFAULT_USER_ID,
        "last_health": None,
        "last_agent_tools": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.conversation_owner != st.session_state.user_id:
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.session_state.conversation_owner = st.session_state.user_id
        st.session_state.pop("zep_ack", None)


def request_json(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    headers = {}
    if API_AUTH_MODE == "development":
        headers["X-Dev-User-Id"] = str(
            st.session_state.get("user_id", DEFAULT_USER_ID)
        )
    response = requests.request(
        method,
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise requests.RequestException(f"{response.status_code}: {detail}")
    if response.status_code == 204:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise requests.RequestException("Backend returned invalid JSON") from exc


def request_inbody_ocr(uploaded_file) -> Dict[str, Any]:
    """Send one private report through the authenticated backend gateway."""
    headers = {}
    if API_AUTH_MODE == "development":
        headers["X-Dev-User-Id"] = str(st.session_state.get("user_id", DEFAULT_USER_ID))
    with requests.Session() as session:
        session.trust_env = False
        response = session.post(
            f"{API_BASE_URL}/me/inbody-ocr",
            files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
            headers=headers,
            timeout=110,
        )
    if response.status_code >= 400:
        raise requests.RequestException(f"{response.status_code}: {response.json().get('detail', 'Không thể đọc phiếu InBody')}")
    return response.json()


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


def classify_bmi_asian(bmi: Optional[float]) -> Tuple[str, str, str]:
    """Phân loại BMI theo tiêu chuẩn WHO dành cho người châu Á (WPRO).
    Returns (nhãn_tiếng_việt, mã_màu, màu_nền).
    """
    if bmi is None or bmi <= 0:
        return ("Chưa có số đo", "#64748b", "#f1f5f9")
    if bmi < 18.5:
        return ("Thiếu cân", "#2563eb", "#eff6ff")
    elif bmi <= 22.9:
        return ("Chuẩn bình thường", "#16a34a", "#f0fdf4")
    elif bmi <= 24.9:
        return ("Tiền béo phì", "#d97706", "#fffbeb")
    else:
        return ("Béo phì", "#dc2626", "#fef2f2")


def classify_visceral_fat(level: Optional[float]) -> Tuple[str, str, str]:
    """Phân loại cấp độ mỡ nội tạng (Visceral Fat Level)."""
    if level is None or level < 0:
        return ("Chưa có số đo", "#64748b", "#f1f5f9")
    if level <= 9:
        return ("Mức an toàn (1-9)", "#16a34a", "#f0fdf4")
    elif level <= 14:
        return ("Cảnh báo cao (10-14)", "#d97706", "#fffbeb")
    else:
        return ("Nguy cơ tim mạch (≥15)", "#dc2626", "#fef2f2")


def classify_pbf(pbf: Optional[float], sex: str = "male") -> Tuple[str, str, str]:
    """Phân loại phần trăm mỡ cơ thể (PBF) theo giới tính."""
    if pbf is None or pbf <= 0:
        return ("Chưa có số đo", "#64748b", "#f1f5f9")
    is_female = (sex or "").lower() == "female"
    if is_female:
        if pbf < 18.0:
            return ("Mỡ rất thấp", "#2563eb", "#eff6ff")
        elif pbf <= 28.0:
            return ("Lý tưởng (18-28%)", "#16a34a", "#f0fdf4")
        elif pbf <= 32.0:
            return ("Mức trung bình", "#d97706", "#fffbeb")
        else:
            return ("Tỷ lệ mỡ cao", "#dc2626", "#fef2f2")
    else:
        if pbf < 10.0:
            return ("Mỡ rất thấp", "#2563eb", "#eff6ff")
        elif pbf <= 20.0:
            return ("Lý tưởng (10-20%)", "#16a34a", "#f0fdf4")
        elif pbf <= 25.0:
            return ("Mức trung bình", "#d97706", "#fffbeb")
        else:
            return ("Tỷ lệ mỡ cao", "#dc2626", "#fef2f2")


def extract_chat_response(data: Dict[str, Any]) -> Dict[str, Any]:
    def normalized_response(response: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": str(response.get("content") or response.get("answer") or ""),
            "conversation_id": response.get("conversation_id"),
            "memory_proposals": response.get("memory_proposals") or [],
            "memory_status": response.get("memory_status"),
            "status": response.get("status", "ok"),
            "fast_path": response.get("fast_path"),
            "latency_ms": response.get("latency_ms"),
            "agent_trace": response.get("agent_trace") or [],
            "selected_agents": response.get("selected_agents") or [],
            "citations": response.get("citations") or response.get("evidence") or [],
            "evidence_status": response.get("evidence_status") or "not_required",
            "limitations": response.get("limitations") or [],
            "safety_result": response.get("safety_result") or {},
            "personalization_used": response.get("personalization_used") or {},
            "errors": response.get("errors") or [],
        }

    if "response" in data:
        response = data["response"]
        if isinstance(response, dict):
            return normalized_response(response)
        return {
            "content": str(response),
            "status": "ok",
            "fast_path": None,
            "latency_ms": None,
            "agent_trace": [],
            "selected_agents": [],
            "citations": [],
            "evidence_status": "not_required",
            "limitations": [],
            "safety_result": {},
            "personalization_used": {},
            "errors": [],
        }

    if "answer" in data:
        return normalized_response(data)

    task_result = data.get("task_result")
    if isinstance(task_result, dict):
        return normalized_response(task_result)
    if isinstance(task_result, str):
        return {
            "content": task_result,
            "status": "ok",
            "fast_path": None,
            "latency_ms": None,
            "agent_trace": [],
            "selected_agents": [],
            "citations": [],
            "evidence_status": "not_required",
            "limitations": [],
            "safety_result": {},
            "personalization_used": {},
            "errors": [],
        }

    return {
        "content": "",
        "status": "ok",
        "fast_path": None,
        "latency_ms": None,
        "agent_trace": [],
        "selected_agents": [],
        "citations": [],
        "evidence_status": "not_required",
        "limitations": [],
        "safety_result": {},
        "personalization_used": {},
        "errors": [],
    }


def send_chat_message(user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    payload = {
        "bot_id": BOT_ID,
        "user_message": user_message,
        "conversation_id": st.session_state.conversation_id,
        "sync_request": True,
    }
    data = request_json("POST", "/chat/complete", payload, timeout=REQUEST_TIMEOUT)
    chat_response = extract_chat_response(data)
    st.session_state.conversation_id = chat_response.get("conversation_id")
    content = str(chat_response.get("content") or "").strip()
    if not content:
        raise requests.RequestException("Backend trả lời rỗng.")
    chat_response["content"] = content
    return chat_response


def render_safety_banner(safety_result: Dict[str, Any]) -> None:
    if not safety_result:
        return

    risk_level = safety_result.get("risk_level", "low")
    warnings = safety_result.get("warnings") or []
    escaped_warnings = [html.escape(str(w)) for w in warnings]

    if risk_level == "urgent":
        st.markdown(
            f"""
            <div class="alert-card alert-urgent">
                <div style="display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 1.05rem; margin-bottom: 6px;">
                    <span>🚨</span> CẢNH BÁO AN TOÀN Y TẾ KHẨN CẤP
                </div>
                <div style="font-size: 0.92rem; line-height: 1.5;">
                    Triệu chứng bạn vừa đề cập có dấu hiệu nguy hiểm cấp cứu (như đau ngực, khó thở nghiêm trọng, choáng váng).
                    <strong>Hãy ngừng ngay hoạt động thể chất và gọi cấp cứu (115) hoặc đến ngay cơ sở y tế gần nhất!</strong>
                </div>
                {''.join(f'<div style="margin-top: 6px; font-size: 0.85rem;">• {w}</div>' for w in escaped_warnings)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif risk_level == "medical_caution":
        st.markdown(
            f"""
            <div class="alert-card alert-caution">
                <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 0.95rem; margin-bottom: 4px;">
                    <span>⚠️</span> LƯU Ý SỨC KHỎE ĐẶC BIỆT
                </div>
                <div style="font-size: 0.88rem; line-height: 1.45;">
                    Bạn đang có tình trạng sức khỏe hoặc triệu chứng cần cẩn trọng. Vui lòng tham khảo ý kiến bác sĩ chuyên khoa trước khi thay đổi chế độ dinh dưỡng hoặc bài tập cường độ cao.
                </div>
                {''.join(f'<div style="margin-top: 4px; font-size: 0.82rem;">• {w}</div>' for w in escaped_warnings)}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_message_meta_chips(message: Dict[str, Any]) -> None:
    fast_path = message.get("fast_path")
    latency_ms = message.get("latency_ms")
    selected_agents = message.get("selected_agents") or []
    pers = message.get("personalization_used") or {}

    chips_html = []

    if fast_path:
        label = "⚡ Fast-path BMI (<100ms)" if fast_path == "bmi" else f"⚡ Fast-path: {html.escape(str(fast_path))}"
        chips_html.append(f'<span class="meta-chip meta-chip-fast">{label}</span>')

    if latency_ms is not None:
        chips_html.append(f'<span class="meta-chip meta-chip-latency">⏱️ {latency_ms:.0f} ms</span>')

    agent_names_map = {
        "supervisor": "🎯 Supervisor",
        "inbody_agent": "📊 InBody",
        "nutrition_agent": "🥗 Dinh dưỡng",
        "exercise_agent": "🏋️ Tập luyện",
        "rag_agent": "🔍 RAG Corpus",
        "safety_agent": "🛡️ Safety",
    }
    for ag in selected_agents:
        ag_label = agent_names_map.get(ag, f"🤖 {ag}")
        chips_html.append(f'<span class="meta-chip meta-chip-agent">{html.escape(ag_label)}</span>')

    if pers.get("used_in_prompt") or pers.get("measurement_date"):
        meas_d = pers.get("measurement_date", "")[:10]
        label = f"👤 InBody ({meas_d})" if meas_d else "👤 Có áp dụng hồ sơ InBody"
        chips_html.append(f'<span class="meta-chip meta-chip-pers">{html.escape(label)}</span>')

    if chips_html:
        st.markdown(
            f'<div class="meta-chips-bar">{"".join(chips_html)}</div>',
            unsafe_allow_html=True,
        )


def render_agent_trace(trace: List[Dict[str, Any]]) -> None:
    if not trace:
        return
    with st.expander(f"Quy trình xử lý Agent ({len(trace)} bước)", expanded=False):
        stepper_items = []
        for index, item in enumerate(trace, start=1):
            status = html.escape(str(item.get("status", "unknown")))
            agent = html.escape(str(item.get("agent", "Agent")))
            action = html.escape(str(item.get("action", "")))
            summary = html.escape(str(item.get("summary", "")))

            stepper_items.append(
                f"""
                <div class="stepper-row">
                    <div class="stepper-num">{index}</div>
                    <div class="stepper-content">
                        <div class="stepper-header">
                            <span>{agent}</span>
                            <span style="color: #64748b; font-weight: 500;">· {action}</span>
                            <span style="margin-left: auto; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; background: #e2e8f0; color: #475569;">{status}</span>
                        </div>
                        {f'<div class="stepper-summary">{summary}</div>' if summary else ''}
                    </div>
                </div>
                """
            )
        st.markdown(
            f'<div class="stepper-container">{"".join(stepper_items)}</div>',
            unsafe_allow_html=True,
        )


def render_evidence(
    citations: List[Dict[str, Any]],
    evidence_status: str,
    limitations: List[str],
) -> None:
    if evidence_status == "insufficient":
        st.warning("Kho tri thức hiện chưa có đủ bằng chứng trực tiếp cho câu trả lời này.")
    elif evidence_status == "partial":
        st.warning("Nguồn tài liệu hiện có chỉ hỗ trợ một phần câu trả lời.")

    for limitation in limitations:
        st.caption(f"Giới hạn dữ liệu: {html.escape(limitation)}")

    if not citations:
        return

    with st.expander(f"📚 Nguồn tham khảo khoa học ({len(citations)})", expanded=False):
        for item in citations:
            citation_id = html.escape(str(item.get("id", "?")))
            raw_title = item.get("title") or f"Tài liệu {citation_id}"
            title = html.escape(str(raw_title))
            source_url = str(item.get("source_url") or "").strip()
            domain = ""
            if source_url:
                parsed = urlparse(source_url)
                if parsed.scheme in {"http", "https"}:
                    domain = parsed.netloc
                else:
                    source_url = ""

            publisher = html.escape(str(item.get("publisher") or item.get("source") or "Nguồn chuẩn y tế"))
            published_at = html.escape(str(item.get("published_at") or ""))

            st.markdown(f"**[{citation_id}] {title}**")
            meta_parts = [publisher]
            if domain:
                meta_parts.append(domain)
            if published_at:
                meta_parts.append(published_at)
            st.caption(" · ".join(meta_parts))

            excerpt = item.get("excerpt")
            if excerpt:
                st.markdown(
                    f"""
                    <div style="background: #f8fafc; border-left: 3px solid #cbd5e1; padding: 6px 12px; margin: 4px 0 8px 0; font-size: 0.85rem; color: #334155;">
                        "{html.escape(str(excerpt))}"
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if source_url:
                st.markdown(f"[🔗 Xem nguồn gốc]({source_url})")
            st.divider()


def render_kpi_card_html(
    title: str,
    value_str: str,
    unit: str,
    tag_text: str,
    tag_color: str,
    tag_bg: str,
    accent_color: str = "#0f766e",
    delta_text: Optional[str] = None,
    delta_color: Optional[str] = None,
) -> str:
    escaped_title = html.escape(title)
    escaped_val = html.escape(value_str)
    escaped_unit = html.escape(unit)
    escaped_tag = html.escape(tag_text)
    delta_html = ""
    if delta_text:
        d_color = delta_color or "#64748b"
        delta_html = f'<div class="kpi-delta" style="color: {d_color};">{html.escape(delta_text)}</div>'

    return f"""
    <div class="kpi-card">
        <div class="kpi-card-top-accent" style="background: {accent_color};"></div>
        <div class="kpi-label">{escaped_title}</div>
        <div class="kpi-val-row">
            <span class="kpi-num">{escaped_val}</span>
            <span class="kpi-unit">{escaped_unit}</span>
        </div>
        <div>
            <span class="kpi-badge" style="color: {tag_color}; background: {tag_bg}; border: 1px solid {tag_color}40;">
                {escaped_tag}
            </span>
        </div>
        {delta_html}
    </div>
    """


def render_timeline_chart(timeline: List[Dict[str, Any]], sex: str = "male") -> None:
    if len(timeline) < 2:
        return

    sorted_timeline = sorted(timeline, key=lambda x: x.get("measured_at", ""))
    dates = [item.get("measured_at", "")[:10] for item in sorted_timeline]
    weights = [item.get("weight_kg") for item in sorted_timeline]
    bmis = [item.get("bmi") for item in sorted_timeline]
    pbfs = [item.get("pbf_percent") for item in sorted_timeline]
    smms = [item.get("smm_kg") for item in sorted_timeline]
    vfats = [item.get("visceral_fat_level") for item in sorted_timeline]

    st.subheader("📈 Biểu đồ tiến độ & xu hướng thay đổi")
    view_mode = st.radio(
        "Chọn chế độ hiển thị:",
        [
            "📊 Đa chỉ số (Cân nặng & Cơ / Tỷ lệ mỡ & Mỡ nội tạng)",
            "⚖️ Cân nặng & BMI",
            "💪 Cơ xương (SMM) & Tỷ lệ mỡ (PBF)",
            "🩺 Cấp độ Mỡ nội tạng",
        ],
        horizontal=True,
    )

    fig = go.Figure()

    if view_mode.startswith("📊 Đa chỉ số"):
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=weights,
                name="Cân nặng (kg)",
                line=dict(color="#0f766e", width=3, shape="spline"),
                mode="lines+markers",
                marker=dict(size=7),
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=smms,
                name="Cơ xương SMM (kg)",
                line=dict(color="#2563eb", width=2.5, shape="spline"),
                mode="lines+markers",
                marker=dict(size=6),
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=pbfs,
                name="Tỷ lệ mỡ PBF (%)",
                line=dict(color="#d97706", width=2.5, dash="dash", shape="spline"),
                mode="lines+markers",
                marker=dict(size=6),
                yaxis="y2",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=vfats,
                name="Mỡ nội tạng (Level)",
                line=dict(color="#dc2626", width=2, dash="dot", shape="spline"),
                mode="lines+markers",
                marker=dict(size=6),
                yaxis="y2",
            )
        )

        fig.update_layout(
            yaxis=dict(title=dict(text="Cân nặng / Cơ (kg)", font=dict(color="#0f766e")), showgrid=True, gridcolor="#f1f5f9"),
            yaxis2=dict(title=dict(text="Mỡ (%) / Cấp độ", font=dict(color="#d97706")), overlaying="y", side="right", showgrid=False),
        )

    elif view_mode.startswith("⚖️ Cân nặng"):
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=weights,
                name="Cân nặng (kg)",
                line=dict(color="#0f766e", width=3, shape="spline"),
                mode="lines+markers",
                marker=dict(size=8),
                fill="tozeroy",
                fillcolor="rgba(15, 118, 110, 0.08)",
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=bmis,
                name="Chỉ số BMI",
                line=dict(color="#2563eb", width=2.5, dash="dot", shape="spline"),
                mode="lines+markers",
                marker=dict(size=7),
                yaxis="y2",
            )
        )
        fig.update_layout(
            yaxis=dict(title=dict(text="Cân nặng (kg)", font=dict(color="#0f766e")), showgrid=True, gridcolor="#f1f5f9"),
            yaxis2=dict(title=dict(text="BMI (kg/m²)", font=dict(color="#2563eb")), overlaying="y", side="right", showgrid=False),
        )

    elif view_mode.startswith("💪 Cơ xương"):
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=smms,
                name="Khối lượng cơ xương SMM (kg)",
                line=dict(color="#2563eb", width=3, shape="spline"),
                mode="lines+markers",
                marker=dict(size=8),
                yaxis="y1",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=pbfs,
                name="Tỷ lệ mỡ PBF (%)",
                line=dict(color="#d97706", width=2.5, dash="dash", shape="spline"),
                mode="lines+markers",
                marker=dict(size=7),
                yaxis="y2",
            )
        )
        fig.update_layout(
            yaxis=dict(title=dict(text="Cơ xương SMM (kg)", font=dict(color="#2563eb")), showgrid=True, gridcolor="#f1f5f9"),
            yaxis2=dict(title=dict(text="Tỷ lệ mỡ PBF (%)", font=dict(color="#d97706")), overlaying="y", side="right", showgrid=False),
        )

    else:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=vfats,
                name="Mỡ nội tạng (Level)",
                line=dict(color="#dc2626", width=3, shape="spline"),
                mode="lines+markers",
                marker=dict(size=8),
                fill="tozeroy",
                fillcolor="rgba(220, 38, 38, 0.08)",
            )
        )
        fig.add_hline(
            y=9,
            line_dash="dot",
            line_color="#16a34a",
            annotation_text="Ngưỡng an toàn (Level 9)",
            annotation_position="bottom right",
        )
        fig.update_layout(yaxis=dict(title="Cấp độ mỡ nội tạng", showgrid=True, gridcolor="#f1f5f9"))

    fig.update_layout(
        font=dict(family="Plus Jakarta Sans, sans-serif", size=12, color="#334155"),
        plot_bgcolor="rgba(255, 255, 255, 0.95)",
        paper_bgcolor="rgba(255, 255, 255, 0)",
        margin=dict(l=40, r=40, t=30, b=40),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255, 255, 255, 0.8)",
        ),
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def call_tool(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return request_json("POST", path, payload, timeout=30)


def render_json_result(result: Dict[str, Any]) -> None:
    if "error" in result:
        st.error(result["error"])
        return
    st.json(result, expanded=True)


def render_header() -> None:
    is_healthy = False
    status_text = "Backend: Đang kết nối..."
    if st.session_state.last_health:
        status = st.session_state.last_health.get("status", "unknown")
        service = st.session_state.last_health.get("service", "Backend")
        if status in {"ok", "healthy"}:
            is_healthy = True
            status_text = f"{service}: Hoạt động"
        else:
            status_text = f"{service}: {status}"

    pulse_class = "pulse-dot" if is_healthy else ""
    pulse_style = "" if is_healthy else "background-color: #ef4444;"

    st.markdown(
        f"""
        <div class="hero-header">
            <div class="hero-title-group">
                <div class="hero-icon">🩺</div>
                <div class="hero-text">
                    <h1>Health/InBody Agent RAG</h1>
                    <p>Trợ lý AI đa tác tử phân tích InBody, dinh dưỡng & tối ưu thể trạng cá nhân hóa theo chuẩn WHO.</p>
                </div>
            </div>
            <div class="hero-status-group">
                <div class="live-indicator">
                    <span class="{pulse_class}" style="{pulse_style}"></span>
                    <span>{html.escape(status_text)}</span>
                </div>
                <div class="model-badge">🤖 Qwen 2.5 8B · 🔍 BGE-M3</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        user_name = st.session_state.get("user_id", DEFAULT_USER_ID)
        initials = (user_name[:2] if user_name else "US").upper()
        auth_tag = "Chế độ Phát triển" if API_AUTH_MODE == "development" else "Môi trường Bảo mật (Prod)"

        st.markdown(
            f"""
            <div class="sidebar-user-card">
                <div class="user-avatar-circle">{html.escape(initials)}</div>
                <div style="font-weight: 700; font-size: 1.05rem; color: #0f172a;">{html.escape(str(user_name))}</div>
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 2px;">{auth_tag}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("Hệ thống Backend")
        st.caption(f"Endpoint: `{API_BASE_URL}`")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Kiểm tra kết nối", use_container_width=True):
                try:
                    st.session_state.last_health = get_backend_health()
                    st.success("Kết nối tốt!")
                except Exception as exc:
                    st.session_state.last_health = None
                    st.error(f"Lỗi: {exc}")
        with col_btn2:
            if st.button("Tải danh sách tools", use_container_width=True):
                try:
                    st.session_state.last_agent_tools = get_agent_tools()
                    st.success("Đã tải tools")
                except Exception as exc:
                    st.error(f"Lỗi: {exc}")

        if st.session_state.last_agent_tools:
            with st.expander("Các Agent chuyên môn", expanded=False):
                for agent in st.session_state.last_agent_tools.get("agents", []):
                    st.write(f"• **{agent.get('name')}**: {agent.get('responsibility')}")

        st.divider()
        st.subheader("Phiên làm việc")
        if API_AUTH_MODE == "development":
            st.text_input("User ID (phát triển)", key="user_id")
            st.caption("Chỉ dùng thử nghiệm local; production danh tính được xác thực từ auth middleware.")

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Tin nhắn", len(st.session_state.messages))
        with col_b:
            user_count = len([m for m in st.session_state.messages if m["role"] == "user"])
            st.metric("Câu hỏi", user_count)

        if st.button("🗑️ Xóa cuộc trò chuyện", use_container_width=True):
            if st.session_state.conversation_id:
                try:
                    request_json("DELETE", f"/me/conversations/{st.session_state.conversation_id}")
                except requests.RequestException:
                    st.error("Chưa xóa được cuộc trò chuyện trên máy chủ. Vui lòng thử lại.")
                    return
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.rerun()

        if st.session_state.messages:
            export_data = {
                "conversation_id": st.session_state.conversation_id,
                "export_time": datetime.datetime.now().isoformat(),
                "user_id": st.session_state.user_id,
                "messages": st.session_state.messages,
            }
            st.download_button(
                "📥 Xuất dữ liệu JSON",
                data=json.dumps(export_data, ensure_ascii=False, indent=2),
                file_name=f"health_inbody_chat_{st.session_state.conversation_id}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.divider()
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; font-size: 0.8rem; color: #64748b; line-height: 1.45;">
                <strong style="color: #0f172a;">⚕️ Rào cản An toàn Y tế:</strong><br>
                Mọi tư vấn từ AI chỉ mang tính tham khảo khoa học, không thay thế bác sĩ điều trị và không dùng để chẩn đoán hay kê đơn thuốc.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_tab() -> None:
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="info-panel">
                <strong>Chào mừng bạn đến với Health/InBody Agent RAG!</strong><br>
                Bạn có thể trò chuyện tự nhiên về chỉ số InBody (BMI, PBF, SMM, Mỡ nội tạng), chế độ ăn thâm hụt calo, hay lịch tập luyện. Hệ thống sẽ tự động phối hợp các agent chuyên môn và đối chiếu tri thức khoa học để hỗ trợ bạn.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("**Câu hỏi gợi ý để bắt đầu nhanh:**")
        examples = [
            ("📊 Phân tích InBody", "Tôi nặng 72kg, cao 170cm, tỷ lệ mỡ PBF 24%, mỡ nội tạng cấp 8. Đánh giá giúp tôi."),
            ("⚡ Fast-path BMI", "Tính chỉ số BMI cho người nặng 68kg, cao 1m65."),
            ("🥗 Dinh dưỡng giảm mỡ", "Gợi ý nguyên tắc thâm hụt calo và phân bổ protein để giảm mỡ mà không mất cơ."),
            ("🏋️ Lịch tập luyện", "Gợi ý lịch tập kháng lực 3 buổi/tuần cho người mới bắt đầu để giảm mỡ."),
            ("🛡️ Cảnh báo an toàn", "Tôi bị đau ngực và khó thở khi chạy bộ, nên làm gì?"),
            ("🔍 Cơ chế InBody", "Mỡ nội tạng khác gì so với mỡ dưới da và tại sao mỡ nội tạng lại nguy hiểm hơn?"),
        ]

        cols = st.columns(2)
        for index, (label, prompt_text) in enumerate(examples):
            with cols[index % 2]:
                if st.button(f"{label}: \"{prompt_text[:45]}...\"", key=f"ex_{index}", use_container_width=True):
                    st.session_state.pending_prompt = prompt_text
                    st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                render_safety_banner(message.get("safety_result") or {})
                render_message_meta_chips(message)

            st.markdown(message["content"])

            if message["role"] == "assistant":
                render_evidence(
                    message.get("citations") or [],
                    message.get("evidence_status") or "not_required",
                    message.get("limitations") or [],
                )
                render_agent_trace(message.get("agent_trace") or [])

                requires_disclaimer = (message.get("safety_result") or {}).get("requires_disclaimer", True)
                if requires_disclaimer:
                    st.markdown(
                        """
                        <div class="alert-disclaimer">
                            ⚕️ <em>Thông tin chỉ mang tính tham khảo khoa học, không thay thế chẩn đoán hay chỉ định y khoa từ chuyên gia y tế.</em>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            if message.get("timestamp"):
                st.caption(message["timestamp"])

    prompt = st.session_state.pop("pending_prompt", None)
    chat_input = st.chat_input("Hỏi về chỉ số InBody, dinh dưỡng hoặc lịch tập luyện...")
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
            with st.spinner("🤖 Health Agent đang phân tích và tổng hợp..."):
                try:
                    chat_response = send_chat_message(prompt, history_before_turn)
                    answer = chat_response["content"]

                    render_safety_banner(chat_response.get("safety_result") or {})
                    render_message_meta_chips(chat_response)
                    st.markdown(answer)
                    render_evidence(
                        chat_response.get("citations") or [],
                        chat_response.get("evidence_status") or "not_required",
                        chat_response.get("limitations") or [],
                    )
                    render_agent_trace(chat_response.get("agent_trace") or [])

                    assistant_message = {
                        "role": "assistant",
                        "content": answer,
                        "status": chat_response.get("status", "ok"),
                        "fast_path": chat_response.get("fast_path"),
                        "latency_ms": chat_response.get("latency_ms"),
                        "agent_trace": chat_response.get("agent_trace") or [],
                        "selected_agents": chat_response.get("selected_agents") or [],
                        "citations": chat_response.get("citations") or [],
                        "evidence_status": chat_response.get("evidence_status") or "not_required",
                        "limitations": chat_response.get("limitations") or [],
                        "safety_result": chat_response.get("safety_result") or {},
                        "personalization_used": chat_response.get("personalization_used") or {},
                        "timestamp": now_label(),
                    }
                    st.caption(assistant_message["timestamp"])
                    st.session_state.messages.append(assistant_message)
                except Exception as exc:
                    error_text = f"Hệ thống tạm thời không phản hồi được yêu cầu này. Chi tiết: {exc}"
                    st.error(error_text)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": error_text,
                            "timestamp": now_label(),
                        }
                    )


def render_progress_summary_subtab() -> None:
    try:
        summary = request_json("GET", "/me/progress/summary")
    except Exception as exc:
        st.warning(f"Chưa thể tải dữ liệu tiến độ: {exc}. Hãy đảm bảo backend đang hoạt động.")
        return

    current = summary.get("current")
    if not current:
        st.markdown(
            """
            <div class="info-panel warning-panel">
                💡 <strong>Bạn chưa có bản ghi đo InBody nào được xác nhận.</strong><br>
                Vui lòng chuyển qua tab <strong>'Ghi nhận lần đo InBody'</strong> để nhập kết quả đo đầu tiên của bạn.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    profile_data: Dict[str, Any] = {}
    try:
        profile_data = request_json("GET", "/me/profile")
    except Exception:
        pass
    user_sex = profile_data.get("sex_at_birth", "male")

    st.subheader("📋 Kết quả phân tích lần đo gần nhất")
    meas_date = current.get("measured_at", "")[:10]
    st.caption(f"Thời gian đo: **{meas_date}** · Tiêu chuẩn đánh giá: **WHO Dành cho Người Châu Á (WPRO)**")

    c1, c2, c3, c4, c5 = st.columns(5)

    w_val = current.get("weight_kg")
    w_str = f"{w_val:.1f}" if w_val else "N/A"
    with c1:
        st.markdown(
            render_kpi_card_html("Cân nặng", w_str, "kg", "Trọng lượng", "#0f766e", "#f0fdfa", "#0f766e"),
            unsafe_allow_html=True,
        )

    bmi_val = current.get("bmi")
    bmi_str = f"{bmi_val:.1f}" if bmi_val else "N/A"
    bmi_tag, bmi_color, bmi_bg = classify_bmi_asian(bmi_val)
    with c2:
        st.markdown(
            render_kpi_card_html("Chỉ số BMI", bmi_str, "kg/m²", bmi_tag, bmi_color, bmi_bg, bmi_color),
            unsafe_allow_html=True,
        )

    pbf_val = current.get("pbf_percent")
    pbf_str = f"{pbf_val:.1f}" if pbf_val is not None else "N/A"
    pbf_tag, pbf_color, pbf_bg = classify_pbf(pbf_val, sex=user_sex)
    with c3:
        st.markdown(
            render_kpi_card_html("Tỷ lệ mỡ (PBF)", pbf_str, "%", pbf_tag, pbf_color, pbf_bg, pbf_color),
            unsafe_allow_html=True,
        )

    smm_val = current.get("smm_kg")
    smm_str = f"{smm_val:.1f}" if smm_val is not None else "N/A"
    with c4:
        st.markdown(
            render_kpi_card_html("Cơ xương (SMM)", smm_str, "kg", "Khối cơ nạc", "#2563eb", "#eff6ff", "#2563eb"),
            unsafe_allow_html=True,
        )

    vfat_val = current.get("visceral_fat_level")
    vfat_str = f"Level {vfat_val:.0f}" if vfat_val is not None else "N/A"
    vfat_tag, vfat_color, vfat_bg = classify_visceral_fat(vfat_val)
    with c5:
        st.markdown(
            render_kpi_card_html("Mỡ nội tạng", vfat_str, "", vfat_tag, vfat_color, vfat_bg, vfat_color),
            unsafe_allow_html=True,
        )

    previous = summary.get("previous")
    delta = summary.get("delta")
    days_between = summary.get("days_between")

    if previous and delta:
        st.divider()
        prev_date = previous.get("measured_at", "")[:10]
        st.subheader(f"🔄 So sánh thay đổi với lần đo trước (cách {days_between} ngày)")
        st.caption(f"Lần đo trước: **{prev_date}**")

        delta_w = delta.get("weight_kg")
        delta_pbf = delta.get("pbf_percent")
        delta_smm = delta.get("smm_kg")
        delta_vfat = delta.get("visceral_fat_level")

        d1, d2, d3, d4 = st.columns(4)

        with d1:
            st.metric(
                "Thay đổi Cân nặng",
                f"{current.get('weight_kg', 0):.1f} kg",
                delta=f"{delta_w:+.1f} kg" if delta_w is not None else None,
                delta_color="inverse",
            )
        with d2:
            st.metric(
                "Thay đổi Tỷ lệ mỡ (PBF)",
                f"{current.get('pbf_percent', 0):.1f} %" if current.get('pbf_percent') is not None else "N/A",
                delta=f"{delta_pbf:+.1f} %" if delta_pbf is not None else None,
                delta_color="inverse",
            )
        with d3:
            st.metric(
                "Thay đổi Cơ xương (SMM)",
                f"{current.get('smm_kg', 0):.1f} kg" if current.get('smm_kg') is not None else "N/A",
                delta=f"{delta_smm:+.1f} kg" if delta_smm is not None else None,
                delta_color="normal",
            )
        with d4:
            st.metric(
                "Thay đổi Mỡ nội tạng",
                f"Level {current.get('visceral_fat_level', 0):.0f}" if current.get('visceral_fat_level') is not None else "N/A",
                delta=f"{delta_vfat:+.0f}" if delta_vfat is not None else None,
                delta_color="inverse",
            )

        limitations = summary.get("data_quality", {}).get("limitations", [])
        if limitations:
            for lim in limitations:
                st.caption(f"ℹ️ *{html.escape(lim)}*")
        else:
            st.caption("ℹ️ *Chênh lệch delta phản ánh biến thiên số đo giữa hai thời điểm, không suy diễn nguyên nhân y khoa.*")

        st.write("")
        if st.button("💬 Nhờ Health Agent phân tích chuyên sâu sự thay đổi này", use_container_width=True, type="primary"):
            dw_str = f"{delta_w:+.1f} kg" if delta_w is not None else "không đổi"
            dp_str = f"{delta_pbf:+.1f}%" if delta_pbf is not None else "không đổi"
            ds_str = f"{delta_smm:+.1f} kg" if delta_smm is not None else "không đổi"
            prompt_text = (
                f"Dựa vào kết quả đo InBody gần nhất của tôi: Cân nặng {current.get('weight_kg')} kg "
                f"(thay đổi {dw_str}), tỷ lệ mỡ PBF {current.get('pbf_percent')}% (thay đổi {dp_str}), "
                f"khối lượng cơ SMM {current.get('smm_kg')} kg (thay đổi {ds_str}) so với lần đo trước "
                f"cách đây {days_between} ngày. "
                "Hãy phân tích sự thay đổi thể trạng này và tư vấn xem tôi nên điều chỉnh chế độ ăn uống hay bài tập như thế nào?"
            )
            st.session_state.pending_prompt = prompt_text
            st.rerun()

    try:
        timeline_res = request_json("GET", "/me/progress/timeline?limit=30")
        timeline = timeline_res.get("timeline", [])
        if len(timeline) >= 2:
            st.divider()
            render_timeline_chart(timeline, sex=user_sex)
    except Exception as exc:
        logger.warning("Không thể hiển thị biểu đồ timeline: %s", exc)


def render_measurement_log_subtab() -> None:
    st.subheader("📝 Ghi nhận kết quả đo InBody mới")
    st.caption("Nhập các thông số chính xác từ phiếu in kết quả đo InBody của bạn (máy đo InBody 270, 370, 570, 770...).")

    if os.getenv("FEATURE_OCR_UPLOAD", "false").lower() in {"1", "true", "yes", "on"}:
        st.markdown("#### Đọc chỉ số từ ảnh hoặc PDF")
        st.caption("Cần đồng ý xử lý dữ liệu sức khỏe trong Hồ sơ. Kết quả nhận dạng chỉ để điền nháp; hãy đối chiếu từng số với phiếu trước khi lưu.")
        report = st.file_uploader("Chọn phiếu InBody", type=["jpg", "jpeg", "png", "webp", "pdf"], key="inbody_ocr_file")
        report_hash = hashlib.sha256(report.getvalue()).hexdigest() if report is not None else None
        if (st.session_state.get("inbody_ocr_result") is not None
                and (st.session_state.get("inbody_ocr_owner") != st.session_state.get("user_id", DEFAULT_USER_ID)
                     or st.session_state.get("inbody_ocr_file_hash") != report_hash)):
            for key in ("inbody_ocr_result", "inbody_ocr_owner", "inbody_ocr_file_hash", "inbody_ocr_confirmed"):
                st.session_state.pop(key, None)
        if report is not None and st.button("Đọc phiếu InBody", key="read_inbody_report"):
            try:
                for key in ("height_cm", "weight_kg", "smm_kg", "bfm_kg", "pbf_percent", "visceral_fat_level", "body_water_l"):
                    st.session_state.pop(f"ocr_{key}", None)
                st.session_state.pop("inbody_ocr_confirmed", None)
                st.session_state.inbody_ocr_result = request_inbody_ocr(report)
                st.session_state.inbody_ocr_owner = st.session_state.get("user_id", DEFAULT_USER_ID)
                st.session_state.inbody_ocr_file_hash = report_hash
            except (requests.RequestException, ValueError) as exc:
                st.error(f"Không thể đọc phiếu: {exc}")
        result = (st.session_state.get("inbody_ocr_result")
                  if st.session_state.get("inbody_ocr_owner") == st.session_state.get("user_id", DEFAULT_USER_ID)
                  and st.session_state.get("inbody_ocr_file_hash") == report_hash
                  else None)
        if result:
            if not result.get("extracted_fields"):
                st.warning("Không đọc được chỉ số nào từ phiếu. Nếu tiếp tục nhập, dữ liệu sẽ được ghi là nhập tay.")
            for warning in result.get("warnings", []):
                st.warning(warning)
            if result.get("unresolved_fields"):
                st.info("Chỉ số chưa đọc được: " + ", ".join(result["unresolved_fields"]))
            with st.form("confirm_inbody_ocr"):
                fields = {}
                labels = {
                    "height_cm": "Chiều cao (cm)", "weight_kg": "Cân nặng (kg)",
                    "smm_kg": "Cơ xương SMM (kg)", "bfm_kg": "Mỡ cơ thể BFM (kg)",
                    "pbf_percent": "Mỡ cơ thể PBF (%)", "visceral_fat_level": "Mỡ nội tạng (level)",
                    "body_water_l": "Nước cơ thể (L)",
                }
                for key, label in labels.items():
                    extracted = result.get("extracted_fields", {}).get(key) or {}
                    value = extracted.get("value")
                    fields[key] = st.text_input(label, value="" if value is None else str(value), key=f"ocr_{key}")
                    if extracted:
                        st.caption(f"OCR báo đọc được ở trang {extracted.get('page_number')}: {extracted.get('raw_text', '')}")
                measured_date = st.date_input("Ngày đo trên phiếu (giờ Việt Nam)", value=datetime.date.today(), key="ocr_measured_date")
                measured_time = st.time_input("Giờ đo trên phiếu", value=datetime.time(12, 0), key="ocr_measured_time")
                confirmed_ocr = st.checkbox("Tôi đã đối chiếu và sửa các chỉ số theo phiếu gốc", value=False, key="inbody_ocr_confirmed")
                save_ocr = st.form_submit_button("Lưu chỉ số đã xác nhận")
            if save_ocr:
                if not confirmed_ocr:
                    st.error("Bạn cần xác nhận các chỉ số trước khi lưu.")
                else:
                    try:
                        values = {key: float(value.replace(",", ".")) for key, value in fields.items() if value.strip()}
                        payload = {
                            "measured_at": datetime.datetime.combine(
                                measured_date, measured_time,
                                tzinfo=datetime.timezone(datetime.timedelta(hours=7)),
                            ).isoformat(),
                            **values,
                            "source_type": "ocr_confirmed" if result.get("extracted_fields") else "manual_confirmed",
                            "confirmed_by_user": True,
                        }
                        request_json("POST", "/me/measurements", payload)
                        st.session_state.pop("inbody_ocr_result", None)
                        st.session_state.pop("inbody_ocr_owner", None)
                        st.session_state.pop("inbody_ocr_file_hash", None)
                        st.success("Đã lưu chỉ số do bạn xác nhận.")
                        st.rerun()
                    except (ValueError, requests.RequestException) as exc:
                        st.error(f"Không thể lưu chỉ số: {exc}")
        st.divider()

    with st.form("new_measurement_form"):
        col1, col2 = st.columns(2)
        with col1:
            meas_date = st.date_input("Ngày đo", value=datetime.date.today())
            meas_time = st.time_input("Giờ đo", value=datetime.datetime.now().time())
            height = st.number_input("Chiều cao (cm)", min_value=50.0, max_value=250.0, value=170.0, step=0.5)
            weight = st.number_input("Cân nặng (kg)", min_value=20.0, max_value=300.0, value=70.0, step=0.1)

        with col2:
            smm = st.number_input("Khối lượng cơ xương SMM (kg)", min_value=0.0, max_value=150.0, value=30.0, step=0.1)
            bfm = st.number_input("Khối lượng mỡ cơ thể BFM (kg)", min_value=0.0, max_value=150.0, value=18.0, step=0.1)
            pbf = st.number_input("Phần trăm mỡ cơ thể PBF (%)", min_value=0.0, max_value=80.0, value=25.0, step=0.1)
            vfat = st.number_input("Cấp độ mỡ nội tạng (Level 1-30)", min_value=0.0, max_value=30.0, value=8.0, step=1.0)
            water = st.number_input("Nước cơ thể (L, tùy chọn)", min_value=0.0, max_value=150.0, value=0.0, step=0.1)

        confirmed = st.checkbox(
            "Tôi xác nhận đây là kết quả đo chính xác từ thiết bị InBody chuẩn",
            value=True,
            help="Chỉ dữ liệu đã được xác nhận mới được hệ thống sử dụng cho tiến độ và cá nhân hóa tư vấn.",
        )
        submit_meas = st.form_submit_button("Lưu kết quả đo InBody", use_container_width=True, type="primary")

    if submit_meas:
        try:
            dt = datetime.datetime.combine(meas_date, meas_time).astimezone()
            payload: Dict[str, Any] = {
                "measured_at": dt.isoformat(),
                "height_cm": height,
                "weight_kg": weight,
                "smm_kg": smm if smm > 0 else None,
                "bfm_kg": bfm if bfm > 0 else None,
                "pbf_percent": pbf if pbf > 0 else None,
                "visceral_fat_level": vfat if vfat > 0 else None,
                "body_water_l": water if water > 0 else None,
                "source_type": "manual_confirmed" if confirmed else "manual",
                "confirmed_by_user": confirmed,
            }
            request_json("POST", "/me/measurements", payload)
            st.success("✅ Đã lưu kết quả đo InBody thành công!")
            time.sleep(1)
            st.rerun()
        except Exception as exc:
            st.error(f"Lưu kết quả thất bại: {exc}")

    st.divider()
    st.subheader("📜 Danh sách các lần đo gần đây")
    try:
        data = request_json("GET", "/me/measurements?limit=10")
        items = data.get("items", [])
        if not items:
            st.info("Chưa có bản ghi nào.")
        else:
            for item in items:
                m_id = item.get("id")
                m_date = item.get("measured_at", "")[:16].replace("T", " ")
                m_weight = item.get("weight_kg", "N/A")
                m_pbf = item.get("pbf_percent", "N/A")
                m_smm = item.get("smm_kg", "N/A")
                m_vfat = item.get("visceral_fat_level", "N/A")
                is_conf = item.get("confirmed_by_user", False)
                conf_tag = "✅ Đã xác nhận" if is_conf else "⏳ Chưa xác nhận"

                with st.expander(f"📅 {m_date} — {m_weight} kg · PBF: {m_pbf}% · SMM: {m_smm} kg · ({conf_tag})"):
                    st.write(f"- **Cân nặng:** {m_weight} kg | **BMI:** {item.get('bmi', 'N/A')}")
                    st.write(f"- **Cơ xương (SMM):** {m_smm} kg | **Khối lượng mỡ (BFM):** {item.get('bfm_kg', 'N/A')} kg")
                    st.write(f"- **Tỷ lệ mỡ (PBF):** {m_pbf}% | **Mỡ nội tạng:** Level {m_vfat}")
                    if st.button("Xóa lần đo này", key=f"del_meas_{m_id}"):
                        try:
                            request_json("DELETE", f"/me/measurements/{m_id}")
                            st.success("Đã xóa lần đo.")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Xóa thất bại: {exc}")
    except Exception as exc:
        st.warning(f"Không thể tải danh sách lần đo: {exc}")


def render_profile_and_goals_subtab() -> None:
    st.subheader("👤 Hồ sơ sức khỏe cá nhân & Mục tiêu thể trạng")
    st.caption("Dữ liệu giúp Health Agent đưa ra lời khuyên phù hợp và thiết lập rào cản an toàn y tế.")

    current_profile: Dict[str, Any] = {}
    try:
        current_profile = request_json("GET", "/me/profile")
    except Exception as exc:
        st.warning(f"Chưa thể tải hồ sơ: {exc}")

    current_goal: Dict[str, Any] = {}
    try:
        goal_data = request_json("GET", "/me/goals/current")
        current_goal = goal_data.get("goal") or {}
    except Exception:
        pass

    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            display_name = st.text_input("Tên hiển thị", value=current_profile.get("display_name") or "")
            sex_map = {"male": "Nam", "female": "Nữ", "intersex": "Khác", "prefer_not_to_say": "Không muốn tiết lộ"}
            sex_val = current_profile.get("sex_at_birth") or "male"
            sex = st.selectbox(
                "Giới tính sinh học",
                list(sex_map.keys()),
                index=list(sex_map.keys()).index(sex_val) if sex_val in sex_map else 0,
                format_func=lambda x: sex_map[x],
            )
            age_options = ["18_24", "25_34", "35_44", "45_54", "55_64", "65_plus", "under_18"]
            age_val = current_profile.get("age_range") or "25_34"
            age_range = st.selectbox(
                "Nhóm tuổi",
                age_options,
                index=age_options.index(age_val) if age_val in age_options else 1,
            )
            height_cm = st.number_input(
                "Chiều cao (cm)",
                min_value=50.0,
                max_value=250.0,
                value=float(current_profile.get("height_cm") or 170.0),
                step=0.5,
            )

        with col2:
            act_map = {"low": "Ít vận động (văn phòng)", "moderate": "Vận động vừa phải (3-4 buổi/tuần)", "high": "Năng động (5-6 buổi/tuần)", "very_high": "Cường độ cao/Vận động viên"}
            act_val = current_profile.get("activity_level") or "moderate"
            activity = st.selectbox(
                "Mức độ vận động",
                list(act_map.keys()),
                index=list(act_map.keys()).index(act_val) if act_val in act_map else 1,
                format_func=lambda x: act_map[x],
            )
            diet_str = ", ".join(current_profile.get("dietary_preferences") or [])
            diet = st.text_input("Chế độ ăn uống (cách nhau dấu phẩy)", value=diet_str, help="Ví dụ: eat clean, high protein, chay, keto...")
            med_str = ", ".join(current_profile.get("medical_conditions") or [])
            med = st.text_input("Bệnh nền / Cảnh báo y tế (cách nhau dấu phẩy)", value=med_str, help="Ví dụ: huyết áp cao, tiểu đường, hen suyễn...")
            ex_str = ", ".join(current_profile.get("exercise_constraints") or [])
            exercise_constraints = st.text_input("Hạn chế vận động (cách nhau dấu phẩy)", value=ex_str, help="Ví dụ: đau khớp gối, thoái hóa cột sống...")

        st.subheader("🎯 Mục tiêu luyện tập")
        goal_map = {"fat_loss": "Giảm mỡ thừa", "muscle_gain": "Tăng khối cơ", "maintenance": "Duy trì vóc dáng", "fitness": "Tăng cường thể lực"}
        goal_type_val = current_goal.get("goal_type") or "fat_loss"
        goal_type = st.selectbox(
            "Mục tiêu chính",
            list(goal_map.keys()),
            index=list(goal_map.keys()).index(goal_type_val) if goal_type_val in goal_map else 0,
            format_func=lambda x: goal_map[x],
        )
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            target_weight = st.number_input(
                "Cân nặng mục tiêu (kg)",
                min_value=30.0,
                max_value=200.0,
                value=float(current_goal.get("target_weight_kg") or 68.0),
                step=0.5,
            )
        with col_g2:
            training_days = st.slider(
                "Số buổi tập dự kiến mỗi tuần",
                min_value=1,
                max_value=7,
                value=int(current_goal.get("training_days_per_week") or 3),
            )

        st.subheader("🔒 Quyền riêng tư & Cam kết")
        consent_flags = current_profile.get("consent_flags") or {}
        c_health = st.checkbox("Đồng ý cho hệ thống xử lý dữ liệu số đo InBody để phân tích", value=consent_flags.get("health_data_processing", True))
        c_pers = st.checkbox("Đồng ý cho AI cá nhân hóa lời khuyên theo hồ sơ của tôi", value=consent_flags.get("personalization", True))

        submit_profile = st.form_submit_button("Lưu hồ sơ & Mục tiêu", use_container_width=True, type="primary")

    if submit_profile:
        try:
            profile_payload = {
                "display_name": display_name.strip() or None,
                "sex_at_birth": sex,
                "age_range": age_range,
                "height_cm": height_cm,
                "activity_level": activity,
                "dietary_preferences": [d.strip() for d in diet.split(",") if d.strip()],
                "medical_conditions": [m.strip() for m in med.split(",") if m.strip()],
                "exercise_constraints": [e.strip() for e in exercise_constraints.split(",") if e.strip()],
                "consent_flags": {
                    "health_data_processing": c_health,
                    "personalization": c_pers,
                },
            }
            request_json("PUT", "/me/profile", profile_payload)

            goal_payload = {
                "goal_type": goal_type,
                "target_weight_kg": target_weight if target_weight > 30 else None,
                "training_days_per_week": training_days,
                "weekly_activity_level": activity,
            }
            request_json("PUT", "/me/goals/current", goal_payload)

            st.success("✅ Đã cập nhật hồ sơ và mục tiêu thành công!")
            time.sleep(1)
            st.rerun()
        except Exception as exc:
            st.error(f"Cập nhật thất bại: {exc}")


def render_checkin_subtab() -> None:
    st.subheader("📋 Check-in định kỳ hàng tuần")
    st.caption("Theo dõi mức độ tuân thủ, mức năng lượng, chất lượng giấc ngủ và phát hiện sớm các dấu hiệu đau mỏi hoặc chấn thương.")

    with st.form("weekly_checkin_form"):
        adherence = st.slider("Mức độ hoàn thành lịch tập tuần qua (%)", min_value=0, max_value=100, value=80, step=5)
        c1, c2 = st.columns(2)
        with c1:
            energy = st.slider("Mức năng lượng trong tuần (1 = Rất mệt mỏi, 5 = Tràn đầy năng lượng)", min_value=1, max_value=5, value=4)
        with c2:
            sleep = st.slider("Chất lượng giấc ngủ (1 = Kém/mất ngủ, 5 = Ngủ ngon và sâu)", min_value=1, max_value=5, value=4)

        symptoms_text = st.text_input(
            "Triệu chứng bất thường hoặc đau chấn thương (cách nhau dấu phẩy)",
            value="",
            help="Ví dụ: Đau mỏi cơ đùi, hoặc Đau nhói khớp vai khi đẩy tạ...",
        )
        note = st.text_area("Ghi chú về ăn uống, cảm xúc hoặc khó khăn gặp phải", value="")
        submit_checkin = st.form_submit_button("Gửi Check-in tuần", use_container_width=True, type="primary")

    if submit_checkin:
        try:
            now_dt = datetime.datetime.now().astimezone()
            symptom_list = [s.strip() for s in symptoms_text.split(",") if s.strip()]
            payload = {
                "checked_at": now_dt.isoformat(),
                "adherence": adherence,
                "energy_level": energy,
                "sleep_quality": sleep,
                "symptoms": symptom_list,
                "note": note.strip() or None,
            }
            res = request_json("POST", "/me/check-ins", payload)
            safety = res.get("safety_result", {})
            risk = safety.get("risk_level", "low")

            if risk == "urgent":
                st.error("🚨 **CẢNH BÁO AN TOÀN Y TẾ:** Triệu chứng của bạn có dấu hiệu nguy hiểm cấp cứu! Hãy ngừng tập ngay và liên hệ cơ sở y tế gần nhất.")
            elif risk == "medical_caution":
                st.warning("⚠️ **LƯU Ý Y TẾ:** Triệu chứng của bạn cần được theo dõi cẩn trọng. Hãy giảm tải hoặc nghỉ ngơi để tránh chấn thương nặng hơn.")
            else:
                st.success("🎉 Gửi check-in thành công! Bạn đang duy trì phong độ rất tốt.")
            time.sleep(1.5)
            st.rerun()
        except Exception as exc:
            st.error(f"Gửi check-in thất bại: {exc}")

    st.divider()
    st.subheader("📜 Nhật ký check-in gần đây")
    try:
        data = request_json("GET", "/me/check-ins?limit=5")
        items = data.get("items", [])
        if not items:
            st.info("Chưa có lịch sử check-in.")
        else:
            for item in items:
                c_date = item.get("checked_at", "")[:16].replace("T", " ")
                adh = item.get("adherence", "N/A")
                syms = item.get("symptoms", [])
                sym_str = ", ".join(syms) if syms else "Không có triệu chứng đau"
                with st.expander(f"📅 {c_date} — Hoàn thành: {adh}% · Triệu chứng: {sym_str}"):
                    st.write(f"- **Mức năng lượng:** {item.get('energy_level', 'N/A')}/5 | **Giấc ngủ:** {item.get('sleep_quality', 'N/A')}/5")
                    if item.get("note"):
                        st.write(f"- **Ghi chú:** {item.get('note')}")
                    safe_res = item.get("safety_result") or {}
                    if safe_res.get("warnings"):
                        st.warning(f"Cảnh báo: {', '.join(safe_res['warnings'])}")
    except Exception as exc:
        st.warning(f"Không thể tải lịch sử check-in: {exc}")


def render_memory_subtab() -> None:
    st.caption("Chỉ ghi nhớ lâu dài điều bạn xác nhận. Chỉ số InBody và bệnh sử được quản lý trong hồ sơ sức khỏe.")
    try:
        data = request_json("GET", "/me/memory/facts")
    except requests.RequestException:
        st.info("Hãy tạo hồ sơ và đồng ý xử lý dữ liệu/cá nhân hóa để sử dụng bộ nhớ.")
        return
    for fact in data.get("items", []):
        st.write(fact["text"])
        st.caption(f"{'Chờ xác nhận' if fact['status'] == 'pending' else 'Đã xác nhận'} · Hết hạn: {fact['expires_at'][:10]}")
        left, right = st.columns(2)
        try:
            if fact["status"] == "pending" and left.button("Xác nhận ghi nhớ", key=f"confirm_{fact['id']}"):
                request_json("POST", f"/me/memory/facts/{fact['id']}/confirm")
                st.rerun()
            if right.button("Xóa / từ chối", key=f"delete_{fact['id']}"):
                request_json("DELETE", f"/me/memory/facts/{fact['id']}")
                st.rerun()
        except requests.RequestException:
            st.error("Chưa cập nhật được ghi nhớ. Vui lòng thử lại.")
    if not data.get("items"):
        st.info("Chưa có ghi nhớ. Bạn có thể nói trong chat: “Tôi thích câu trả lời ngắn gọn.”")
    st.divider()
    agree = st.checkbox("Tôi đồng ý gửi các ghi nhớ đã xác nhận đến Zep để hỗ trợ nhớ lâu dài.", key="zep_ack")
    try:
        if st.button("Bật bộ nhớ Zep", disabled=not agree):
            request_json("PUT", "/me/memory-consent", {"acknowledged_external_processing": True})
            st.rerun()
        if data.get("external_memory"):
            st.caption("Có thay đổi chờ đồng bộ; dữ liệu đã xóa không còn dùng để trả lời, nhưng bản Zep còn chờ cập nhật."
                       if data.get("sync_pending") else "Bộ nhớ Zep đã được bật.")
            if st.button("Đồng bộ ghi nhớ đã xác nhận"):
                request_json("POST", "/me/memory/sync")
                st.success("Đã đồng bộ các ghi nhớ đã xác nhận.")
        if st.button("Tắt và xóa bộ nhớ trên Zep"):
            request_json("DELETE", "/me/memory")
            st.success("Đã tắt và xóa bộ nhớ ngoài. Ghi nhớ trong hồ sơ vẫn do bạn quản lý riêng.")
    except requests.RequestException:
        st.error("Chưa hoàn tất thao tác với bộ nhớ ngoài. Vui lòng thử lại.")


def render_progress_tab() -> None:
    tab_summary, tab_log, tab_profile, tab_checkin, tab_memory = st.tabs(
        [
            "📊 Tiến độ & So sánh Delta",
            "📝 Ghi nhận lần đo InBody",
            "👤 Hồ sơ & Mục tiêu",
            "📋 Check-in định kỳ",
            "🧠 Ghi nhớ",
        ]
    )

    with tab_summary:
        render_progress_summary_subtab()

    with tab_log:
        render_measurement_log_subtab()

    with tab_profile:
        render_profile_and_goals_subtab()

    with tab_checkin:
        render_checkin_subtab()
    with tab_memory:
        render_memory_subtab()


def render_dev_tools_tab() -> None:
    st.markdown(
        """
        <div class="info-panel warning-panel">
            <strong>Khu vực Kiểm thử Kỹ thuật (Developer Tools)</strong><br>
            Khu vực này dùng để kiểm tra trực tiếp từng endpoint tool của backend. Ở flow người dùng thực tế, Agent Router sẽ tự động phân phối tool thích hợp.
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        with st.form("bmi_form"):
            st.subheader("Tool: BMI Calculator")
            weight = st.number_input("Cân nặng (kg)", min_value=1.0, max_value=300.0, value=70.0, step=0.5)
            height = st.number_input("Chiều cao (cm)", min_value=50.0, max_value=250.0, value=170.0, step=0.5)
            submitted = st.form_submit_button("Kiểm tra tính BMI", use_container_width=True)
            if submitted:
                render_json_result(call_tool("/tools/bmi", {"weight_kg": weight, "height_cm": height}))

        with st.form("pbf_form"):
            st.subheader("Tool: PBF Evaluator")
            pbf = st.number_input("Phần trăm mỡ cơ thể (%)", min_value=0.0, max_value=80.0, value=25.0, step=0.5)
            sex = st.selectbox("Giới tính", ["unknown", "male", "female"], format_func=lambda x: {"unknown": "Chưa rõ", "male": "Nam", "female": "Nữ"}[x])
            submitted = st.form_submit_button("Kiểm tra đánh giá PBF", use_container_width=True)
            if submitted:
                payload: Dict[str, Any] = {"pbf_percent": pbf}
                if sex != "unknown":
                    payload["sex"] = sex
                render_json_result(call_tool("/tools/pbf", payload))

        with st.form("visceral_form"):
            st.subheader("Tool: Visceral Fat")
            level = st.number_input("Visceral fat level", min_value=0.0, max_value=40.0, value=9.0, step=1.0)
            submitted = st.form_submit_button("Kiểm tra mỡ nội tạng", use_container_width=True)
            if submitted:
                render_json_result(call_tool("/tools/visceral-fat", {"visceral_fat_level": level}))

    with right:
        with st.form("nutrition_form"):
            st.subheader("Tool: Nutrition")
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
            submitted = st.form_submit_button("Kiểm tra gợi ý dinh dưỡng", use_container_width=True)
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
            st.subheader("Tool: Workout Planner")
            training_goal = st.selectbox("Mục tiêu tập", ["fat_loss", "muscle_gain", "maintenance"], key="training_goal")
            level = st.selectbox("Trình độ", ["beginner", "intermediate", "advanced"])
            days = st.slider("Số buổi mỗi tuần", min_value=1, max_value=7, value=3)
            submitted = st.form_submit_button("Kiểm tra gợi ý lịch tập", use_container_width=True)
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
            st.subheader("Tool: Clinical Safety Guard")
            question = st.text_area("Triệu chứng thử nghiệm", value="Tôi bị đau ngực khi tập cardio, nên làm gì?")
            conditions_text = st.text_input("Bệnh nền (phân cách dấu phẩy)", value="")
            submitted = st.form_submit_button("Kiểm tra Guardrail an toàn", use_container_width=True)
            if submitted:
                conditions = [item.strip() for item in conditions_text.split(",") if item.strip()]
                render_json_result(call_tool("/tools/safety", {"question": question, "conditions": conditions}))


def render_search_tab() -> None:
    st.markdown(
        """
        <div class="info-panel">
            <strong>Tra cứu tri thức Hybrid Search (Dense Vector + BM25 Sparse)</strong><br>
            Tìm kiếm trực tiếp trên corpus tri thức y tế, InBody và thể hình được index trong Qdrant & BM25 engine.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("search_form"):
        query = st.text_input("Nội dung tra cứu", value="mỡ nội tạng cao nên làm gì")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            limit = st.slider("Số tài liệu tối đa", min_value=1, max_value=20, value=5)
        with col_s2:
            use_rerank = st.checkbox("Sử dụng Reranking nâng cao", value=True)
        submitted = st.form_submit_button("Tìm kiếm tài liệu", use_container_width=True, type="primary")

    if submitted:
        with st.spinner("Đang truy vấn kho tri thức y tế..."):
            try:
                data = request_json(
                    "POST",
                    "/search",
                    {"query": query, "limit": limit, "use_rerank": use_rerank},
                    timeout=60,
                )
                results = data.get("results", [])
                st.write(f"Tìm thấy **{len(results)}** tài liệu phù hợp.")
                for index, item in enumerate(results, start=1):
                    raw_title = item.get("question") or item.get("title") or f"Tài liệu {index}"
                    title = html.escape(str(raw_title))
                    raw_source = item.get("source") or item.get("source_file") or "Kho tri thức"
                    source = html.escape(str(raw_source))
                    score = item.get("relevance_score", item.get("hybrid_score", item.get("score", "")))
                    content = item.get("content") or item.get("page_content") or ""

                    st.markdown(
                        f"""
                        <div class="source-row">
                            <strong style="color: #0f766e; font-size: 0.98rem;">{index}. {title}</strong><br>
                            <small>Nguồn: {source} | Điểm liên quan: {score}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.write(content[:1200] + ("..." if len(content) > 1200 else ""))
            except Exception as exc:
                st.error(f"Lỗi tìm kiếm: {exc}")


def render_system_tab() -> None:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
            <div class="metric-box">
                <strong>{html.escape(BOT_ID)}</strong>
                <span>Bot ID</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-box">
                <strong>{html.escape(str(st.session_state.user_id))}</strong>
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

    st.subheader("Kiểm tra trạng thái dịch vụ (Health Check)")
    if st.button("Làm mới Health Check", use_container_width=True):
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

    # Rule AGENTS.md: Dev tools/System phải ẩn ở production.
    if API_AUTH_MODE == "development":
        chat_tab, progress_tab, search_tab, tools_tab, system_tab = st.tabs(
            [
                "💬 Trò chuyện với Agent",
                "📊 Hồ sơ & Tiến độ InBody",
                "🔍 Tra cứu Tri thức",
                "🛠️ Dev Tool Test",
                "⚙️ Trạng thái Hệ thống",
            ]
        )
        with chat_tab:
            render_chat_tab()
        with progress_tab:
            render_progress_tab()
        with search_tab:
            render_search_tab()
        with tools_tab:
            render_dev_tools_tab()
        with system_tab:
            render_system_tab()
    else:
        chat_tab, progress_tab, search_tab = st.tabs(
            [
                "💬 Trò chuyện với Agent",
                "📊 Hồ sơ & Tiến độ InBody",
                "🔍 Tra cứu Tri thức",
            ]
        )
        with chat_tab:
            render_chat_tab()
        with progress_tab:
            render_progress_tab()
        with search_tab:
            render_search_tab()


if __name__ == "__main__":
    main()
