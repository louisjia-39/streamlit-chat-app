import uuid
import time
import hmac
import hashlib
from datetime import datetime, timezone

import streamlit as st
from openai import OpenAI


# =========================
# 访问控制 / 每周密钥（A 方案）
# =========================
def current_week_id() -> str:
    # 使用 UTC 的 ISO Week
    now = datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def weekly_access_code(seed: str) -> str:
    # 生成短访问码（8 位），可按需改长
    msg = current_week_id().encode("utf-8")
    digest = hmac.new(seed.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return digest[:8].upper()


def require_gate():
    """
    门禁：
    - weekly access code（由 ACCESS_SEED 生成）
    - admin key（固定 ADMIN_KEY）
    通过后：
    - st.session_state.authed = True
    - st.session_state.is_admin = True/False
    """
    seed = st.secrets.get("ACCESS_SEED", "")
    admin_key = st.secrets.get("ADMIN_KEY", "")

    st.sidebar.divider()
    st.sidebar.subheader("访问控制")

    if st.session_state.get("authed"):
        return

    code_in = st.sidebar.text_input("输入访问码", type="password")
    admin_in = st.sidebar.text_input("管理员密钥（可选）", type="password")

    ok_weekly = bool(seed) and bool(code_in) and (code_in.strip().upper() == weekly_access_code(seed))
    ok_admin = bool(admin_key) and bool(admin_in) and (admin_in.strip() == admin_key)

    if ok_weekly or ok_admin:
        st.session_state.authed = True
        st.session_state.is_admin = bool(ok_admin)
        st.rerun()

    st.info("需要访问码才能使用。")
    st.stop()


def rate_limit(min_interval_sec: float = 2.0, max_per_day: int = 200):
    """
    基础限流（按 session_state）：
    - 最短间隔 min_interval_sec
    - 每日最多 max_per_day 次
    """
    now_ts = time.time()
    last = st.session_state.get("last_call_ts", 0.0)
    if now_ts - last < min_interval_sec:
        st.warning("操作太快了，稍等一下再发。")
        st.stop()
    st.session_state.last_call_ts = now_ts

    today = datetime.now(timezone.utc).date().isoformat()
    key = f"count_{today}"
    st.session_state[key] = st.session_state.get(key, 0) + 1
    if st.session_state[key] > max_per_day:
        st.error("今日使用次数已达上限。")
        st.stop()


# =========================
# Streamlit 基础配置
# =========================
st.set_page_config(page_title="多角色聊天", layout="wide")

CHARACTERS = {
    "小美": "温柔、会关心人、聊天自然",
    "阿哲": "理性、冷静、喜欢分析问题",
    "小周": "活泼、爱开玩笑、反应快",
}

# 先门禁（A 方案：在任何 DB / API 之前）
require_gate()

# 管理员可见：显示本周访问码（方便你发给女朋友）
if st.session_state.get("is_admin") and "ACCESS_SEED" in st.secrets:
    st.sidebar.success(f"本周访问码：{weekly_access_code(st.secrets['ACCESS_SEED'])}")

# Session ID（用于区分不同访问者的对话记录）
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 门禁通过后再连接数据库（A 方案）
conn = st.connection("neon", type="sql")


# =========================
# DB helpers
# =========================
def load_messages(character: str):
    q = """
    SELECT role, content
    FROM chat_messages
    WHERE session_id = :sid AND character = :ch
    ORDER BY created_at
    """
    df = conn.query(
        q,
        params={"sid": st.session_state.session_id, "ch": character},
        ttl=0,
    )
    return df.to_dict("records")


def save_message(character: str, role: str, content: str):
    q = """
    INSERT INTO chat_messages (session_id, character, role, content)
    VALUES (:sid, :ch, :role, :content)
    """
    with conn.session as s:
        s.execute(
            q,
            {
                "sid": st.session_state.session_id,
                "ch": character,
                "role": role,
                "content": content,
            },
        )
        s.commit()


# =========================
# OpenAI
# =========================
def get_ai_reply(character: str, history: list[dict], user_text: str) -> str:
    if "OPENAI_API_KEY" not in st.secrets:
        return f"（测试模式）{character} 收到了：{user_text}"

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    messages = [
        {
            "role": "system",
            "content": f"你在扮演{character}，性格是：{CHARACTERS[character]}。请用中文自然聊天。",
        }
    ]

    # 控制上下文长度，避免无限增长
    for m in history[-15:]:
        # history 结构：{"role": "...", "content": "..."}
        messages.append(m)

    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
    )
    return resp.choices[0].message.content


# =========================
# UI
# =========================
st.sidebar.title("好友列表")
character = st.sidebar.radio("选择角色", list(CHARACTERS.keys()))

st.title(f"正在和「{character}」聊天")

history = load_messages(character)

for msg in history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_text = st.chat_input("输入消息...")
if user_text:
    # 存用户消息
    save_message(character, "user", user_text)
    with st.chat_message("user"):
        st.write(user_text)

    # 限流（在调用 OpenAI 前）
    rate_limit(min_interval_sec=2.0, max_per_day=200)

    # AI 回复
    reply = get_ai_reply(character, history, user_text)
    save_message(character, "assistant", reply)

    with st.chat_message("assistant"):
        st.write(reply)

    st.rerun()
