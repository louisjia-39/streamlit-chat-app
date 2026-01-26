import uuid
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="多角色聊天", layout="wide")

CHARACTERS = {
    "小美": "温柔、会关心人、聊天自然",
    "阿哲": "理性、冷静、喜欢分析问题",
    "小周": "活泼、爱开玩笑、反应快",
}

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

conn = st.connection("neon", type="sql")

def load_messages(character):
    q = """
    SELECT role, content
    FROM chat_messages
    WHERE session_id = :sid AND character = :ch
    ORDER BY created_at
    """
    df = conn.query(q, params={
        "sid": st.session_state.session_id,
        "ch": character
    }, ttl=0)
    return df.to_dict("records")

def save_message(character, role, content):
    q = """
    INSERT INTO chat_messages (session_id, character, role, content)
    VALUES (:sid, :ch, :role, :content)
    """
    with conn.session as s:
        s.execute(q, {
            "sid": st.session_state.session_id,
            "ch": character,
            "role": role,
            "content": content
        })
        s.commit()

def get_ai_reply(character, history, user_text):
    if "OPENAI_API_KEY" not in st.secrets:
        return f"（测试模式）{character} 收到了：{user_text}"

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    messages = [{
        "role": "system",
        "content": f"你在扮演{character}，性格是：{CHARACTERS[character]}，请用中文自然聊天。"
    }]

    for m in history[-15:]:
        messages.append(m)

    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages
    )
    return resp.choices[0].message.content

st.sidebar.title("好友列表")
character = st.sidebar.radio("选择角色", list(CHARACTERS.keys()))

st.title(f"正在和「{character}」聊天")

history = load_messages(character)

for msg in history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_text = st.chat_input("输入消息...")
if user_text:
    save_message(character, "user", user_text)
    with st.chat_message("user"):
        st.write(user_text)

    reply = get_ai_reply(character, history, user_text)
    save_message(character, "assistant", reply)

    with st.chat_message("assistant"):
        st.write(reply)

    st.rerun()
