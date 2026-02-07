import time
import random
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import io
import html as _html
import json
import re

import streamlit as st
from openai import OpenAI
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from PIL import Image
import pandas as pd


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
GROUP_CHAT = "群聊"
GROUP_MEMBERS = ["芙宁娜", "胡桃", "宵宫"]

DEFAULT_AVATARS = {
    "user": "🙂",
    "芙宁娜": "👑",
    "胡桃": "🦋",
    "宵宫": "🎆",
    "群聊": "👥",
}

DEFAULT_SETTINGS = {
    "TEMP_CHAT": "1.05",
    "TEMP_TEACH": "0.35",
    "TOP_P": "1.0",
    "PRESENCE_PENALTY": "0.7",
    "FREQUENCY_PENALTY": "0.25",
    "PROMPT_CHAT_EXTRA": "",
    "PROMPT_TEACH_EXTRA": "",
    "PROACTIVE_ENABLED": "1",
    "PROACTIVE_MIN_INTERVAL_MIN": "20",
    "PROACTIVE_PROB_PCT": "25",
    "TIME_DIVIDER_GRANULARITY": "minute",  # minute / 5min
    "GROUP_NAME": GROUP_CHAT,
}

DEFAULT_USAGE_LIMIT = 200


# =========================
# CSS：微信风格（✅ 不隐藏 header，iPad/手机端需要打开 sidebar）
# =========================
st.markdown(
    """
<style>
div[data-testid="stToolbar"], footer { display:none !important; }

/* 背景更像微信 */
.main { background:#ECE5DD; }

/* Sidebar */
section[data-testid="stSidebar"] { background:#F7F7F7; }
.sidebar-title { font-size:18px; font-weight:700; margin: 6px 0 10px 0; }

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
.unread-dot {
  width:10px; height:10px;
  border-radius:999px;
  background:#FF3B30;
  flex: 0 0 10px;
}
.group-avatar {
  display:grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap:2px;
  padding:4px;
  box-sizing:border-box;
}
.group-avatar .ga-item {
  width:100%;
  height:100%;
  border-radius:4px;
  overflow:hidden;
  background: rgba(0,0,0,.06);
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:12px;
}
.group-avatar .ga-item img {
  width:100%;
  height:100%;
  object-fit:cover;
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
.wx-name {
  font-size:12px;
  color: rgba(0,0,0,.55);
  margin: 0 0 2px 6px;
}
.wx-name.user {
  text-align: right;
  margin: 0 6px 2px 0;
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
# 周工具
# =========================
def current_week_id() -> str:
    now = datetime.now(LA_TZ)
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def next_week_id() -> str:
    d = datetime.now(LA_TZ) + timedelta(days=7)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


# =========================
# 访问码：默认 HMAC（不依赖 DB）
# =========================
def weekly_code_hmac(seed: str, week_id: str) -> str:
    digest = hmac.new(seed.encode("utf-8"), week_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:8].upper()


# =========================
# DB：延迟初始化（登录后才连）
# =========================
conn = None


class LocalSQLiteConnection:
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        self._session_maker = sessionmaker(bind=self.engine, future=True)

    @property
    def session(self):
        return self._session_maker()

    def query(self, sql: str, params: dict | None = None, ttl: int = 0):
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params)


def get_conn():
    global conn
    if conn is None:
        try:
            conn = st.connection("neon", type="sql")
        except Exception:
            st.warning("未检测到数据库连接配置，已切换到本地 SQLite（仅当前环境生效）。")
            conn = LocalSQLiteConnection("local_chat.db")
    return conn


def ensure_tables_safe():
    c = get_conn()
    is_sqlite = isinstance(c, LocalSQLiteConnection)
    id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGSERIAL PRIMARY KEY"
    ts_type = "TIMESTAMP" if is_sqlite else "TIMESTAMPTZ"
    ts_default = "CURRENT_TIMESTAMP"
    with c.session as s:
        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS users (
                id {id_type},
                username TEXT UNIQUE NOT NULL,
                usage_limit INTEGER NOT NULL DEFAULT {DEFAULT_USAGE_LIMIT},
                is_banned BOOLEAN NOT NULL DEFAULT 0,
                created_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS user_usage (
                user_id INTEGER NOT NULL,
                week_id TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                updated_at {ts_type} NOT NULL DEFAULT {ts_default},
                PRIMARY KEY (user_id, week_id)
            );
        """))

        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS chat_messages_v2 (
                id {id_type},
                user_id INTEGER NOT NULL,
                character TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_v2_user
            ON chat_messages_v2(user_id, character, created_at);
        """))

        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS group_messages_v2 (
                id {id_type},
                user_id INTEGER NOT NULL,
                speaker TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_group_messages_v2_user
            ON group_messages_v2(user_id, created_at);
        """))

        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id {id_type},
                session_id TEXT NOT NULL,
                character TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages(session_id, character, created_at);
        """))

        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS character_profiles (
                character TEXT PRIMARY KEY,
                avatar_data_url TEXT,
                updated_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))

        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS group_messages (
                id {id_type},
                session_id TEXT NOT NULL,
                speaker TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_group_messages_session
            ON group_messages(session_id, created_at);
        """))

        # 管理员重置本周码 override（可选）
        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS weekly_access_overrides (
                week_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                updated_at {ts_type} NOT NULL DEFAULT {ts_default}
            );
        """))
        s.commit()


def get_override_code_db(week_id: str) -> str | None:
    try:
        df = get_conn().query(
            "SELECT code FROM weekly_access_overrides WHERE week_id = :w LIMIT 1",
            params={"w": week_id},
            ttl=0
        )
        if df.empty:
            return None
        return str(df.iloc[0]["code"]).strip().upper()
    except Exception:
        return None


def reset_override_code_db(week_id: str) -> str:
    new_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    q = text("""
        INSERT INTO weekly_access_overrides (week_id, code)
        VALUES (:w, :c)
        ON CONFLICT (week_id)
        DO UPDATE SET code = EXCLUDED.code,
                      updated_at = CURRENT_TIMESTAMP;
    """)
    with get_conn().session as s:
        s.execute(q, {"w": week_id, "c": new_code})
        s.commit()
    return new_code


def effective_weekly_code(seed: str, week_id: str) -> str:
    ov = get_override_code_db(week_id)
    return ov if ov else weekly_code_hmac(seed, week_id)


# =========================
# 用户
# =========================
def normalize_username(raw: str) -> str | None:
    name = (raw or "").strip()
    if not name:
        return None
    if len(name) > 32:
        return None
    return name


def get_user_by_name(username: str):
    df = get_conn().query(
        "SELECT id, username, usage_limit, is_banned FROM users WHERE username = :u LIMIT 1",
        params={"u": username},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def create_user(username: str):
    q = text("""
        INSERT INTO users (username, usage_limit, is_banned)
        VALUES (:u, :limit, 0)
        ON CONFLICT (username) DO NOTHING
    """)
    with get_conn().session as s:
        s.execute(q, {"u": username, "limit": DEFAULT_USAGE_LIMIT})
        s.commit()
    return get_user_by_name(username)


def set_user_banned(user_id: int, banned: bool):
    q = text("UPDATE users SET is_banned = :b WHERE id = :uid")
    with get_conn().session as s:
        s.execute(q, {"uid": user_id, "b": 1 if banned else 0})
        s.commit()


def update_user_limit(user_id: int, limit: int):
    q = text("UPDATE users SET usage_limit = :l WHERE id = :uid")
    with get_conn().session as s:
        s.execute(q, {"uid": user_id, "l": limit})
        s.commit()


def get_user_summary(user_id: int):
    df = get_conn().query(
        "SELECT id, username, usage_limit, is_banned FROM users WHERE id = :uid LIMIT 1",
        params={"uid": user_id},
        ttl=0,
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_user_usage(user_id: int, week_id: str) -> int:
    df = get_conn().query(
        "SELECT used FROM user_usage WHERE user_id = :uid AND week_id = :w LIMIT 1",
        params={"uid": user_id, "w": week_id},
        ttl=0,
    )
    if df.empty:
        q = text("""
            INSERT INTO user_usage (user_id, week_id, used)
            VALUES (:uid, :w, 0)
            ON CONFLICT (user_id, week_id) DO NOTHING
        """)
        with get_conn().session as s:
            s.execute(q, {"uid": user_id, "w": week_id})
            s.commit()
        return 0
    return int(df.iloc[0]["used"])


def consume_usage(user_id: int, week_id: str, limit: int) -> tuple[bool, int]:
    used = get_user_usage(user_id, week_id)
    if used >= limit:
        return False, used
    new_used = used + 1
    q = text("""
        INSERT INTO user_usage (user_id, week_id, used)
        VALUES (:uid, :w, :used)
        ON CONFLICT (user_id, week_id)
        DO UPDATE SET used = EXCLUDED.used,
                      updated_at = CURRENT_TIMESTAMP
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": user_id, "w": week_id, "used": new_used})
        s.commit()
    return True, new_used


def get_weekly_code_for_login(seed: str, week_id: str) -> str:
    try:
        return effective_weekly_code(seed, week_id)
    except Exception:
        return weekly_code_hmac(seed, week_id)


# =========================
# 登录/注册：主页面 + sidebar 都能输入
# =========================
def require_login():
    if st.session_state.get("authed"):
        return

    seed = st.secrets.get("ACCESS_SEED", "")
    admin_key = st.secrets.get("ADMIN_KEY", "")

    if not seed:
        st.error("缺少 ACCESS_SEED（请在 Secrets 里配置）。")
        st.stop()
    if not admin_key:
        st.error("缺少 ADMIN_KEY（请在 Secrets 里配置管理员密码）。")
        st.stop()

    week_id = current_week_id()
    weekly_code = get_weekly_code_for_login(seed, week_id)

    st.sidebar.subheader("账号登录 / 注册")
    username_sb = st.sidebar.text_input("用户名", key="login_user_sb")
    code_in_sb = st.sidebar.text_input("本周访问码", type="password", key="login_code_sb")
    admin_in_sb = st.sidebar.text_input("管理员密钥（可选）", type="password", key="login_admin_sb")
    login_sb = st.sidebar.button("登录", type="primary", key="login_submit_sb")
    register_sb = st.sidebar.button("注册", key="register_submit_sb")

    st.markdown(
        """
        <div style="max-width:680px;margin:40px auto 0 auto;
                    padding:18px 18px;border-radius:14px;
                    background:rgba(255,255,255,.75);
                    border:1px solid rgba(0,0,0,.06);">
          <div style="font-size:18px;font-weight:800;margin-bottom:8px;">登录 / 注册</div>
          <div style="font-size:13px;color:rgba(0,0,0,.55);margin-bottom:12px;">
            使用“用户名 + 本周访问码”注册或登录；管理员可用密钥直接登录。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        with st.form("login_form_main", clear_on_submit=False):
            username_in = st.text_input("用户名", key="login_user_main")
            code_in = st.text_input("本周访问码", type="password", key="login_code_main")
            admin_in = st.text_input("管理员密钥（可选）", type="password", key="login_admin_main")
            submitted = st.form_submit_button("登录", use_container_width=True)

    with register_tab:
        with st.form("register_form_main", clear_on_submit=False):
            username_reg = st.text_input("用户名", key="register_user_main")
            code_reg = st.text_input("本周访问码", type="password", key="register_code_main")
            admin_reg = st.text_input("管理员密钥（可选）", type="password", key="register_admin_main")
            submitted_reg = st.form_submit_button("注册", use_container_width=True)

    def handle_login(username_val: str, code_val: str, admin_val: str, is_register: bool):
        name = normalize_username(username_val)
        if not name:
            st.error("请输入有效用户名（最多 32 个字符）。")
            return
        ok_weekly = bool(code_val) and (code_val.strip().upper() == weekly_code.upper())
        ok_admin = bool(admin_val) and (admin_val.strip() == admin_key)
        if not (ok_weekly or ok_admin):
            st.error("访问码或管理员密钥不正确。")
            return
        user = get_user_by_name(name)
        if is_register:
            if user:
                st.error("用户名已存在，请直接登录。")
                return
            user = create_user(name)
        if not user:
            st.error("用户不存在，请先注册。")
            return
        if bool(user.get("is_banned")):
            st.error("账号已被封禁，请联系管理员。")
            return
        st.session_state.authed = True
        st.session_state.is_admin = bool(ok_admin)
        st.session_state.user_id = int(user["id"])
        st.session_state.username = str(user["username"])
        st.rerun()

    if submitted or login_sb:
        handle_login(username_in or username_sb, code_in or code_in_sb, admin_in or admin_in_sb, False)
    if submitted_reg or register_sb:
        handle_login(username_reg or username_sb, code_reg or code_in_sb, admin_reg or admin_in_sb, True)

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


def handle_usage_limit_blocked(character: str, is_group: bool):
    message = "已欠费：AI 使用量已达上限，请联系管理员。"
    if is_group:
        save_group_message("系统", "assistant", message)
        mark_group_seen()
    else:
        save_message(character, "assistant", message)
        mark_seen(character)
    st.warning(message)


def try_consume_usage() -> bool:
    user_summary = get_user_summary(st.session_state.user_id)
    if not user_summary:
        return False
    limit = int(user_summary.get("usage_limit") or DEFAULT_USAGE_LIMIT)
    ok, _used = consume_usage(st.session_state.user_id, current_week_id(), limit)
    return ok


# 初始化 DB
try:
    ensure_tables_safe()
except Exception as e:
    st.error("数据库连接失败（Neon）。请点右下角 Manage app → Logs 看真实原因。")
    st.exception(e)
    st.stop()

# 先登录
require_login()


# 默认模式
if "mode" not in st.session_state:
    st.session_state.mode = "聊天"

# 色色模式（仅单聊）
if "sexy_mode" not in st.session_state:
    st.session_state.sexy_mode = {ch: False for ch in CHARACTERS.keys()}

# 默认选中角色
if "selected_character" not in st.session_state:
    st.session_state.selected_character = list(CHARACTERS.keys())[0]

# 未读
if "last_seen_ts" not in st.session_state:
    st.session_state.last_seen_ts = {ch: 0.0 for ch in CHARACTERS.keys()}
    st.session_state.last_seen_ts[GROUP_CHAT] = 0.0
if GROUP_CHAT not in st.session_state.last_seen_ts:
    st.session_state.last_seen_ts[GROUP_CHAT] = 0.0

# 登录后随机触发一次主动聊天（1-5分钟）
if "random_chat_due_ts" not in st.session_state:
    st.session_state.random_chat_due_ts = time.time() + random.randint(60, 300)
if "random_chat_fired" not in st.session_state:
    st.session_state.random_chat_fired = False
if "group_random_due_ts" not in st.session_state:
    st.session_state.group_random_due_ts = time.time() + random.randint(20, 120)
if "group_random_fired" not in st.session_state:
    st.session_state.group_random_fired = False
if "group_pending" not in st.session_state:
    st.session_state.group_pending = []


# =========================
# 当前用户信息 & Usage
# =========================
user_summary = get_user_summary(st.session_state.user_id)
if not user_summary:
    st.error("用户信息缺失，请重新登录。")
    st.session_state.authed = False
    st.rerun()
current_week = current_week_id()
current_used = get_user_usage(st.session_state.user_id, current_week)
current_limit = int(user_summary.get("usage_limit") or DEFAULT_USAGE_LIMIT)

st.sidebar.markdown(f"**当前用户：{_html.escape(str(user_summary.get('username', '')))}**")
st.sidebar.markdown(f"AI 使用量：{current_used}/{current_limit}（{current_week}）")


# =========================
# Settings（DB）
# =========================
def load_settings() -> dict:
    df = get_conn().query("SELECT key, value FROM app_settings", ttl=0)
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
                      updated_at = CURRENT_TIMESTAMP;
    """)
    with get_conn().session as s:
        s.execute(q, {"k": key, "v": value})
        s.commit()


SETTINGS = load_settings()
GROUP_DISPLAY_NAME = SETTINGS.get("GROUP_NAME", GROUP_CHAT)


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

    # EXIF 旋转修正
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

    has_alpha = (img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info))

    if has_alpha:
        out = io.BytesIO()
        img_rgba = img.convert("RGBA")
        img_rgba.save(out, format="PNG", optimize=True)
        data = out.getvalue()

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


def build_teaching_attachments(uploaded_files: list) -> list[dict]:
    attachments: list[dict] = []
    if not uploaded_files:
        return attachments
    text_limit = 6000
    for up in uploaded_files:
        mime = (up.type or "").lower()
        name = up.name or "附件"
        data = up.getvalue()
        if mime.startswith("image/"):
            b64 = base64.b64encode(data).decode("utf-8")
            attachments.append(
                {"type": "image", "name": name, "data_url": f"data:{mime};base64,{b64}"}
            )
            continue
        try:
            text = data.decode("utf-8", errors="ignore").strip()
        except Exception:
            text = ""
        if text:
            if len(text) > text_limit:
                text = text[:text_limit] + "\n...（内容过长已截断）"
            attachments.append({"type": "text", "name": name, "text": f"【文件：{name}】\n{text}"})
        else:
            attachments.append({"type": "text", "name": name, "text": f"【文件：{name}】（无法解析为文本）"})
    return attachments


def upsert_avatar(key_name: str, avatar_data_url: str | None):
    q = text("""
        INSERT INTO character_profiles (character, avatar_data_url)
        VALUES (:ch, :url)
        ON CONFLICT (character)
        DO UPDATE SET avatar_data_url = EXCLUDED.avatar_data_url,
                      updated_at = CURRENT_TIMESTAMP;
    """)
    with get_conn().session as s:
        s.execute(q, {"ch": key_name, "url": avatar_data_url})
        s.commit()


def get_avatars_from_db() -> dict:
    df = get_conn().query("SELECT character, avatar_data_url FROM character_profiles", ttl=0)
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
def load_messages(character: str, user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = """
        SELECT id, role, content, created_at
        FROM chat_messages_v2
        WHERE user_id = :uid AND character = :ch
        ORDER BY created_at
    """
    df = get_conn().query(q, params={"uid": uid, "ch": character}, ttl=0)
    recs = df.to_dict("records")
    for r in recs:
        ca = r.get("created_at")
        if isinstance(ca, str):
            try:
                r["created_at"] = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            except Exception:
                r["created_at"] = None
    return recs


def save_message(character: str, role: str, content: str, user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = text("""
        INSERT INTO chat_messages_v2 (user_id, character, role, content)
        VALUES (:uid, :ch, :role, :content)
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": uid, "ch": character, "role": role, "content": content})
        s.commit()


def get_latest_message_meta(character: str, user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = """
        SELECT id, role, content, created_at
        FROM chat_messages_v2
        WHERE user_id = :uid AND character = :ch
        ORDER BY created_at DESC
        LIMIT 1
    """
    df = get_conn().query(q, params={"uid": uid, "ch": character}, ttl=0)
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


def ensure_sexy_mode_entry(character: str):
    if "sexy_mode" not in st.session_state:
        st.session_state.sexy_mode = {}
    if character not in st.session_state.sexy_mode:
        st.session_state.sexy_mode[character] = False


def is_sexy_mode(character: str) -> bool:
    ensure_sexy_mode_entry(character)
    return bool(st.session_state.sexy_mode.get(character))


def set_sexy_mode(character: str, enabled: bool):
    ensure_sexy_mode_entry(character)
    st.session_state.sexy_mode[character] = enabled


def preview_text(s: str, n: int = 22) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s if len(s) <= n else (s[:n] + "…")


# =========================
# 群聊：消息读写
# =========================
def load_group_messages(user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = """
        SELECT id, speaker, role, content, created_at
        FROM group_messages_v2
        WHERE user_id = :uid
        ORDER BY created_at
    """
    df = get_conn().query(q, params={"uid": uid}, ttl=0)
    recs = df.to_dict("records")
    for r in recs:
        ca = r.get("created_at")
        if isinstance(ca, str):
            try:
                r["created_at"] = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            except Exception:
                r["created_at"] = None
    return recs


def save_group_message(speaker: str, role: str, content: str, user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = text("""
        INSERT INTO group_messages_v2 (user_id, speaker, role, content)
        VALUES (:uid, :sp, :role, :content)
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": uid, "sp": speaker, "role": role, "content": content})
        s.commit()


def delete_messages(message_ids: list[int], user_id: int | None = None):
    if not message_ids:
        return
    uid = user_id if user_id is not None else st.session_state.user_id
    params = {"uid": uid}
    placeholders = []
    for idx, mid in enumerate(message_ids):
        key = f"id_{idx}"
        params[key] = int(mid)
        placeholders.append(f":{key}")
    q = text(f"""
        DELETE FROM chat_messages_v2
        WHERE user_id = :uid AND id IN ({", ".join(placeholders)})
    """)
    with get_conn().session as s:
        s.execute(q, params)
        s.commit()


def delete_group_messages(message_ids: list[int], user_id: int | None = None):
    if not message_ids:
        return
    uid = user_id if user_id is not None else st.session_state.user_id
    params = {"uid": uid}
    placeholders = []
    for idx, mid in enumerate(message_ids):
        key = f"id_{idx}"
        params[key] = int(mid)
        placeholders.append(f":{key}")
    q = text(f"""
        DELETE FROM group_messages_v2
        WHERE user_id = :uid AND id IN ({", ".join(placeholders)})
    """)
    with get_conn().session as s:
        s.execute(q, params)
        s.commit()


def get_group_latest_message_meta(user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = """
        SELECT id, speaker, role, content, created_at
        FROM group_messages_v2
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 1
    """
    df = get_conn().query(q, params={"uid": uid}, ttl=0)
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


def get_group_unread_count() -> int:
    last_seen = st.session_state.last_seen_ts.get(GROUP_CHAT, 0.0)
    hist = load_group_messages()
    cnt = 0
    for m in hist:
        if m.get("role") == "assistant" and isinstance(m.get("created_at"), datetime):
            ts = m["created_at"].timestamp()
            if ts > last_seen:
                cnt += 1
    return cnt


def mark_group_seen():
    hist = load_group_messages()
    latest_ts = 0.0
    for m in hist[::-1]:
        dt = m.get("created_at")
        if isinstance(dt, datetime):
            latest_ts = dt.timestamp()
            break
    st.session_state.last_seen_ts[GROUP_CHAT] = max(st.session_state.last_seen_ts.get(GROUP_CHAT, 0.0), latest_ts)


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


def render_group_message(role: str, speaker: str, content: str):
    is_user = (role == "user")
    avatar = avatar_for("user" if is_user else "assistant", speaker)
    safe_text = _html.escape(content).replace("\n", "<br>")
    safe_name = "你" if is_user else _html.escape(speaker)

    if is_user:
        html_block = f"""
        <div class="wx-row user">
            <div>
                <div class="wx-name user">{safe_name}</div>
                <div class="wx-bubble user">{safe_text}</div>
            </div>
            {_avatar_html(avatar)}
        </div>
        """
    else:
        html_block = f"""
        <div class="wx-row bot">
            {_avatar_html(avatar)}
            <div>
                <div class="wx-name">{safe_name}</div>
                <div class="wx-bubble bot">{safe_text}</div>
            </div>
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


def render_history_manager(current_character: str):
    st.sidebar.divider()
    with st.sidebar.expander("聊天记录管理", expanded=False):
        if current_character == GROUP_CHAT:
            history_rows = load_group_messages()
        else:
            history_rows = load_messages(current_character)
        if not history_rows:
            st.sidebar.caption("暂无聊天记录。")
            return
        df = pd.DataFrame(history_rows)
        df["删除"] = False
        display_cols = [c for c in ["id", "created_at", "role", "speaker", "content", "删除"] if c in df.columns]
        editor_df = st.sidebar.data_editor(
            df[display_cols],
            use_container_width=True,
            height=240,
            key=f"history_editor_{current_character}",
            column_config={"删除": st.column_config.CheckboxColumn("删除")},
            hide_index=True,
        )
        if st.sidebar.button("删除选中消息", key=f"delete_history_{current_character}"):
            delete_ids = editor_df.loc[editor_df["删除"] == True, "id"].tolist()  # noqa: E712
            if delete_ids:
                if current_character == GROUP_CHAT:
                    delete_group_messages(delete_ids)
                else:
                    delete_messages(delete_ids)
                st.sidebar.success("已删除选中消息。")
                st.rerun()
            else:
                st.sidebar.info("未选择要删除的消息。")


# =========================
# OpenAI：聊天/教学
# =========================
def build_system_prompt(character: str, mode: str, sexy_mode: bool = False) -> str:
    base_persona = f"你在扮演{character}，性格是：{CHARACTERS[character]}。"

    if mode == "教学":
        teach_core = (
            "你现在进入【教学模式】。\n"
            "目标：像顶级家教一样帮助用户学习/解题。\n"
            "要求：先澄清题目与目标；分步骤讲解；必要时反问引导；给练习与检查点；避免空话。"
        )
        extra = SETTINGS.get("PROMPT_TEACH_EXTRA", "")
        return base_persona + "\n" + teach_core + ("\n" + extra if extra else "")

    sexy_core = ""
    if sexy_mode:
        sexy_core = (
            "\n你现在进入【色色模式】。\n"
            "允许R18+成人话题，关系更亲密、语气更暧昧开放。\n"
            "保持双方自愿与尊重，不要越界到不适内容。"
        )

    chat_core = (
        "你现在进入【聊天模式】。\n"
        "要求：像真实微信聊天，不要AI味；句子自然；可以有情绪；不要长篇论文；避免‘作为AI’。\n"
        "输出格式：只输出一个 JSON 数组，例如 [\"消息1\",\"消息2\"]。\n"
        "规则：数组1-5条（条数随机）；每条1-2句话；每条尽量短（像微信）；不要输出除 JSON 外任何文字。"
    )
    extra = SETTINGS.get("PROMPT_CHAT_EXTRA", "")
    return base_persona + "\n" + chat_core + sexy_core + ("\n" + extra if extra else "")


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


def parse_chat_messages(raw: str, max_messages: int = 5) -> list[str]:
    raw = (raw or "").strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            msgs = [x.strip() for x in arr if isinstance(x, str) and x.strip()]
            return msgs[:max_messages]
    except Exception:
        pass
    parts = [p.strip() for p in re.split(r"\n+|---+|•|\u2022", raw) if p.strip()]
    return parts[:max_messages]


def pick_random_messages(messages: list[str], min_count: int = 1, max_count: int = 5) -> list[str]:
    if not messages:
        return []
    target = random.randint(min_count, max_count)
    if len(messages) <= target:
        return messages
    return messages[:target]


def get_ai_reply(
    character: str,
    history: list[dict],
    user_text: str,
    mode: str,
    sexy_mode: bool = False,
    attachments: list[dict] | None = None,
) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        return [f"（测试模式）{character} 收到了：{user_text}"]

    system_prompt = build_system_prompt(character, mode, sexy_mode=sexy_mode)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-15:]:
        messages.append({"role": m["role"], "content": m["content"]})
    if attachments:
        content_parts: list[dict] = [{"type": "text", "text": user_text}]
        for item in attachments:
            if item.get("type") == "image":
                if item.get("name"):
                    content_parts.append({"type": "text", "text": f"【图片：{item.get('name')}】"})
                content_parts.append(
                    {"type": "image_url", "image_url": {"url": item.get("data_url", "")}}
                )
            elif item.get("type") == "text":
                content_parts.append({"type": "text", "text": item.get("text", "")})
        messages.append({"role": "user", "content": content_parts})
    else:
        messages.append({"role": "user", "content": user_text})

    temp = s_float("TEMP_TEACH", 0.35) if mode == "教学" else s_float("TEMP_CHAT", 1.05)
    raw = call_openai(messages, temp)

    if mode == "教学":
        return [raw.strip()]

    msgs = pick_random_messages(parse_chat_messages(raw))
    return msgs if msgs else [raw.strip() or "嗯？"]


def build_group_system_prompt(character: str) -> str:
    base = build_system_prompt(character, "聊天")
    group_hint = (
        "\n你在一个群聊里，成员有：芙宁娜、胡桃、宵宫、用户。"
        f"你是{character}，只代表自己发言，不要替别人说话。"
        "回复仍按 JSON 数组输出。"
    )
    return base + group_hint


def get_group_ai_reply(character: str, history: list[dict]) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        return [f"（测试模式）{character} 说：收到~"]

    system_prompt = build_group_system_prompt(character)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-20:]:
        speaker = m.get("speaker", "")
        content = m.get("content", "")
        if speaker == "user":
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "assistant", "content": f"{speaker}：{content}"})
    messages.append({"role": "user", "content": "请在群聊中回复上一条消息。"})

    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    msgs = parse_chat_messages(raw)
    return msgs if msgs else [raw.strip() or "嗯？"]


def get_group_proactive_message(character: str, history: list[dict]) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        return [f"（测试模式）{character} 先说一句。"]
    system_prompt = build_group_system_prompt(character)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-12:]:
        speaker = m.get("speaker", "")
        content = m.get("content", "")
        if speaker == "user":
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "assistant", "content": f"{speaker}：{content}"})
    messages.append({"role": "user", "content": "请你在群聊里先开个话题，1-2条短消息。"})
    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    msgs = parse_chat_messages(raw)
    return msgs[:2] if msgs else ["在吗？"]


def get_proactive_message(character: str, history: list[dict], sexy_mode: bool = False) -> list[str]:
    system_prompt = build_system_prompt(character, "聊天", sexy_mode=sexy_mode)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-10:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": "请主动发起微信开场。仍按 JSON 数组输出，1-2条短消息。"})
    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    msgs = parse_chat_messages(raw)
    return msgs[:2] if msgs else ["在吗？"]


# =========================
# 管理员后台（登录后可用 DB override）
# =========================
if st.session_state.get("is_admin"):
    st.sidebar.divider()
    st.sidebar.subheader("管理员后台")

    seed = st.secrets.get("ACCESS_SEED", "")
    w_this = current_week_id()
    w_next = next_week_id()

    # ✅ 登录后可以读 DB override
    code_this = effective_weekly_code(seed, w_this)
    code_next = effective_weekly_code(seed, w_next)

    with st.sidebar.expander("访问码管理", expanded=True):
        st.success(f"本周访问码（{w_this}）：{code_this}")
        st.info(f"下周访问码（{w_next}）：{code_next}")

        st.markdown("---")
        st.caption("重置=写入 DB override（DB 可用时生效）。")
        confirm = st.checkbox("我确认要重置本周访问码", value=False)
        if st.button("♻️ 重置本周访问码", type="primary", disabled=(not confirm)):
            try:
                new_code = reset_override_code_db(w_this)
                st.success(f"已重置！新的本周访问码：{new_code}")
                st.rerun()
            except Exception as e:
                st.error("重置失败：数据库不可用。")
                st.exception(e)

    with st.sidebar.expander("用户管理", expanded=False):
        users_df = get_conn().query(
            "SELECT id, username, usage_limit, is_banned FROM users ORDER BY username",
            ttl=0,
        )
        if users_df.empty:
            st.sidebar.info("暂无用户。")
        else:
            user_choices = users_df["username"].tolist()
            selected_user = st.sidebar.selectbox("选择用户", user_choices)
            selected_row = users_df[users_df["username"] == selected_user].iloc[0].to_dict()
            selected_user_id = int(selected_row["id"])
            selected_limit = int(selected_row.get("usage_limit") or DEFAULT_USAGE_LIMIT)
            selected_banned = bool(selected_row.get("is_banned"))

            st.sidebar.caption(
                f"状态：{'已封禁' if selected_banned else '正常'} | Limit：{selected_limit}"
            )
            usage_week = current_week_id()
            usage_used = get_user_usage(selected_user_id, usage_week)
            st.sidebar.caption(f"本周使用量：{usage_used}/{selected_limit}（{usage_week}）")

            new_limit = st.sidebar.number_input(
                "调整 AI 使用上限",
                min_value=0,
                max_value=9999,
                value=selected_limit,
                step=10,
            )
            if st.sidebar.button("保存使用上限"):
                update_user_limit(selected_user_id, int(new_limit))
                st.sidebar.success("已更新上限。")
                st.rerun()

            if selected_banned:
                if st.sidebar.button("解除封号"):
                    set_user_banned(selected_user_id, False)
                    st.sidebar.success("已解除封号。")
                    st.rerun()
            else:
                if st.sidebar.button("封号"):
                    set_user_banned(selected_user_id, True)
                    st.sidebar.success("已封号。")
                    st.rerun()

            st.sidebar.markdown("**查看聊天记录**")
            view_type = st.sidebar.selectbox("记录类型", ["单聊", "群聊"])
            if view_type == "单聊":
                view_character = st.sidebar.selectbox("角色", list(CHARACTERS.keys()))
                history_rows = load_messages(view_character, user_id=selected_user_id)
            else:
                history_rows = load_group_messages(user_id=selected_user_id)

            if history_rows:
                show_df = pd.DataFrame(history_rows)
                cols = ["created_at", "role", "speaker", "content", "character"]
                existing_cols = [c for c in cols if c in show_df.columns]
                st.sidebar.dataframe(show_df[existing_cols], use_container_width=True, height=240)
            else:
                st.sidebar.caption("暂无聊天记录。")

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
# 好友列表（微信样式：头像+名字+preview+未读）
# =========================
def avatar_small_html(avatar):
    if isinstance(avatar, str) and avatar.startswith("data:"):
        return f'<div class="avatar"><img src="{avatar}"/></div>'
    return f'<div class="avatar">{_html.escape(str(avatar))}</div>'


def group_avatar_html(members: list[str]):
    items = []
    for name in members[:4]:
        avatar = avatar_for("assistant", name)
        if isinstance(avatar, str) and avatar.startswith("data:"):
            items.append(f'<div class="ga-item"><img src="{avatar}"/></div>')
        else:
            items.append(f'<div class="ga-item">{_html.escape(str(avatar))}</div>')
    while len(items) < 4:
        items.append('<div class="ga-item"></div>')
    return f'<div class="avatar group-avatar">{"".join(items)}</div>'


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
        badge_html = '<div class="unread-dot"></div>'

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


def render_group_item(active: bool):
    meta = get_group_latest_message_meta()
    pv = ""
    if meta:
        speaker = meta.get("speaker", "")
        prefix = "你：" if speaker == "user" else f"{speaker}："
        pv = prefix + preview_text(meta.get("content", ""), 22)
    unread = get_group_unread_count()
    avatar = group_avatar_html(GROUP_MEMBERS)
    item_class = "wx-item active" if active else "wx-item"
    badge_html = ""
    if unread > 0 and (not active):
        badge_html = '<div class="unread-dot"></div>'
    html_block = f"""
    <div class="{item_class}">
      {avatar}
      <div class="meta">
        <div class="name">{_html.escape(GROUP_DISPLAY_NAME)}</div>
        <div class="preview">{_html.escape(pv)}</div>
      </div>
      {badge_html}
    </div>
    """
    return html_block


st.sidebar.divider()
st.sidebar.markdown('<div class="sidebar-title">好友列表</div>', unsafe_allow_html=True)

is_group_active = (st.session_state.selected_character == GROUP_CHAT)
if st.sidebar.button(" ", key="sel_group", help=f"打开 {GROUP_DISPLAY_NAME}", use_container_width=True):
    st.session_state.selected_character = GROUP_CHAT
    st.session_state.mode = GROUP_CHAT
    mark_group_seen()
    st.rerun()
st.sidebar.markdown(render_group_item(is_group_active), unsafe_allow_html=True)

for ch in CHARACTERS.keys():
    is_active = (st.session_state.selected_character == ch)
    if st.sidebar.button(" ", key=f"sel_{ch}", help=f"打开 {ch}", use_container_width=True):
        st.session_state.selected_character = ch
        if st.session_state.mode == GROUP_CHAT:
            st.session_state.mode = "聊天"
        mark_seen(ch)
        st.rerun()
    st.sidebar.markdown(render_friend_item(ch, is_active), unsafe_allow_html=True)


# =========================
# 顶部标题 + 模式切换
# =========================
character = st.session_state.selected_character

colA, colB = st.columns([4, 1])
with colA:
    if character == GROUP_CHAT or st.session_state.mode == GROUP_CHAT:
        st.markdown(f'<div class="wx-title">{_html.escape(GROUP_DISPLAY_NAME)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="wx-title">{_html.escape(character)}</div>', unsafe_allow_html=True)
with colB:
    mode_options = ["聊天", "教学", GROUP_CHAT]
    current_mode = st.session_state.mode if st.session_state.mode in mode_options else "聊天"
    mode = st.selectbox("模式", mode_options, index=mode_options.index(current_mode))
    st.session_state.mode = mode
    if character != GROUP_CHAT and is_sexy_mode(character):
        st.markdown('<div class="wx-pill">模式：色色</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="wx-pill">模式：{mode}</div>', unsafe_allow_html=True)

if st.session_state.mode == GROUP_CHAT:
    st.session_state.selected_character = GROUP_CHAT
    character = GROUP_CHAT
elif st.session_state.selected_character == GROUP_CHAT:
    st.session_state.mode = GROUP_CHAT
    character = GROUP_CHAT
elif is_sexy_mode(character):
    st.session_state.mode = "聊天"

if character == GROUP_CHAT:
    GROUP_DISPLAY_NAME = SETTINGS.get("GROUP_NAME", GROUP_CHAT)

render_history_manager(character)


def maybe_trigger_random_chat():
    if st.session_state.get("random_chat_fired"):
        return
    due_ts = st.session_state.get("random_chat_due_ts")
    if not due_ts or time.time() < float(due_ts):
        return
    starter = random.choice(list(CHARACTERS.keys()))
    history = load_messages(starter)
    msgs = get_proactive_message(starter, history, sexy_mode=is_sexy_mode(starter))
    for m in msgs:
        save_message(starter, "assistant", m)
    st.session_state.random_chat_fired = True
    st.rerun()


def queue_group_messages(speaker: str, messages: list[str], start_delay: int | None = None):
    delay = start_delay if start_delay is not None else random.randint(2, 5)
    for msg in messages:
        st.session_state.group_pending.append(
            {"speaker": speaker, "role": "assistant", "content": msg, "due_ts": time.time() + delay}
        )
        delay += random.randint(2, 5)


def maybe_trigger_group_random_chat():
    if st.session_state.get("group_random_fired"):
        return
    due_ts = st.session_state.get("group_random_due_ts")
    if not due_ts or time.time() < float(due_ts):
        return
    starter = random.choice(GROUP_MEMBERS)
    history = load_group_messages()
    msgs = get_group_proactive_message(starter, history)
    queue_group_messages(starter, msgs, start_delay=random.randint(2, 6))
    st.session_state.group_random_fired = True


def process_group_pending():
    pending = st.session_state.get("group_pending", [])
    if not pending:
        return
    now_ts = time.time()
    ready = [p for p in pending if p.get("due_ts", 0) <= now_ts]
    if not ready:
        return
    remaining = [p for p in pending if p.get("due_ts", 0) > now_ts]
    for item in sorted(ready, key=lambda x: x.get("due_ts", 0)):
        save_group_message(item["speaker"], item.get("role", "assistant"), item["content"])
    st.session_state.group_pending = remaining


# =========================
# 主动消息（管理员按钮 or 自动概率）
# =========================
if character == GROUP_CHAT:
    history = load_group_messages()
else:
    history = load_messages(character)

maybe_trigger_random_chat()
maybe_trigger_group_random_chat()
process_group_pending()

if character != GROUP_CHAT and proactive_now:
    rate_limit(1.0, 600)
    msgs = get_proactive_message(character, history, sexy_mode=is_sexy_mode(character))
    for m in msgs:
        save_message(character, "assistant", m)
    st.rerun()

if character != GROUP_CHAT and st.session_state.mode == "聊天" and s_bool("PROACTIVE_ENABLED", True):
    last_key = f"last_proactive_ts_{character}"
    last_ts = st.session_state.get(last_key, 0.0)
    now_ts = time.time()
    interval_min = s_int("PROACTIVE_MIN_INTERVAL_MIN", 20)
    prob_pct = s_int("PROACTIVE_PROB_PCT", 25)
    if now_ts - last_ts >= interval_min * 60:
        st.session_state[last_key] = now_ts
        if random.randint(1, 100) <= prob_pct:
            msgs = get_proactive_message(character, history, sexy_mode=is_sexy_mode(character))
            for m in msgs:
                save_message(character, "assistant", m)
            st.rerun()


# =========================
# “正在输入”延迟回复
# =========================
def start_pending_reply(character: str, mode: str, attachments: list[dict] | None = None):
    delay = random.randint(1, 5)
    st.session_state.pending = {
        "character": character,
        "mode": mode,
        "due_ts": time.time() + delay,
        "attachments": attachments or [],
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
    attachments = p.get("attachments", [])
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
    replies = get_ai_reply(ch, hist, last_user, mode, sexy_mode=is_sexy_mode(ch), attachments=attachments)
    for r in replies:
        save_message(ch, "assistant", r)

    st.session_state.pending = None
    st.rerun()


# =========================
# 渲染聊天区
# =========================
if character == GROUP_CHAT:
    history = load_group_messages()
else:
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
    if character == GROUP_CHAT:
        render_group_message(msg.get("role", "assistant"), msg.get("speaker", ""), msg.get("content", ""))
    else:
        render_message(msg["role"], character, msg["content"])

if character != GROUP_CHAT and has_pending_for(character):
    render_typing(character)

st.markdown("</div>", unsafe_allow_html=True)

if character == GROUP_CHAT:
    mark_group_seen()
else:
    mark_seen(character)
    maybe_finish_pending()

if character != GROUP_CHAT and has_pending_for(character):
    time.sleep(0.35)
    st.rerun()
if character == GROUP_CHAT and st.session_state.get("group_pending"):
    time.sleep(0.35)
    st.rerun()


# =========================
# 教学模式附件（图片/文件）
# =========================
teach_uploads = None
if character != GROUP_CHAT and st.session_state.mode == "教学":
    teach_uploads = st.file_uploader(
        "教学模式附件（图片/文件，可多选）",
        type=["png", "jpg", "jpeg", "gif", "txt", "md", "csv", "json"],
        accept_multiple_files=True,
        key="teach_uploader",
        help="图片会直接传给模型；文本类文件会作为文字内容附加。",
    )


# =========================
# 输入：用户发消息
# =========================
user_text = st.chat_input("输入消息…")
if user_text:
    if character == GROUP_CHAT:
        rate_limit(1.0, 600)
        save_group_message("user", "user", user_text)
        mark_group_seen()
        if not try_consume_usage():
            handle_usage_limit_blocked(character, True)
            st.rerun()
        history = load_group_messages()
        responders = random.sample(GROUP_MEMBERS, k=len(GROUP_MEMBERS))
        delay_seed = random.randint(2, 5)
        for responder in responders:
            replies = get_group_ai_reply(responder, history)
            queue_group_messages(responder, replies, start_delay=delay_seed)
            for reply in replies:
                history.append({"speaker": responder, "role": "assistant", "content": reply})
            delay_seed += random.randint(2, 5)
        st.rerun()
    else:
        normalized = user_text.strip()
        if normalized in ("打开色色模式", "关闭色色模式"):
            set_sexy_mode(character, normalized == "打开色色模式")
            save_message(character, "user", user_text)
            reply = "已开启色色模式。" if normalized == "打开色色模式" else "已关闭色色模式。"
            save_message(character, "assistant", reply)
            mark_seen(character)
            st.session_state.mode = "聊天"
            st.rerun()
        attachments = []
        if st.session_state.mode == "教学" and teach_uploads:
            attachments = build_teaching_attachments(teach_uploads)
            if "teach_uploader" in st.session_state:
                st.session_state["teach_uploader"] = None
        save_message(character, "user", user_text)
        mark_seen(character)
        if not try_consume_usage():
            handle_usage_limit_blocked(character, False)
            st.rerun()
        start_pending_reply(character, st.session_state.mode, attachments=attachments)
        st.rerun()
