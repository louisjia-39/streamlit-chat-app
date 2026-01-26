import uuid
import time
import random
import base64
import hmac
import hashlib
from datetime import datetime, timezone
from PIL import Image
import io
import streamlit as st
from openai import OpenAI
from sqlalchemy import text


# =========================
# 访问控制 / 每周密钥（A 方案）
# =========================
def current_week_id() -> str:
    now = datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def weekly_access_code(seed: str) -> str:
    msg = current_week_id().encode("utf-8")
    digest = hmac.new(seed.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return digest[:8].upper()


def require_gate():
    seed = st.secrets.get("ACCESS_SEED", "")
    admin_key = st.secrets.get("ADMIN_KEY", "")

    st.sidebar.divider()
    st.sidebar.subheader("访问控制")

    if st.session_state.get("authed"):
        return

    code_in = st.sidebar.text_input("输入访问码", type="password")
    admin_in = st.sidebar.text_input("管理员密钥（可选）", type="password")

    # 移动端 Enter 不一定触发 rerun，显式按钮最稳
    submitted = st.sidebar.button("登录")

    if submitted:
        ok_weekly = bool(seed) and bool(code_in) and (code_in.strip().upper() == weekly_access_code(seed))
        ok_admin = bool(admin_key) and bool(admin_in) and (admin_in.strip() == admin_key)

        if ok_weekly or ok_admin:
            st.session_state.authed = True
            st.session_state.is_admin = bool(ok_admin)
            st.rerun()
        else:
            st.sidebar.error("访问码或管理员密钥不正确。")

    st.info("需要访问码才能使用。")
    st.stop()


def rate_limit(min_interval_sec: float = 2.0, max_per_day: int = 200):
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
# Streamlit 配置 & 角色
# =========================
st.set_page_config(page_title="多角色聊天", layout="wide")

CHARACTERS = {
    "芙宁娜": "自尊心强、嘴硬、不轻易示弱、本质关心用户、不主动讨好",
    "胡桃": "活泼、调皮、善良、偶尔吓人、爱开玩笑",
    "宵宫": "热情、可靠、爱照顾人、工作认真、幽默",
}

# 没设置头像图片时的默认（emoji）
DEFAULT_AVATARS = {
    "user": "🙂",
    "芙宁娜": "🌸",
    "胡桃": "🧠",
    "宵宫": "⚡",
}

# 先门禁（在 DB / API 之前）
require_gate()

# 管理员显示本周访问码
if st.session_state.get("is_admin") and "ACCESS_SEED" in st.secrets:
    st.sidebar.success(f"本周访问码：{weekly_access_code(st.secrets['ACCESS_SEED'])}")

# Session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 连接 DB（门禁通过后）
conn = st.connection("neon", type="sql")


# =========================
# DB：建表（只补头像表）
# =========================
def ensure_tables():
    # 注意：session.execute 必须用 text()
    q = text("""
        CREATE TABLE IF NOT EXISTS character_profiles (
            character TEXT PRIMARY KEY,
            avatar_data_url TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    with conn.session as s:
        s.execute(q)
        s.commit()


ensure_tables()


# =========================
# 头像：存取（data URL，持久化到 Neon）
# =========================
def file_to_data_url(uploaded_file) -> str:
    """
    上传头像：自动缩放 + 压缩，输出 data URL 存 Neon。
    - 输入：png/jpg/jpeg
    - 输出：优先 JPEG（体积小）；如有透明通道则用 PNG
    - 目标：<= 2MB（若超过会自动降低 JPEG 质量）
    """
    MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB
    MAX_SIDE = 512  # 最长边像素

    raw = uploaded_file.getvalue()
    if len(raw) == 0:
        raise ValueError("空文件。")

    # 读取图片
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise ValueError("无法识别图片格式，请上传 png/jpg/jpeg。")

    # 修正方向（有些手机照片会旋转）
    try:
        exif = img.getexif()
        orientation = exif.get(274)  # 274 = Orientation
        if orientation == 3:
            img = img.rotate(180, expand=True)
        elif orientation == 6:
            img = img.rotate(270, expand=True)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
    except Exception:
        pass

    # 缩放到最长边 MAX_SIDE（保持比例）
    w, h = img.size
    scale = min(MAX_SIDE / max(w, h), 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 判断是否有透明通道
    has_alpha = (
        img.mode in ("RGBA", "LA") or
        (img.mode == "P" and "transparency" in img.info)
    )

    # 透明图：尽量保留透明（PNG），但 PNG 可能大；一般头像建议用无透明 JPEG
    if has_alpha:
        # 转 RGBA 并输出 PNG（带 optimize）
        out = io.BytesIO()
        img_rgba = img.convert("RGBA")
        img_rgba.save(out, format="PNG", optimize=True)
        data = out.getvalue()

        # 如果 PNG 仍然 >2MB，改用 JPEG（白底），更容易压到 2MB
        if len(data) > MAX_AVATAR_BYTES:
            img_rgb = Image.new("RGB", img_rgba.size, (255, 255, 255))
            img_rgb.paste(img_rgba, mask=img_rgba.split()[-1])  # alpha 作为 mask
            data, mime = _encode_jpeg_under_limit(img_rgb, MAX_AVATAR_BYTES)
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"

        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    # 非透明：JPEG 压缩并确保 <= 2MB
    img_rgb = img.convert("RGB")
    data, mime = _encode_jpeg_under_limit(img_rgb, MAX_AVATAR_BYTES)
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _encode_jpeg_under_limit(img_rgb: "Image.Image", max_bytes: int):
    """
    尝试用不同 JPEG 质量输出，确保 <= max_bytes
    """
    for quality in [85, 80, 75, 70, 65, 60, 55, 50]:
        out = io.BytesIO()
        img_rgb.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) <= max_bytes:
            return data, "image/jpeg"

    # 仍然超限：最后再强行降一点（通常不会到这里，除非图片异常大/复杂）
    out = io.BytesIO()
    img_rgb.save(out, format="JPEG", quality=45, optimize=True, progressive=True)
    data = out.getvalue()
    if len(data) > max_bytes:
        raise ValueError("图片内容过于复杂，压缩后仍超过 2MB。请换一张更小的图或先截图裁剪。")
    return data, "image/jpeg"

# =========================
# DB：聊天记录
# =========================
def load_messages(character: str):
    # conn.query 用字符串 SQL
    q = """
        SELECT role, content
        FROM chat_messages
        WHERE session_id = :sid AND character = :ch
        ORDER BY created_at
    """
    df = conn.query(q, params={"sid": st.session_state.session_id, "ch": character}, ttl=0)
    return df.to_dict("records")


def save_message(character: str, role: str, content: str):
    # session.execute 必须用 text()
    q = text("""
        INSERT INTO chat_messages (session_id, character, role, content)
        VALUES (:sid, :ch, :role, :content)
    """)
    with conn.session as s:
        s.execute(q, {"sid": st.session_state.session_id, "ch": character, "role": role, "content": content})
        s.commit()


# =========================
# OpenAI
# =========================
def get_ai_reply(character: str, history: list[dict], user_text: str) -> str:
    if "OPENAI_API_KEY" not in st.secrets:
        return f"（测试模式）{character} 收到了：{user_text}"

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    messages = [{
        "role": "system",
        "content": f"你在扮演{character}，性格是：{CHARACTERS[character]}。请用中文自然聊天，像真实女朋友一样。",
    }]

    for m in history[-15:]:
        messages.append(m)

    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
    )
    return resp.choices[0].message.content


def get_proactive_message(character: str, history: list[dict]) -> str:
    if "OPENAI_API_KEY" not in st.secrets:
        samples = {
            "芙宁娜": "我刚刚想到一个问题：如果今晚只能做一件让你开心的事，你会选什么？",
            "胡桃": "我想抛个小问题：你觉得“效率”和“幸福感”哪个更重要？为什么？",
            "宵宫": "随机话题：你最近最上头的一首歌是什么？我去听听。",
        }
        return f"（测试模式）{samples.get(character, '我来主动开个话题：你最近在忙啥？')}"

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    messages = [{
        "role": "system",
        "content": f"你在扮演{character}，性格是：{CHARACTERS[character]}。你现在要主动开启一个轻松自然的话题，避免AI味，像真实聊天。",
    }]

    for m in history[-15:]:
        messages.append(m)

    messages.append({
        "role": "user",
        "content": "请你主动发起一条消息来开启话题。要求：简短自然、像朋友发微信、不要问卷式连环提问。",
    })

    resp = client.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
    )
    return resp.choices[0].message.content


# =========================
# 头像：根据 DB 配置决定每条消息的 avatar
# =========================
db_avatars = get_avatars_from_db()


def avatar_for(role: str, character: str):
    if role == "user":
        return DEFAULT_AVATARS["user"]
    # assistant：优先 DB 图像，其次默认 emoji
    return db_avatars.get(character, DEFAULT_AVATARS.get(character, "🤖"))


# =========================
# 管理员：头像管理面板
# =========================
if st.session_state.get("is_admin"):
    st.sidebar.divider()
    st.sidebar.subheader("管理员：头像管理")

    target = st.sidebar.selectbox("选择要修改头像的角色", list(CHARACTERS.keys()))
    current = db_avatars.get(target)

    if current:
        st.sidebar.caption("当前头像（预览）")
        st.sidebar.image(current, width=64)
    else:
        st.sidebar.caption("当前头像：默认（未设置图片）")

    up = st.sidebar.file_uploader("上传新头像（png/jpg，≤300KB）", type=["png", "jpg", "jpeg"])

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("保存头像", use_container_width=True, disabled=(up is None)):
            try:
                data_url = file_to_data_url(up)
                upsert_avatar(target, data_url)
                st.sidebar.success("头像已保存。")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))

    with col2:
        if st.button("清空头像", use_container_width=True):
            upsert_avatar(target, None)
            st.sidebar.success("已清空，回到默认头像。")
            st.rerun()


# =========================
# 主动发消息控制
# =========================
st.sidebar.divider()
st.sidebar.subheader("主动发消息")
auto_proactive = st.sidebar.checkbox("启用自动主动（有交互时触发）", value=False)
proactive_interval_min = st.sidebar.slider("最短间隔（分钟）", 1, 60, 10)
proactive_prob = st.sidebar.slider("触发概率（%）", 0, 100, 30)
proactive_now = st.sidebar.button("让 TA 主动说一句")


# =========================
# UI
# =========================
st.sidebar.title("好友列表")
character = st.sidebar.radio("选择角色", list(CHARACTERS.keys()))

st.title(f"正在和「{character}」聊天")

history = load_messages(character)

for msg in history:
    if msg["role"] == "user":
        with st.chat_message("user", avatar=avatar_for("user", character)):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar=avatar_for("assistant", character)):
            st.write(msg["content"])

# 按钮主动（最可靠）
if proactive_now:
    rate_limit(min_interval_sec=1.0, max_per_day=200)
    proactive_text = get_proactive_message(character, history)
    save_message(character, "assistant", proactive_text)
    st.rerun()

# 自动主动（只在页面有 rerun/交互时触发）
if auto_proactive:
    last_key = f"last_proactive_ts_{character}"
    last_ts = st.session_state.get(last_key, 0.0)
    now_ts = time.time()
    if now_ts - last_ts >= proactive_interval_min * 60:
        if random.randint(1, 100) <= proactive_prob:
            rate_limit(min_interval_sec=1.0, max_per_day=200)
            proactive_text = get_proactive_message(character, history)
            save_message(character, "assistant", proactive_text)
            st.session_state[last_key] = now_ts
            st.rerun()
        else:
            st.session_state[last_key] = now_ts

user_text = st.chat_input("输入消息...")
if user_text:
    save_message(character, "user", user_text)
    with st.chat_message("user", avatar=avatar_for("user", character)):
        st.write(user_text)

    rate_limit(min_interval_sec=2.0, max_per_day=200)

    reply = get_ai_reply(character, history, user_text)
    save_message(character, "assistant", reply)

    with st.chat_message("assistant", avatar=avatar_for("assistant", character)):
        st.write(reply)

    st.rerun()
