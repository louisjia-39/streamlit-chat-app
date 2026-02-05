import uuid
import time
import random
import base64
import secrets
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import io
import html as _html
import json
import re

import streamlit as st
from openai import OpenAI
from sqlalchemy import text
from PIL import Image


# =========================
# 配置
# =========================
st.set_page_config(page_title="聊天", layout="wide")

LA_TZ = ZoneInfo("America/Los_Angeles")

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
    # 温度：聊天更自然，教学更稳定
    "TEMP_CHAT": "1.05",
    "TEMP_TEACH": "0.35",
    "TOP_P": "1.0",
    "PRESENCE_PENALTY": "0.7",
    "FREQUENCY_PENALTY": "0.25",

    # prompt 追加（管理员可改）
    "PROMPT_CHAT_EXTRA": "",
    "PROMPT_TEACH_EXTRA": "",

    # 主动聊天（管理员可控）
    "PROACTIVE_ENABLED": "1",
    "PROACTIVE_MIN_INTERVAL_MIN": "20",
    "PROACTIVE_PROB_PCT": "25",

    # 时间分割条粒度
    "TIME_DIVIDER_GRANULARITY": "minute",  # minute / 5min
}


# =========================
# CSS：微信风格 + 好友列表 + 未读点 + 正在输入
# =========================
st.markdown(
    """
<style>
header[data-testid="stHeader"], div[data-testid="stToolbar"], footer { display:none !important; }

/* 背景更像微信 */
.main { background:#ECE5DD; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#F7F7F7; }
.sidebar-title { font-size:18px; font-weight:700; margin: 6px 0 10px 0; }
.wx-list { display:flex; flex-direction:column; gap:8px; }
.wx-item {
  display:flex; gap:10px; align-items:center;
  padding:10px 10px;
  border-radius:12px;
  border:1px solid rgba(0,0,0,.06);
  background: rgba(255,255,255,.85);
}
.wx-item.active { background:#FFFFFF; border-color: rgba(0,0,0,.10); }
.wx-item:hover { border-color: rgba(0,0,0,.14); }
.wx-item .avatar {
  width:40px; height:40px; border-radius:10px; overflow:hidden;
  background: rgba(0,0,0,.06);
  display:flex; align-items:center; justify-content:center;
  flex: 0 0 40px;
  position: relative;
  font-size: 20px;
}
.wx-item .avatar img { width:100%; height:100%; object-fit:cover; }
.wx-item .meta { flex:1; min-width:0; }
.wx-item .name { font-size:15px; font-weight:700; line-height:1.2; }
.wx-item .preview {
  font-size:12px; color: rgba(0,0,0,.60);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  margin-top:4px;
}
.unread-badge {
  min-width:18px; height:18px; padding:0 6px;
  border-radius:999px;
  background:#FF3B30;
  color:white;
  font-size:12px; line-height:18px;
  text-align:center;
}

/* 主区域 */
.wx-title {
  font-size: 30px; font-weight: 800;
  margin: 10px 0 6px 0;
}
.wx-pill {
  display:inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,.75);
  border: 1px solid rgba(0,0,0,.06);
  font-size: 13px;
}

/* 聊天容器 */
.wx-chat {
  width:100%;
  max-width: 940px;
  margin:0 auto;
  padding: 6px 10px 0 10px;
}

/* 时间分割条 */
.wx-time { width:100%; display:flex; justify-content:center; margin:10px 0 8px 0; }
.wx-time span {
  font-size:12px; color: rgba(0,0,0,.55);
  background: rgba(255,255,255,.55);
  border: 1px solid rgba(0,0,0,.05);
  border-radius: 999px;
  padding: 4px 10px;
}

/* 消息行 */
.wx-row { display:flex; gap:8px; margin:6px 0; align-items:flex-start; }
.wx-row.bot { justify-content:flex-start; }
.wx-row.user { justify-content:flex-end; }

/* 头像 */
.wx-avatar {
  width:40px; height:40px; border-radius:10px; overflow:hidden;
  background: rgba(0,0,0,.06);
  display:flex; align-items:center; justify-content:center;
  flex:0 0 40px;
  font-size:20px;
}
.wx-avatar img { width:100%; height:100%; object-fit:cover; }

/* 气泡 */
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
.wx-bubble.bot { background:#FFFFFF; border:1px solid rgba(0,0,0,.06); }
.wx-bubble.user { background:#95EC69; border:1px solid rgba(0,0,0,.03); }

/* 尖角 */
.wx-bubble.bot:before {
  content:""; position:absolute; left:-6px; top:12px; width:0; height:0;
  border-top:6px solid transparent; border-bottom:6px solid transparent;
  border-right:7px solid #FFFFFF;
}
.wx-bubble.bot:after {
  content:""; position:absolute; left:-7px; top:12px; width:0; height:0;
  border-top:6px solid transparent; border-bottom:6px solid transparent;
  border-right:7px solid rgba(0,0,0,.06); z-index:-1;
}
.wx-bubble.user:before {
  content:""; position:absolute; right:-6px; top:12px; width:0; height:0;
  border-top:6px solid transparent; border-bottom:6px solid transparent;
  border-left:7px solid #95EC69;
}

/* 输入框贴底 */
div[data-testid="stChatInput"]{
  position: sticky;
  bottom: 0;
  background: #ECE5DD;
  padding-top: 10px;
  padding-bottom: 12px;
  z-index: 10;
}

/* 正在输入… */
.typing {
  display:flex; gap:6px; align-items:center;
  color: rgba(0,0,0,.55);
  font-size: 14px;
}
.dots span{
  display:inline-block;
  width:6px; height:6px; border-radius:99px;
  background: rgba(0,0,0,.35);
  margin-right:3px;
  animation: blink 1s infinite;
}
.dots span:nth-child(2){ animation-delay: .2s; }
.dots span:nth-child(3){ animation-delay: .4s; }

@keyframes blink {
  0%, 100% { opacity: .2; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-2px); }
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# DB（Neon）
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

        # 每周随机访问码（全局一份，不按 session）
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS weekly_access_codes (
                week_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        s.commit()


ensure_tables()


# =========================
# 每周随机访问码（B）
# =========================
def current_week_id() -> str:
    now = datetime.now(LA_TZ)  # 按洛杉矶时间计算 ISO 周（周一切换）
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def week_id_from_dt(dt: datetime) -> str:
    d = dt.astimezone(LA_TZ)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def next_week_id() -> str:
    now = datetime.now(LA_TZ)
    thursday = now + timedelta(days=(3 - now.weekday()))
    next_thursday = thursday + timedelta(days=7)
    return week_id_from_dt(next_thursday)


def _gen_week_code(length: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_week_code_from_db(week_id: str) -> str | None:
    df = conn.query(
        "SELECT code FROM weekly_access_codes WHERE week_id = :w LIMIT 1",
        params={"w": week_id},
        ttl=0
    )
    if df.empty:
        return None
    return str(df.iloc[0]["code"])


def ensure_week_code(week_id: str) -> str:
    code = get_week_code_from_db(week_id)
    if code:
        return code

    new_code = _gen_week_code(8)
    q = text("""
        INSERT INTO weekly_access_codes (week_id, code)
        VALUES (:w, :c)
        ON CONFLICT (week_id) DO NOTHING;
    """)
    with conn.session as s:
        s.execute(q, {"w": week_id, "c": new_code})
        s.commit()

    return get_week_code_from_db(week_id) or new_code


def reset_week_code(week_id: str) -> str:
    """强制重置指定 week_id 的访问码（覆盖旧码）。返回新码。"""
    new_code = _gen_week_code(8)
    q = text("""
        INSERT INTO weekly_access_codes (week_id, code)
        VALUES (:w, :c)
        ON CONFLICT (week_id)
        DO UPDATE SET code = EXCLUDED.code,
                      created_at = now();
    """)
    with conn.session as s:
        s.execute(q, {"w": week_id, "c": new_code})
        s.commit()
    return new_code


# =========================
# 访问控制（A：登录后不显示门禁区）
# =========================
def require_gate():
    if st.session_state.get("authed"):
        return

    admin_key = st.secrets.get("ADMIN_KEY", "")
    if not admin_key:
        st.sidebar.error("缺少 ADMIN_KEY（请在 Secrets 配置管理员密码）。")
        st.stop()

    week_id = current_week_id()
    weekly_code = ensure_week_code(week_id)

    st.sidebar.subheader("访问控制（每周更新）")
    code_in = st.sidebar.text_input("输入本周访问码", type="password")
    admin_in = st.sidebar.text_input("管理员密钥（可选）", type="password")
    submitted = st.sidebar.button("登录", type="primary")

    if submitted:
        ok_weekly = bool(code_in) and (code_in.strip().upper() == weekly_code.upper())
        ok_admin = bool(admin_in) and (admin_in.strip() == admin_key)

        if ok_weekly or ok_admin:
            st.session_state.authed = True
            st.session_state.is_admin = bool(ok_admin)
            st.rerun()
        else:
            st.sidebar.error("访问码或管理员密钥不正确。")

    st.info("需要访问码才能使用（每周一自动刷新）。")
    st.stop()


def rate_limit(min_interval_sec: float = 1.4, max_per_day: int = 400):
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

# session id
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 默认模式
if "mode" not in st.session_state:
    st.session_state.mode = "聊天"

# 默认选中角色
if "selected_character" not in st.session_state:
    st.session_state.selected_character = list(CHARACTERS.keys())[0]

# 未读：上次查看时间（每个角色）
if "last_seen_ts" not in st.session_state:
    st.session_state.last_seen_ts = {ch: 0.0 for ch in CHARACTERS.keys()}


# =========================
# 设置（Neon）
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
# 头像：压缩 <=2MB（管理员上传）
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

    # 旋转修正（EXIF）
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
        img.mode in ("RGBA", "LA")
        or (img.mode == "P" and "transparency" in img.info)
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
# DB：消息读写
# =========================
def load_messages(character: str):
    q = """
        SELECT id, role, content, created_at
        FROM chat_messages
        WHERE session_id = :sid AND character = :ch
        ORDER BY created_at
    """
    df = conn.query(q, params={"sid": st.session_state.session_id, "ch": character}, ttl=0)
    recs = df.to_dict("records")
    for r in recs:
        ca = r.get("created_at")
        if isinstance(ca, str):
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


def get_latest_message_meta(character: str):
    q = """
        SELECT id, role, content, created_at
        FROM chat_messages
        WHERE session_id = :sid AND character = :ch
        ORDER BY created_at DESC
        LIMIT 1
    """
    df = conn.query(q, params={"sid": st.session_state.session_id, "ch": character}, ttl=0)
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    ca = row.get("created_at")
    if isinstance(ca, str):
        try:
            row["created_at"] = datetime.fromisoformat(ca.replace("Z", "+00:00"))
        except Exception:
            row["created_at"] = None
    return row


def get_unread_count(character: str) -> int:
    last_seen = st.session_state.last_seen_ts.get(character, 0.0)
    hist = load_messages(character)
    cnt = 0
    for m in hist:
        if m.get("role") == "assistant" and isinstance(m.get("created_at"), datetime):
            ts = m["created_at"].timestamp()
            if ts > last_seen:
                cnt += 1
    return cnt


def mark_seen(character: str):
    hist = load_messages(character)
    latest_ts = 0.0
    for m in hist[::-1]:
        dt = m.get("created_at")
        if isinstance(dt, datetime):
            latest_ts = dt.timestamp()
            break
    st.session_state.last_seen_ts[character] = max(st.session_state.last_seen_ts.get(character, 0.0), latest_ts)


def preview_text(s: str, n: int = 22) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if len(s) <= n:
        return s
    return s[:n] + "…"


# =========================
# 时间分割条
# =========================
def fmt_time_label(dt: datetime) -> str:
    try:
        local_dt = dt.astimezone(LA_TZ)
    except Exception:
        local_dt = dt

    now = datetime.now(LA_TZ)

    if local_dt.date() == now.date():
        return local_dt.strftime("%H:%M")
    return local_dt.strftime("%m/%d %H:%M")


def bucket_key(dt: datetime) -> str:
    gran = SETTINGS.get("TIME_DIVIDER_GRANULARITY", "minute")
    try:
        d = dt.astimezone(LA_TZ)
    except Exception:
        d = dt
    if gran == "5min":
        m = (d.minute // 5) * 5
        return d.replace(minute=m, second=0, microsecond=0).isoformat()
    return d.replace(second=0, microsecond=0).isoformat()


def render_time_divider(label: str):
    st.markdown(f'<div class="wx-time"><span>{_html.escape(label)}</span></div>', unsafe_allow_html=True)


# =========================
# 微信消息渲染
# =========================
def _avatar_html(avatar):
    if isinstance(avatar, str) and avatar.startswith("data:"):
        return f'<div class="wx-avatar"><img src="{avatar}" /></div>'
    safe = _html.escape(str(avatar))
    return f'<div class="wx-avatar">{safe}</div>'


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


def render_typing(character: str):
    avatar = avatar_for("assistant", character)
    html_block = f"""
    <div class="wx-row bot">
        {_avatar_html(avatar)}
        <div class="wx-bubble bot">
            <div class="typing">
                <div>对方正在输入</div>
                <div class="dots"><span></span><span></span><span></span></div>
            </div>
        </div>
    </div>
    """
    st.markdown(html_block, unsafe_allow_html=True)


# =========================
# OpenAI：聊天/教学
# =========================
def build_system_prompt(character: str, mode: str) -> str:
    base_persona = f"你在扮演{character}，性格是：{CHARACTERS[character]}。"

    if mode == "教学":
        teach_core = (
            "你现在进入【教学模式】。\n"
            "目标：像顶级家教一样帮助用户学习/解题。\n"
            "要求：先澄清题目与目标；分步骤讲解；必要时反问引导；给练习与检查点；避免空话。"
        )
        extra = SETTINGS.get("PROMPT_TEACH_EXTRA", "")
        return base_persona + "\n" + teach_core + ("\n" + extra if extra else "")

    chat_core = (
        "你现在进入【聊天模式】。\n"
        "要求：像真实微信聊天，不要AI味；句子自然；可以有情绪；不要长篇论文；避免‘作为AI’。\n"
        "输出格式：只输出一个 JSON 数组，例如 [\"消息1\",\"消息2\"]。\n"
        "规则：数组最多3条；每条1-2句话；每条尽量短（像微信）；不要在一条里塞三四句话；不要输出除 JSON 外任何文字。"
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
        presence_penalty=s_float("PRESENCE_PENALTY", 0.7),
        frequency_penalty=s_float("FREQUENCY_PENALTY", 0.25),
    )
    return resp.choices[0].message.content


def parse_chat_messages(raw: str) -> list[str]:
    raw = (raw or "").strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            msgs = []
            for x in arr:
                if isinstance(x, str):
                    t = x.strip()
                    if t:
                        msgs.append(t)
            return msgs[:3] if msgs else []
    except Exception:
        pass

    parts = [p.strip() for p in re.split(r"\n+|---+|•|\u2022", raw) if p.strip()]
    return parts[:3]


def get_ai_reply(character: str, history: list[dict], user_text: str, mode: str) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        return [f"（测试模式）{character} 收到了：{user_text}"]

    system_prompt = build_system_prompt(character, mode)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-15:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    temp = s_float("TEMP_TEACH", 0.35) if mode == "教学" else s_float("TEMP_CHAT", 1.05)
    raw = call_openai(messages, temp)

    if mode == "教学":
        return [raw.strip()]

    msgs = parse_chat_messages(raw)
    if not msgs:
        msgs = [raw.strip()] if raw.strip() else ["嗯？"]
    return msgs[:3]


def get_proactive_message(character: str, history: list[dict]) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        samples = {
            "芙宁娜": ["哼，你忙完了吗？", "我可不是在等你……只是刚好想到你。"],
            "胡桃": ["嘿嘿！我路过！", "你今天有没有发生什么离谱但好笑的事？"],
            "宵宫": ["我突然想到你！", "今天过得怎么样？要不要来点轻松话题～"],
        }
        return samples.get(character, ["我来主动开个话题：你最近在忙啥？"])

    system_prompt = build_system_prompt(character, "聊天")
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": "请主动发起微信开场。仍按 JSON 数组输出，1-2条短消息。"})
    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    msgs = parse_chat_messages(raw)
    return msgs[:2] if msgs else ["在吗？"]


# =========================
# 管理员后台（含：本周/下周码 + 重置本周码）
# =========================
if st.session_state.get("is_admin"):
    st.sidebar.divider()
    st.sidebar.subheader("管理员后台")

    w_this = current_week_id()
    w_next = next_week_id()
    code_this = ensure_week_code(w_this)
    code_next = ensure_week_code(w_next)

    with st.sidebar.expander("访问码管理", expanded=True):
        st.success(f"本周访问码（{w_this}）：{code_this}")
        st.info(f"下周访问码（{w_next}）：{code_next}")

        st.markdown("---")
        st.warning("重置后：本周旧访问码立刻失效，新访客必须使用新码。")
        confirm = st.checkbox("我确认要重置本周访问码", value=False)
        if st.button("♻️ 重置本周访问码", type="primary", disabled=(not confirm)):
            new_code = reset_week_code(w_this)
            st.success(f"已重置！新的本周访问码：{new_code}")
            st.rerun()

    st.sidebar.markdown("#### 头像管理（含 user）")
    target = st.sidebar.selectbox("选择要修改头像的对象", ["user"] + list(CHARACTERS.keys()))
    cur = get_avatars_from_db().get(target)
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
    temp_chat = st.sidebar.slider("聊天温度 Temperature", 0.0, 1.6, float(s_float("TEMP_CHAT", 1.05)), 0.05)
    temp_teach = st.sidebar.slider("教学温度 Temperature", 0.0, 1.6, float(s_float("TEMP_TEACH", 0.35)), 0.05)
    top_p = st.sidebar.slider("top_p", 0.1, 1.0, float(s_float("TOP_P", 1.0)), 0.05)
    presence = st.sidebar.slider("presence_penalty", -2.0, 2.0, float(s_float("PRESENCE_PENALTY", 0.7)), 0.1)
    freq = st.sidebar.slider("frequency_penalty", -2.0, 2.0, float(s_float("FREQUENCY_PENALTY", 0.25)), 0.1)

    st.sidebar.markdown("#### Prompt（追加）")
    prompt_chat = st.sidebar.text_area("聊天模式追加 Prompt", value=SETTINGS.get("PROMPT_CHAT_EXTRA", ""), height=120)
    prompt_teach = st.sidebar.text_area("教学模式追加 Prompt", value=SETTINGS.get("PROMPT_TEACH_EXTRA", ""), height=120)

    st.sidebar.markdown("#### 主动聊天（管理员可控）")
    proactive_enabled = st.sidebar.checkbox("启用主动聊天", value=s_bool("PROACTIVE_ENABLED", True))
    proactive_interval = st.sidebar.slider("最短间隔（分钟）", 1, 180, s_int("PROACTIVE_MIN_INTERVAL_MIN", 20))
    proactive_prob = st.sidebar.slider("触发概率（%）", 0, 100, s_int("PROACTIVE_PROB_PCT", 25))
    proactive_now = st.sidebar.button("让 TA 立刻主动说一句")

    st.sidebar.markdown("#### 时间分割条")
    gran = st.sidebar.selectbox(
        "时间分割粒度", ["minute", "5min"],
        index=0 if SETTINGS.get("TIME_DIVIDER_GRANULARITY", "minute") == "minute" else 1
    )

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
# 好友列表（微信样式：头像+名字+preview+未读点）
# =========================
def avatar_small_html(avatar):
    if isinstance(avatar, str) and avatar.startswith("data:"):
        return f'<div class="avatar"><img src="{avatar}"/></div>'
    return f'<div class="avatar">{_html.escape(str(avatar))}</div>'


def render_friend_item(character: str, active: bool):
    meta = get_latest_message_meta(character)
    pv = ""
    if meta:
        prefix = "你：" if meta.get("role") == "user" else ""
        pv = prefix + preview_text(meta.get("content", ""), 22)

    unread = get_unread_count(character)
    avatar = avatar_for("assistant", character)

    item_class = "wx-item active" if active else "wx-item"
    badge_html = ""
    if unread > 0 and (not active):
        badge_html = f'<div class="unread-badge">{unread if unread < 100 else "99+"}</div>'

    html_block = f"""
    <div class="{item_class}">
      {avatar_small_html(avatar)}
      <div class="meta">
        <div class="name">{_html.escape(character)}</div>
        <div class="preview">{_html.escape(pv)}</div>
      </div>
      {badge_html}
    </div>
    """
    return html_block


st.sidebar.divider()
st.sidebar.markdown('<div class="sidebar-title">好友列表</div>', unsafe_allow_html=True)

for ch in CHARACTERS.keys():
    is_active = (st.session_state.selected_character == ch)
    if st.sidebar.button(" ", key=f"sel_{ch}", help=f"打开 {ch}", use_container_width=True):
        st.session_state.selected_character = ch
        mark_seen(ch)
        st.rerun()

    st.sidebar.markdown(render_friend_item(ch, is_active), unsafe_allow_html=True)


# =========================
# 顶部标题 + 模式切换（普通用户可见）
# =========================
character = st.session_state.selected_character

colA, colB = st.columns([4, 1])
with colA:
    st.markdown(f'<div class="wx-title">正在和「{character}」聊天</div>', unsafe_allow_html=True)
with colB:
    mode = st.selectbox("模式", ["聊天", "教学"], index=0 if st.session_state.mode == "聊天" else 1)
    st.session_state.mode = mode
    st.markdown(f'<div class="wx-pill">模式：{mode}</div>', unsafe_allow_html=True)


# =========================
# 主动消息（管理员按钮 or 自动概率）
# =========================
history = load_messages(character)

if proactive_now:
    rate_limit(1.0, 600)
    msgs = get_proactive_message(character, history)
    for m in msgs:
        save_message(character, "assistant", m)
    st.rerun()

if st.session_state.mode == "聊天" and s_bool("PROACTIVE_ENABLED", True):
    last_key = f"last_proactive_ts_{character}"
    last_ts = st.session_state.get(last_key, 0.0)
    now_ts = time.time()
    interval_min = s_int("PROACTIVE_MIN_INTERVAL_MIN", 20)
    prob_pct = s_int("PROACTIVE_PROB_PCT", 25)
    if now_ts - last_ts >= interval_min * 60:
        st.session_state[last_key] = now_ts
        if random.randint(1, 100) <= prob_pct:
            msgs = get_proactive_message(character, history)
            for m in msgs:
                save_message(character, "assistant", m)
            st.rerun()


# =========================
# “正在输入”延迟回复机制
# =========================
def start_pending_reply(character: str, mode: str):
    delay = random.randint(1, 5)  # 1~5 秒
    st.session_state.pending = {
        "character": character,
        "mode": mode,
        "due_ts": time.time() + delay,
    }


def has_pending_for(character: str) -> bool:
    p = st.session_state.get("pending")
    return bool(p) and p.get("character") == character


def maybe_finish_pending():
    p = st.session_state.get("pending")
    if not p:
        return
    if time.time() < float(p.get("due_ts", 0)):
        return

    ch = p.get("character")
    mode = p.get("mode", "聊天")

    hist = load_messages(ch)

    last_user = None
    for m in reversed(hist):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    if not last_user:
        st.session_state.pending = None
        return

    rate_limit(1.0, 600)
    replies = get_ai_reply(ch, hist, last_user, mode)
    for r in replies:
        save_message(ch, "assistant", r)

    st.session_state.pending = None
    st.rerun()


# =========================
# 渲染聊天区（含时间分割条）
# =========================
history = load_messages(character)

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

if has_pending_for(character):
    render_typing(character)

st.markdown("</div>", unsafe_allow_html=True)

mark_seen(character)

maybe_finish_pending()

if has_pending_for(character):
    time.sleep(0.35)
    st.rerun()


# =========================
# 输入：用户发消息 -> 先入库 -> 启动 pending
# =========================
user_text = st.chat_input("输入消息…")
if user_text:
    save_message(character, "user", user_text)
    mark_seen(character)
    start_pending_reply(character, st.session_state.mode)
    st.rerun()
