import uuid
import time
import random
import base64
import hmac
import hashlib
from datetime import datetime, timezone
import io
import html as _html

import streamlit as st
from openai import OpenAI
from sqlalchemy import text
from PIL import Image


# =========================
# 基础配置
# =========================
st.set_page_config(page_title="聊天", layout="wide")

CHARACTERS = {
    "芙宁娜": "自尊心强、嘴硬、不轻易示弱、本质关心用户、不主动讨好",
    "胡桃": "活泼、调皮、善良、偶尔吓人、爱开玩笑",
    "宵宫": "热情、可靠、爱照顾人、工作认真、幽默",
}

DEFAULT_AVATARS = {
    "user": "🙂",
    "芙宁娜": "👑",
    "胡桃": "🦋",
    "宵宫": "🎆",
}

DEFAULT_SETTINGS = {
    "TEMP_CHAT": "0.95",
    "TEMP_TEACH": "0.35",
    "TOP_P": "1.0",
    "PRESENCE_PENALTY": "0.6",
    "FREQUENCY_PENALTY": "0.2",
    "PROMPT_CHAT_EXTRA": "",
    "PROMPT_TEACH_EXTRA": "",
    "PROACTIVE_ENABLED": "1",
    "PROACTIVE_MIN_INTERVAL_MIN": "20",
    "PROACTIVE_PROB_PCT": "25",
    # A2：时间分割条粒度
    "TIME_DIVIDER_GRANULARITY": "minute",  # "minute" 或 "5min"
}

# =========================
# A1/A2：WeChat-ish UI（更像微信）
# =========================
st.markdown(
    """
<style>
header[data-testid="stHeader"] { display: none; }
div[data-testid="stToolbar"] { display: none; }
footer { display: none; }

/* 主背景更像微信聊天背景 */
.main { background: #ECE5DD; }

/* 侧边栏稍微淡一点 */
section[data-testid="stSidebar"] { background: #F7F7F7; }

/* 输入框贴底 + 视觉更像微信输入区域 */
div[data-testid="stChatInput"] {
    position: sticky;
    bottom: 0;
    background: #ECE5DD;
    padding-top: 10px;
    padding-bottom: 12px;
    z-index: 10;
}

/* 标题 */
.wx-title {
    font-size: 30px;
    font-weight: 800;
    margin: 10px 0 6px 0;
}
.wx-pill {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(255,255,255,.75);
    border: 1px solid rgba(0,0,0,.06);
    font-size: 13px;
}

/* 聊天容器 */
.wx-chat {
    width: 100%;
    max-width: 940px;
    margin: 0 auto;
    padding: 6px 10px 0 10px;
}

/* A2 时间分割条 */
.wx-time {
    width: 100%;
    display: flex;
    justify-content: center;
    margin: 10px 0 8px 0;
}
.wx-time span {
    font-size: 12px;
    color: rgba(0,0,0,.55);
    background: rgba(255,255,255,.55);
    border: 1px solid rgba(0,0,0,.05);
    border-radius: 999px;
    padding: 4px 10px;
}

/* 一条消息一行 */
.wx-row {
    display: flex;
    gap: 8px;
    margin: 6px 0;
    align-items: flex-start;
}

/* 左（AI） */
.wx-row.bot { justify-content: flex-start; }

/* 右（用户） */
.wx-row.user { justify-content: flex-end; }

/* 头像更贴微信：方圆角（不是完美圆），稍大一点 */
.wx-avatar {
    width: 40px;
    height: 40px;
    border-radius: 9px;
    overflow: hidden;
    flex: 0 0 40px;
    background: rgba(0,0,0,.06);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
}
.wx-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

/* 气泡：更像微信（圆角更大、阴影更轻、宽度更像） */
.wx-bubble {
    max-width: min(72%, 620px);
    padding: 9px 12px;
    border-radius: 14px;
    font-size: 16px;
    line-height: 1.55;
    position: relative;
    box-shadow: 0 1px 0 rgba(0,0,0,.05);
    word-wrap: break-word;
    white-space: pre-wrap;
}

/* 左白 */
.wx-bubble.bot {
    background: #FFFFFF;
    border: 1px solid rgba(0,0,0,.06);
}

/* 右绿（微信绿更接近） */
.wx-bubble.user {
    background: #95EC69;
    border: 1px solid rgba(0,0,0,.03);
}

/* 尖角：微信更小更贴近 */
.wx-bubble.bot:before {
    content: "";
    position: absolute;
    left: -6px;
    top: 12px;
    width: 0; height: 0;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
    border-right: 7px solid #FFFFFF;
}
.wx-bubble.bot:after {
    content: "";
    position: absolute;
    left: -7px;
    top: 12px;
    width: 0; height: 0;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
    border-right: 7px solid rgba(0,0,0,.06);
    z-index: -1;
}

/* 右尖角 */
.wx-bubble.user:before {
    content: "";
    position: absolute;
    right: -6px;
    top: 12px;
    width: 0; height: 0;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
    border-left: 7px solid #95EC69;
}

/* 让右侧气泡和头像更贴近 */
.wx-row.user .wx-bubble { margin-right: 1px; }
.wx-row.bot .wx-bubble { margin-left: 1px; }

</style>
""",
    unsafe_allow_html=True,
)


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

    st.sidebar.subheader("访问控制")

    if st.session_state.get("authed"):
        return

    code_in = st.sidebar.text_input("输入访问码", type="password")
    admin_in = st.sidebar.text_input("管理员密钥（可选）", type="password")
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


def rate_limit(min_interval_sec: float = 1.6, max_per_day: int = 300):
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


# 先门禁
require_gate()

# Session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 默认模式
if "mode" not in st.session_state:
    st.session_state.mode = "聊天"


# =========================
# DB 连接 & 建表
# =========================
conn = st.connection("neon", type="sql")


def ensure_tables():
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                character TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        s.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages(session_id, character, created_at);
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS character_profiles (
                character TEXT PRIMARY KEY,
                avatar_data_url TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        s.commit()


ensure_tables()


# =========================
# Settings：读取/写入
# =========================
def load_settings() -> dict:
    df = conn.query("SELECT key, value FROM app_settings", ttl=0)
    s = dict(DEFAULT_SETTINGS)
    for _, row in df.iterrows():
        s[str(row["key"])] = str(row["value"])
    return s


def upsert_setting(key: str, value: str):
    q = text("""
        INSERT INTO app_settings (key, value)
        VALUES (:k, :v)
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value,
                      updated_at = now();
    """)
    with conn.session as s:
        s.execute(q, {"k": key, "v": value})
        s.commit()


SETTINGS = load_settings()


def s_float(key: str, default: float) -> float:
    try:
        return float(SETTINGS.get(key, str(default)))
    except Exception:
        return default


def s_int(key: str, default: int) -> int:
    try:
        return int(float(SETTINGS.get(key, str(default))))
    except Exception:
        return default


def s_bool(key: str, default: bool) -> bool:
    v = SETTINGS.get(key, "1" if default else "0").strip()
    return v in ("1", "true", "True", "yes", "YES", "on", "ON")


# =========================
# 头像：压缩 + 存取（2MB 内）
# =========================
def _encode_jpeg_under_limit(img_rgb: "Image.Image", max_bytes: int):
    for quality in [85, 80, 75, 70, 65, 60, 55, 50]:
        out = io.BytesIO()
        img_rgb.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) <= max_bytes:
            return data, "image/jpeg"

    out = io.BytesIO()
    img_rgb.save(out, format="JPEG", quality=45, optimize=True, progressive=True)
    data = out.getvalue()
    if len(data) > max_bytes:
        raise ValueError("图片压缩后仍超过 2MB。建议先截图裁剪或换小一点的图。")
    return data, "image/jpeg"


def file_to_data_url(uploaded_file) -> str:
    MAX_AVATAR_BYTES = 2 * 1024 * 1024
    MAX_SIDE = 512

    raw = uploaded_file.getvalue()
    if not raw:
        raise ValueError("空文件。")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise ValueError("无法识别图片格式，请上传 png/jpg/jpeg。")

    # 旋转修正
    try:
        exif = img.getexif()
        orientation = exif.get(274)
        if orientation == 3:
            img = img.rotate(180, expand=True)
        elif orientation == 6:
            img = img.rotate(270, expand=True)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
    except Exception:
        pass

    # 缩放
    w, h = img.size
    scale = min(MAX_SIDE / max(w, h), 1.0)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    has_alpha = (
        img.mode in ("RGBA", "LA") or
        (img.mode == "P" and "transparency" in img.info)
    )

    if has_alpha:
        out = io.BytesIO()
        img_rgba = img.convert("RGBA")
        img_rgba.save(out, format="PNG", optimize=True)
        data = out.getvalue()

        # 超 2MB：白底转 JPEG
        if len(data) > MAX_AVATAR_BYTES:
            img_rgb = Image.new("RGB", img_rgba.size, (255, 255, 255))
            img_rgb.paste(img_rgba, mask=img_rgba.split()[-1])
            data, mime = _encode_jpeg_under_limit(img_rgb, MAX_AVATAR_BYTES)
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"

        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    img_rgb = img.convert("RGB")
    data, mime = _encode_jpeg_under_limit(img_rgb, MAX_AVATAR_BYTES)
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def upsert_avatar(key_name: str, avatar_data_url: str | None):
    q = text("""
        INSERT INTO character_profiles (character, avatar_data_url)
        VALUES (:ch, :url)
        ON CONFLICT (character)
        DO UPDATE SET avatar_data_url = EXCLUDED.avatar_data_url,
                      updated_at = now();
    """)
    with conn.session as s:
        s.execute(q, {"ch": key_name, "url": avatar_data_url})
        s.commit()


def get_avatars_from_db() -> dict:
    df = conn.query("SELECT character, avatar_data_url FROM character_profiles", ttl=0)
    avatars = {}
    for _, row in df.iterrows():
        if row["avatar_data_url"]:
            avatars[str(row["character"])] = str(row["avatar_data_url"])
    return avatars


DB_AVATARS = get_avatars_from_db()


def avatar_for(role: str, character: str):
    if role == "user":
        return DB_AVATARS.get("user", DEFAULT_AVATARS["user"])
    return DB_AVATARS.get(character, DEFAULT_AVATARS.get(character, "🤖"))


# =========================
# DB：聊天记录（A2：带 created_at）
# =========================
def load_messages(character: str):
    q = """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE session_id = :sid AND character = :ch
        ORDER BY created_at
    """
    df = conn.query(q, params={"sid": st.session_state.session_id, "ch": character}, ttl=0)
    recs = df.to_dict("records")
    # 统一把 created_at 变成可用 datetime（pandas/psycopg 可能返回 str）
    for r in recs:
        ca = r.get("created_at")
        if isinstance(ca, str):
            # 兼容 ISO 字符串
            try:
                r["created_at"] = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            except Exception:
                r["created_at"] = None
    return recs


def save_message(character: str, role: str, content: str):
    q = text("""
        INSERT INTO chat_messages (session_id, character, role, content)
        VALUES (:sid, :ch, :role, :content)
    """)
    with conn.session as s:
        s.execute(q, {"sid": st.session_state.session_id, "ch": character, "role": role, "content": content})
        s.commit()


# =========================
# OpenAI：聊天/教学 两种模式
# =========================
def build_system_prompt(character: str, mode: str) -> str:
    base_persona = f"你在扮演{character}，性格是：{CHARACTERS[character]}。"

    if mode == "教学":
        teach_core = (
            "你现在进入【教学模式】。\n"
            "目标：像顶级家教一样帮助用户学习/解题。\n"
            "要求：先澄清题目与目标；分步骤讲解；必要时反问引导；给出可操作练习与检查点；避免空话。"
        )
        extra = SETTINGS.get("PROMPT_TEACH_EXTRA", "")
        return base_persona + "\n" + teach_core + ("\n" + extra if extra else "")
    else:
        chat_core = (
            "你现在进入【聊天模式】。\n"
            "要求：像真实微信聊天，不要AI味；句子自然；可以有口头禅、停顿、情绪；不要长篇论文；"
            "避免‘作为AI’表述；可以适度反问推进聊天。"
        )
        extra = SETTINGS.get("PROMPT_CHAT_EXTRA", "")
        return base_persona + "\n" + chat_core + ("\n" + extra if extra else "")


def call_openai(messages, temperature: float):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
        temperature=temperature,
        top_p=s_float("TOP_P", 1.0),
        presence_penalty=s_float("PRESENCE_PENALTY", 0.6),
        frequency_penalty=s_float("FREQUENCY_PENALTY", 0.2),
    )
    return resp.choices[0].message.content


def get_ai_reply(character: str, history: list[dict], user_text: str, mode: str) -> str:
    if "OPENAI_API_KEY" not in st.secrets:
        return f"（测试模式）{character} 收到了：{user_text}"

    system_prompt = build_system_prompt(character, mode)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-15:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    temp = s_float("TEMP_TEACH", 0.35) if mode == "教学" else s_float("TEMP_CHAT", 0.95)
    return call_openai(messages, temp)


def get_proactive_message(character: str, history: list[dict]) -> str:
    if "OPENAI_API_KEY" not in st.secrets:
        samples = {
            "芙宁娜": "哼，你忙完了吗？我可不是在等你……只是刚好想到你。",
            "胡桃": "嘿嘿！我路过！你今天有没有发生什么离谱但好笑的事？",
            "宵宫": "我突然想到你！今天过得怎么样？要不要来点轻松话题～",
        }
        return samples.get(character, "我来主动开个话题：你最近在忙啥？")

    system_prompt = build_system_prompt(character, "聊天")
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": "请主动发起一条简短自然的微信开场消息，不要问卷式连环提问。"})
    return call_openai(messages, s_float("TEMP_CHAT", 0.95))


# =========================
# A1：自绘消息渲染（左右气泡）
# =========================
def _avatar_html(avatar):
    if isinstance(avatar, str) and avatar.startswith("data:"):
        return f'<div class="wx-avatar"><img src="{avatar}" /></div>'
    safe = _html.escape(str(avatar))
    return f'<div class="wx-avatar">{safe}</div>'


def render_time_divider(label: str):
    st.markdown(f'<div class="wx-time"><span>{_html.escape(label)}</span></div>', unsafe_allow_html=True)


def render_message(role: str, character: str, content: str):
    is_user = (role == "user")
    avatar = avatar_for("user" if is_user else "assistant", character)
    safe_text = _html.escape(content).replace("\n", "<br>")

    if is_user:
        html_block = f"""
        <div class="wx-row user">
            <div class="wx-bubble user">{safe_text}</div>
            {_avatar_html(avatar)}
        </div>
        """
    else:
        html_block = f"""
        <div class="wx-row bot">
            {_avatar_html(avatar)}
            <div class="wx-bubble bot">{safe_text}</div>
        </div>
        """
    st.markdown(html_block, unsafe_allow_html=True)


def fmt_time_label(dt: datetime) -> str:
    # 你在美国，这里做一个本地显示（没有用户时区就用本机/UTC）
    # Streamlit Cloud 通常是 UTC，显示也可接受；想强制某时区再加 pytz/zoneinfo。
    try:
        local_dt = dt.astimezone()  # 使用运行环境本地时区
    except Exception:
        local_dt = dt

    # 更像微信：今天只显示时:分；非今天显示月/日 时:分
    now = datetime.now(timezone.utc)
    try:
        now_local = now.astimezone()
    except Exception:
        now_local = now

    if local_dt.date() == now_local.date():
        return local_dt.strftime("%H:%M")
    return local_dt.strftime("%m/%d %H:%M")


def bucket_key(dt: datetime) -> str:
    gran = SETTINGS.get("TIME_DIVIDER_GRANULARITY", "minute")
    try:
        d = dt.astimezone()
    except Exception:
        d = dt
    if gran == "5min":
        m = (d.minute // 5) * 5
        return d.replace(minute=m, second=0, microsecond=0).isoformat()
    # minute
    return d.replace(second=0, microsecond=0).isoformat()


# =========================
# 管理员后台（只有管理员看得到）
# =========================
if st.session_state.get("is_admin"):
    st.sidebar.divider()
    st.sidebar.subheader("管理员后台")

    if "ACCESS_SEED" in st.secrets:
        st.sidebar.success(f"本周访问码：{weekly_access_code(st.secrets['ACCESS_SEED'])}")

    st.sidebar.markdown("#### 头像管理（含 user）")
    target = st.sidebar.selectbox("选择要修改头像的对象", ["user"] + list(CHARACTERS.keys()))
    cur = DB_AVATARS.get(target)
    if cur:
        st.sidebar.image(cur, width=72, caption="当前头像预览")
    else:
        st.sidebar.caption("当前头像：默认（未设置图片）")

    up = st.sidebar.file_uploader("上传头像（png/jpg ≤2MB，自动压缩）", type=["png", "jpg", "jpeg"])
    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.sidebar.button("保存头像", use_container_width=True, disabled=(up is None)):
            try:
                data_url = file_to_data_url(up)
                upsert_avatar(target, data_url)
                st.sidebar.success("头像已保存。")
                st.rerun()
            except Exception as e:
                st.sidebar.error(str(e))
    with c2:
        if st.sidebar.button("清空头像", use_container_width=True):
            upsert_avatar(target, None)
            st.sidebar.success("已清空，回到默认头像。")
            st.rerun()

    st.sidebar.markdown("#### AI 参数")
    temp_chat = st.sidebar.slider("聊天温度 Temperature", 0.0, 1.5, float(s_float("TEMP_CHAT", 0.95)), 0.05)
    temp_teach = st.sidebar.slider("教学温度 Temperature", 0.0, 1.5, float(s_float("TEMP_TEACH", 0.35)), 0.05)
    top_p = st.sidebar.slider("top_p", 0.1, 1.0, float(s_float("TOP_P", 1.0)), 0.05)
    presence = st.sidebar.slider("presence_penalty", -2.0, 2.0, float(s_float("PRESENCE_PENALTY", 0.6)), 0.1)
    freq = st.sidebar.slider("frequency_penalty", -2.0, 2.0, float(s_float("FREQUENCY_PENALTY", 0.2)), 0.1)

    st.sidebar.markdown("#### Prompt（追加）")
    prompt_chat = st.sidebar.text_area("聊天模式追加 Prompt", value=SETTINGS.get("PROMPT_CHAT_EXTRA", ""), height=120)
    prompt_teach = st.sidebar.text_area("教学模式追加 Prompt", value=SETTINGS.get("PROMPT_TEACH_EXTRA", ""), height=120)

    st.sidebar.markdown("#### 主动聊天（管理员可控）")
    proactive_enabled = st.sidebar.checkbox("启用主动聊天", value=s_bool("PROACTIVE_ENABLED", True))
    proactive_interval = st.sidebar.slider("最短间隔（分钟）", 1, 180, s_int("PROACTIVE_MIN_INTERVAL_MIN", 20))
    proactive_prob = st.sidebar.slider("触发概率（%）", 0, 100, s_int("PROACTIVE_PROB_PCT", 25))
    proactive_now = st.sidebar.button("让 TA 立刻主动说一句")

    st.sidebar.markdown("#### 时间分割条")
    gran = st.sidebar.selectbox("时间分割粒度", ["minute", "5min"], index=0 if SETTINGS.get("TIME_DIVIDER_GRANULARITY", "minute") == "minute" else 1)

    if st.sidebar.button("保存以上设置", type="primary"):
        upsert_setting("TEMP_CHAT", str(temp_chat))
        upsert_setting("TEMP_TEACH", str(temp_teach))
        upsert_setting("TOP_P", str(top_p))
        upsert_setting("PRESENCE_PENALTY", str(presence))
        upsert_setting("FREQUENCY_PENALTY", str(freq))
        upsert_setting("PROMPT_CHAT_EXTRA", prompt_chat)
        upsert_setting("PROMPT_TEACH_EXTRA", prompt_teach)
        upsert_setting("PROACTIVE_ENABLED", "1" if proactive_enabled else "0")
        upsert_setting("PROACTIVE_MIN_INTERVAL_MIN", str(proactive_interval))
        upsert_setting("PROACTIVE_PROB_PCT", str(proactive_prob))
        upsert_setting("TIME_DIVIDER_GRANULARITY", gran)
        st.sidebar.success("设置已保存（Neon）。")
        st.rerun()
else:
    proactive_now = False


# =========================
# 普通用户界面（更像微信）
# =========================
st.sidebar.divider()
st.sidebar.subheader("好友列表")
character = st.sidebar.radio("选择聊天对象", list(CHARACTERS.keys()), label_visibility="collapsed")

colA, colB = st.columns([4, 1])
with colA:
    st.markdown(f'<div class="wx-title">正在和「{character}」聊天</div>', unsafe_allow_html=True)
with colB:
    mode = st.selectbox("模式", ["聊天", "教学"], index=0 if st.session_state.mode == "聊天" else 1)
    st.session_state.mode = mode
    st.markdown(f'<div class="wx-pill">模式：{mode}</div>', unsafe_allow_html=True)

history = load_messages(character)

# 管理员点击“立刻主动”
if proactive_now:
    rate_limit(1.0, 300)
    proactive_text = get_proactive_message(character, history)
    save_message(character, "assistant", proactive_text)
    st.rerun()

# 自动主动（仅聊天模式）
if st.session_state.mode == "聊天" and s_bool("PROACTIVE_ENABLED", True):
    last_key = f"last_proactive_ts_{character}"
    last_ts = st.session_state.get(last_key, 0.0)
    now_ts = time.time()
    interval_min = s_int("PROACTIVE_MIN_INTERVAL_MIN", 20)
    prob_pct = s_int("PROACTIVE_PROB_PCT", 25)
    if now_ts - last_ts >= interval_min * 60:
        st.session_state[last_key] = now_ts
        if random.randint(1, 100) <= prob_pct:
            proactive_text = get_proactive_message(character, history)
            save_message(character, "assistant", proactive_text)
            st.rerun()

# 渲染（A2：时间分割条 + A1：微信气泡）
st.markdown('<div class="wx-chat">', unsafe_allow_html=True)

last_bucket = None
for msg in history:
    dt = msg.get("created_at")
    if isinstance(dt, datetime):
        bk = bucket_key(dt)
        if bk != last_bucket:
            render_time_divider(fmt_time_label(dt))
            last_bucket = bk
    render_message(msg["role"], character, msg["content"])

st.markdown("</div>", unsafe_allow_html=True)

# 输入
user_text = st.chat_input("输入消息…")
if user_text:
    save_message(character, "user", user_text)
    rate_limit()

    reply = get_ai_reply(character, history, user_text, st.session_state.mode)
    save_message(character, "assistant", reply)
    st.rerun()
