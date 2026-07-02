import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://chatbot-api:8000").rstrip("/")
BOT_ID = os.getenv("BOT_ID", "health-inbody-agent")
USER_ID = os.getenv("USER_ID", "demo-user")


st.title("Health/InBody Chatbot")
st.caption("Legacy Streamlit interface. Use chat_interface_new.py for the full UI.")


def send_message(text: str) -> str:
    response = requests.post(
        f"{API_BASE_URL}/chat/complete",
        json={
            "bot_id": BOT_ID,
            "user_id": USER_ID,
            "user_message": text,
            "history": st.session_state.messages[-10:],
            "sync_request": True,
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    result = data.get("response", {})
    if isinstance(result, dict):
        return result.get("content", "")
    return str(result)


if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if prompt := st.chat_input("Hỏi về InBody, BMI, dinh dưỡng hoặc tập luyện"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            answer = send_message(prompt)
            st.markdown(answer)
        except Exception as exc:
            answer = f"Backend chưa trả lời được: {exc}"
            st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
