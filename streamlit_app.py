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
    "DARK_MODE": "0",
    "TTS_ENABLED": "0",
    "CHAT_BG": "",
    "REMINDER_ENABLED": "0",
    "REMINDER_TIME": "09:00",
    "PROACTIVE_ENABLED": "1",
    "PROACTIVE_MIN_INTERVAL_MIN": "20",
    "PROACTIVE_PROB_PCT": "25",
    "TIME_DIVIDER_GRANULARITY": "minute",  # minute / 5min
    "GROUP_NAME": GROUP_CHAT,
    "SUMMARY_MIN_COUNT": "3",
    "SUMMARY_MAX_COUNT": "5",
    "SUMMARY_MAX_CHARS": "220",
    "PROACTIVE_MIN_USER_IDLE_MIN": "5",
}

DEFAULT_USAGE_LIMIT = 200
AFFINITY_DEFAULT = 30
AFFINITY_MIN = 0
AFFINITY_MAX = 120
AFFINITY_SEXY_THRESHOLD = 100
AFFINITY_ANGRY_THRESHOLD = 20
AFFINITY_RECOVER_AMOUNT = 10


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
.wx-bubble p { margin: 0; }
.wx-bubble ul, .wx-bubble ol { margin: 0.3em 0 0.3em 1.1em; }
.wx-bubble li { margin: 0.1em 0; }
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

/* 好感度能量条 */
.affinity-wrap {
  max-width: 940px;
  margin: 4px auto 8px auto;
  padding: 6px 10px 0 10px;
}
.affinity-label {
  font-size: 12px;
  color: rgba(0,0,0,.6);
  margin-bottom: 6px;
}
.affinity-bar {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 122, 187, 0.25);
  border: 1px solid rgba(255, 122, 187, 0.5);
  overflow: hidden;
}
.affinity-fill {
  height: 100%;
  background: linear-gradient(90deg, #ff7abf 0%, #ff4f9a 100%);
  border-radius: 999px;
}
.affinity-scale {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: rgba(0,0,0,.45);
  margin-top: 4px;
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
                message_type TEXT NOT NULL DEFAULT 'text',
                image_url TEXT,
                reply_to_id INTEGER,
                is_deleted BOOLEAN NOT NULL DEFAULT 0,
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
                message_type TEXT NOT NULL DEFAULT 'text',
                image_url TEXT,
                reply_to_id INTEGER,
                is_deleted BOOLEAN NOT NULL DEFAULT 0,
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
            CREATE TABLE IF NOT EXISTS user_context_prompts (
                user_id INTEGER PRIMARY KEY,
                prompt TEXT NOT NULL DEFAULT '',
                last_summary_at {ts_type},
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
        s.execute(text(f"""
            CREATE TABLE IF NOT EXISTS user_affinity (
                user_id INTEGER NOT NULL,
                character TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT {AFFINITY_DEFAULT},
                last_recovered_at {ts_type},
                updated_at {ts_type} NOT NULL DEFAULT {ts_default},
                PRIMARY KEY (user_id, character)
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


def delete_user_account(user_id: int):
    q_list = [
        text("DELETE FROM chat_messages_v2 WHERE user_id = :uid"),
        text("DELETE FROM group_messages_v2 WHERE user_id = :uid"),
        text("DELETE FROM user_usage WHERE user_id = :uid"),
        text("DELETE FROM user_context_prompts WHERE user_id = :uid"),
        text("DELETE FROM user_affinity WHERE user_id = :uid"),
        text("DELETE FROM chat_messages WHERE session_id = CAST(:uid AS TEXT)"),
        text("DELETE FROM group_messages WHERE session_id = CAST(:uid AS TEXT)"),
        text("DELETE FROM users WHERE id = :uid"),
    ]
    with get_conn().session as s:
        for q in q_list:
            s.execute(q, {"uid": user_id})
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


def ensure_affinity_record(user_id: int, character: str):
    q = text("""
        INSERT INTO user_affinity (user_id, character, score)
        VALUES (:uid, :ch, :score)
        ON CONFLICT (user_id, character) DO NOTHING
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": user_id, "ch": character, "score": AFFINITY_DEFAULT})
        s.commit()


def get_affinity_record(user_id: int, character: str) -> dict:
    ensure_affinity_record(user_id, character)
    df = get_conn().query(
        """
        SELECT user_id, character, score, last_recovered_at, updated_at
        FROM user_affinity
        WHERE user_id = :uid AND character = :ch
        LIMIT 1
        """,
        params={"uid": user_id, "ch": character},
        ttl=0,
    )
    if df.empty:
        return {
            "user_id": user_id,
            "character": character,
            "score": AFFINITY_DEFAULT,
            "last_recovered_at": None,
        }
    row = df.iloc[0].to_dict()
    for key in ["last_recovered_at", "updated_at"]:
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                row[key] = None
    return row


def clamp_affinity(score: int) -> int:
    return max(AFFINITY_MIN, min(AFFINITY_MAX, int(score)))


def maybe_recover_affinity(user_id: int, character: str) -> int:
    record = get_affinity_record(user_id, character)
    score = int(record.get("score") or AFFINITY_DEFAULT)
    if score >= AFFINITY_ANGRY_THRESHOLD:
        return score
    last_recovered_at = record.get("last_recovered_at")
    now = datetime.now(timezone.utc)
    if isinstance(last_recovered_at, datetime):
        if last_recovered_at.date() >= now.date():
            return score
    new_score = clamp_affinity(score + AFFINITY_RECOVER_AMOUNT)
    q = text("""
        UPDATE user_affinity
        SET score = :score,
            last_recovered_at = :lra,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = :uid AND character = :ch
    """)
    with get_conn().session as s:
        s.execute(q, {"score": new_score, "lra": now, "uid": user_id, "ch": character})
        s.commit()
    return new_score


def update_affinity(user_id: int, character: str, delta: int = 0, absolute: int | None = None) -> int:
    record = get_affinity_record(user_id, character)
    current = int(record.get("score") or AFFINITY_DEFAULT)
    new_score = clamp_affinity(absolute if absolute is not None else current + delta)
    q = text("""
        UPDATE user_affinity
        SET score = :score,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = :uid AND character = :ch
    """)
    with get_conn().session as s:
        s.execute(q, {"score": new_score, "uid": user_id, "ch": character})
        s.commit()
    return new_score


def build_affinity_prompt(character: str, current_score: int, user_text: str) -> str:
    return (
        "你是恋爱游戏的好感度裁定器，风格参考 galgame。\n"
        f"角色：{character}\n"
        f"当前好感度：{current_score}\n"
        "根据用户发言判断好感度变化幅度，输出一个整数。\n"
        "规则：\n"
        "1) 只输出一个整数，不要任何额外文字。\n"
        "2) 范围 -8 到 8（含）。\n"
        "3) 赞美、体贴、关心、道歉、约会等 -> 增加；侮辱、冷漠、命令、失礼 -> 减少。\n"
        "4) 语气中性就小幅波动（-1~2）。\n"
        f"用户发言：{user_text}"
    )


def _evaluate_affinity_delta_rule(user_text: str) -> int:
    text_val = (user_text or "").lower()
    negative_keywords = ["讨厌", "烦", "滚", "别理", "拉黑", "生气", "你走", "笨", "蠢", "死"]
    positive_keywords = ["谢谢", "喜欢", "爱", "开心", "高兴", "抱抱", "加油", "赞", "好棒"]
    if any(k in text_val for k in negative_keywords):
        return random.randint(-8, -4)
    if any(k in text_val for k in positive_keywords):
        return random.randint(2, 5)
    return random.randint(-1, 2)


def evaluate_affinity_delta(user_text: str, character: str, current_score: int) -> int:
    if "OPENAI_API_KEY" not in st.secrets:
        return _evaluate_affinity_delta_rule(user_text)
    prompt = build_affinity_prompt(character, current_score, user_text)
    try:
        raw = call_openai(
            [
                {"role": "system", "content": "你只输出一个整数。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
    except Exception:
        return _evaluate_affinity_delta_rule(user_text)
    match = re.search(r"-?\d+", str(raw))
    if not match:
        return _evaluate_affinity_delta_rule(user_text)
    value = int(match.group(0))
    return max(-8, min(8, value))


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
if "pending_queue" not in st.session_state:
    st.session_state.pending_queue = {}


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

with st.sidebar.expander("账号管理", expanded=False):
    st.caption("注销账号会永久删除你的聊天记录、好感度与账号信息。")
    confirm_delete = st.checkbox("我确认要注销账号", value=False)
    if st.button("注销账号", type="primary", disabled=(not confirm_delete)):
        delete_user_account(st.session_state.user_id)
        st.success("账号已注销。")
        st.session_state.clear()
        st.rerun()


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


def get_user_prompt_record(user_id: int) -> dict | None:
    df = get_conn().query(
        "SELECT user_id, prompt, last_summary_at, updated_at FROM user_context_prompts WHERE user_id = :uid LIMIT 1",
        params={"uid": user_id},
        ttl=0,
    )
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    last_summary_at = row.get("last_summary_at")
    if isinstance(last_summary_at, str):
        try:
            row["last_summary_at"] = datetime.fromisoformat(last_summary_at.replace("Z", "+00:00"))
        except Exception:
            row["last_summary_at"] = None
    return row


def upsert_user_prompt(user_id: int, prompt: str, last_summary_at: datetime | None = None):
    q = text("""
        INSERT INTO user_context_prompts (user_id, prompt, last_summary_at)
        VALUES (:uid, :prompt, :lsa)
        ON CONFLICT (user_id)
        DO UPDATE SET prompt = EXCLUDED.prompt,
                      last_summary_at = COALESCE(EXCLUDED.last_summary_at, user_context_prompts.last_summary_at),
                      updated_at = CURRENT_TIMESTAMP;
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": user_id, "prompt": prompt, "lsa": last_summary_at})
        s.commit()


def get_user_prompt_text(user_id: int) -> str:
    record = get_user_prompt_record(user_id)
    if not record:
        return ""
    return str(record.get("prompt") or "").strip()


def _normalize_dt_for_query(dt: datetime | None) -> datetime:
    if not dt:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def count_user_messages_since(user_id: int, since_dt: datetime | None) -> int:
    since_dt = _normalize_dt_for_query(since_dt)
    params = {"uid": user_id, "since": since_dt.isoformat()}
    q = """
        SELECT COUNT(*) AS cnt FROM (
            SELECT created_at FROM chat_messages_v2
            WHERE user_id = :uid AND role = 'user' AND created_at >= :since
            UNION ALL
            SELECT created_at FROM group_messages_v2
            WHERE user_id = :uid AND role = 'user' AND created_at >= :since
        ) t
    """
    df = get_conn().query(q, params=params, ttl=0)
    if df.empty:
        return 0
    return int(df.iloc[0]["cnt"] or 0)


def load_recent_messages_for_summary(user_id: int, since_dt: datetime | None, limit: int = 24) -> list[dict]:
    since_dt = _normalize_dt_for_query(since_dt)
    params = {"uid": user_id, "since": since_dt.isoformat(), "limit": int(limit)}
    q = """
        SELECT created_at, source, speaker, role, content FROM (
            SELECT created_at, '单聊' AS source, character AS speaker, role, content
            FROM chat_messages_v2
            WHERE user_id = :uid AND created_at >= :since
            UNION ALL
            SELECT created_at, '群聊' AS source, speaker, role, content
            FROM group_messages_v2
            WHERE user_id = :uid AND created_at >= :since
        ) t
        ORDER BY created_at
        LIMIT :limit
    """
    df = get_conn().query(q, params=params, ttl=0)
    return df.to_dict("records")


def get_next_summary_threshold(user_id: int) -> int:
    key = f"summary_threshold_{user_id}"
    if key not in st.session_state:
        min_cnt = s_int("SUMMARY_MIN_COUNT", 3)
        max_cnt = s_int("SUMMARY_MAX_COUNT", 5)
        st.session_state[key] = random.randint(min_cnt, max_cnt)
    return int(st.session_state[key])


def reset_summary_threshold(user_id: int):
    key = f"summary_threshold_{user_id}"
    min_cnt = s_int("SUMMARY_MIN_COUNT", 3)
    max_cnt = s_int("SUMMARY_MAX_COUNT", 5)
    st.session_state[key] = random.randint(min_cnt, max_cnt)


def maybe_update_user_prompt(user_id: int):
    if "OPENAI_API_KEY" not in st.secrets:
        return
    record = get_user_prompt_record(user_id)
    last_summary_at = record.get("last_summary_at") if record else None
    new_user_msgs = count_user_messages_since(user_id, last_summary_at)
    if new_user_msgs < get_next_summary_threshold(user_id):
        return

    recent = load_recent_messages_for_summary(user_id, last_summary_at, limit=24)
    if not recent:
        return

    existing_prompt = (record.get("prompt") if record else "") or ""
    max_chars = s_int("SUMMARY_MAX_CHARS", 220)
    summary_system = (
        "你是对话记忆压缩器。请根据新增对话更新【用户上下文摘要】。\n"
        "目标：保持聊天记忆，不遗漏关键事实；同时尽量压缩 token。\n"
        "保留：用户偏好/禁忌、关系进展、称呼/语气、长期目标、重要事件。\n"
        "删除：重复信息、寒暄、无关细节。\n"
        f"输出限制：中文，<= {max_chars} 字，仅输出摘要文本。"
    )
    transcript_lines = []
    for item in recent:
        source = item.get("source", "")
        speaker = item.get("speaker", "")
        role = item.get("role", "")
        content = item.get("content", "")
        label = "用户" if role == "user" else speaker
        if source == "群聊":
            label = f"{label}(群聊)"
        transcript_lines.append(f"{label}: {content}")
    transcript = "\n".join(transcript_lines)

    summary_user = (
        f"已有摘要：{existing_prompt or '（无）'}\n"
        "新增对话：\n"
        f"{transcript}\n"
        "请输出更新后的摘要："
    )
    try:
        new_prompt = call_openai(
            [
                {"role": "system", "content": summary_system},
                {"role": "user", "content": summary_user},
            ],
            temperature=0.2,
        )
    except Exception:
        return
    new_prompt = (new_prompt or "").strip()
    if not new_prompt:
        return
    upsert_user_prompt(user_id, new_prompt, last_summary_at=datetime.now(timezone.utc))
    reset_summary_threshold(user_id)


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


def s_str(key: str, default: str) -> str:
    return str(SETTINGS.get(key, default))


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
        SELECT id, role, content, created_at, reply_to_id, message_type, image_url
        FROM chat_messages_v2
        WHERE user_id = :uid AND character = :ch AND is_deleted = 0
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


def save_message(character: str, role: str, content: str, user_id: int | None = None, message_type: str = "text", image_url: str = None, reply_to_id: int = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = text("""
        INSERT INTO chat_messages_v2 (user_id, character, role, content, message_type, image_url, reply_to_id)
        VALUES (:uid, :ch, :role, :content, :msg_type, :img_url, :reply_to)
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": uid, "ch": character, "role": role, "content": content, 
                      "msg_type": message_type, "img_url": image_url, "reply_to": reply_to_id})
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


def get_last_user_message_ts(history: list[dict]) -> float | None:
    for msg in reversed(history):
        if msg.get("role") == "user":
            dt = msg.get("created_at")
            if isinstance(dt, datetime):
                return dt.timestamp()
    return None


# =========================
# 群聊：消息读写
# =========================
def load_group_messages(user_id: int | None = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = """
        SELECT id, speaker, role, content, created_at, reply_to_id, message_type, image_url
        FROM group_messages_v2
        WHERE user_id = :uid AND is_deleted = 0
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


def save_group_message(speaker: str, role: str, content: str, user_id: int | None = None, message_type: str = "text", image_url: str = None, reply_to_id: int = None):
    uid = user_id if user_id is not None else st.session_state.user_id
    q = text("""
        INSERT INTO group_messages_v2 (user_id, speaker, role, content, message_type, image_url, reply_to_id)
        VALUES (:uid, :sp, :role, :content, :msg_type, :img_url, :reply_to)
    """)
    with get_conn().session as s:
        s.execute(q, {"uid": uid, "sp": speaker, "role": role, "content": content,
                      "msg_type": message_type, "img_url": image_url, "reply_to": reply_to_id})
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
def render_affinity_bar(character: str, score: int):
    max_val = AFFINITY_MAX
    min_val = 1
    display_score = max(min_val, min(max_val, int(score)))
    pct = int(display_score / max_val * 100)
    st.markdown(
        f"""
        <div class="affinity-wrap">
          <div class="affinity-label">好感度能量条：{display_score}/{max_val}</div>
          <div class="affinity-bar">
            <div class="affinity-fill" style="width:{pct}%;"></div>
          </div>
          <div class="affinity-scale"><span>{min_val}</span><span>{max_val}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _avatar_html(avatar):
    if isinstance(avatar, str) and avatar.startswith("data:"):
        return f'<div class="wx-avatar"><img src="{avatar}" /></div>'
    safe = _html.escape(str(avatar))
    return f'<div class="wx-avatar">{safe}</div>'


def _message_to_markdown(content: str) -> str:
    safe_text = (content or "").replace("<", "&lt;").replace(">", "&gt;")
    return safe_text.replace("\n", "  \n")


def render_message(role: str, character: str, content: str, message_type: str = "text", image_url: str = None, reply_to_content: str = None):
    is_user = (role == "user")
    avatar = avatar_for("user" if is_user else "assistant", character)
    safe_md = _message_to_markdown(content)

    # 如果有引用消息，显示引用
    if reply_to_content:
        reply_author = "你" if is_user else character
        st.markdown(f'<div class="wx-quote"><span class="wx-quote-author">{reply_author}:</span>{reply_to_content[:50]}...</div>', unsafe_allow_html=True)

    if is_user:
        st.markdown('<div class="wx-row user">', unsafe_allow_html=True)
        st.markdown('<div class="wx-bubble user">', unsafe_allow_html=True)
        if message_type == "image" and image_url:
            st.markdown(f'<img src="{image_url}" class="wx-image" />', unsafe_allow_html=True)
        else:
            st.markdown(safe_md)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(_avatar_html(avatar), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="wx-row bot">', unsafe_allow_html=True)
        st.markdown(_avatar_html(avatar), unsafe_allow_html=True)
        st.markdown('<div class="wx-bubble bot">', unsafe_allow_html=True)
        if message_type == "image" and image_url:
            st.markdown(f'<img src="{image_url}" class="wx-image" />', unsafe_allow_html=True)
        else:
            st.markdown(safe_md)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_group_message(role: str, speaker: str, content: str, message_type: str = "text", image_url: str = None, reply_to_content: str = None):
    is_user = (role == "user")
    avatar = avatar_for("user" if is_user else "assistant", speaker)
    safe_md = _message_to_markdown(content)
    safe_name = "你" if is_user else _html.escape(speaker)

    # 如果有引用消息，显示引用
    if reply_to_content:
        reply_author = "你" if is_user else speaker
        st.markdown(f'<div class="wx-quote"><span class="wx-quote-author">{reply_author}:</span>{reply_to_content[:50]}...</div>', unsafe_allow_html=True)

    if is_user:
        st.markdown('<div class="wx-row user">', unsafe_allow_html=True)
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown(f'<div class="wx-name user">{safe_name}</div>', unsafe_allow_html=True)
        st.markdown('<div class="wx-bubble user">', unsafe_allow_html=True)
        if message_type == "image" and image_url:
            st.markdown(f'<img src="{image_url}" class="wx-image" />', unsafe_allow_html=True)
        else:
            st.markdown(safe_md)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(_avatar_html(avatar), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="wx-row bot">', unsafe_allow_html=True)
        st.markdown(_avatar_html(avatar), unsafe_allow_html=True)
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown(f'<div class="wx-name">{safe_name}</div>', unsafe_allow_html=True)
        st.markdown('<div class="wx-bubble bot">', unsafe_allow_html=True)
        if message_type == "image" and image_url:
            st.markdown(f'<img src="{image_url}" class="wx-image" />', unsafe_allow_html=True)
        else:
            st.markdown(safe_md)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


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


def render_group_typing(speaker: str):
    avatar = avatar_for("assistant", speaker)
    safe_name = _html.escape(speaker)
    html_block = f"""
    <div class="wx-row bot">
        {_avatar_html(avatar)}
        <div>
            <div class="wx-name">{safe_name}</div>
            <div class="wx-bubble bot">
                <div class="typing">
                    <div>对方正在输入</div>
                    <div class="dots"><span></span><span></span><span></span></div>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(html_block, unsafe_allow_html=True)


def render_history_manager(current_character: str):
    st.sidebar.divider()
    with st.sidebar.expander("聊天记录管理", expanded=False):
        # 搜索功能
        search_keyword = st.sidebar.text_input("🔍 搜索聊天记录", placeholder="输入关键词搜索", key=f"search_{current_character}")
        if search_keyword:
            search_results = search_messages(search_keyword, user_id, current_character if current_character != GROUP_CHAT else None)
            if search_results:
                st.sidebar.caption(f"找到 {len(search_results)} 条结果")
                for msg in search_results[:10]:
                    char = msg.get('character', msg.get('speaker', ''))
                    role = "我" if msg.get('role') == 'user' else char
                    st.sidebar.markdown(f"**{role}** ({msg['created_at'][:16]}): {msg['content'][:50]}...")
            else:
                st.sidebar.caption("未找到匹配的消息")
        
        # 显示/管理历史记录
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
        
        # 撤回功能 - 只显示用户自己发送的消息
        user_msgs = df[df["role"] == "user"] if "role" in df.columns else pd.DataFrame()
        if not user_msgs.empty:
            st.sidebar.markdown("---")
            st.sidebar.caption("💬 撤回消息")
            msg_choices = {f"{row.get('content', '')[:30]}... ({row.get('created_at', '')[:16]})": row.get('id') 
                          for _, row in user_msgs.iterrows()}
            if msg_choices:
                selected_msg = st.sidebar.selectbox("选择要撤回的消息", list(msg_choices.keys()), key=f"withdraw_select_{current_character}")
                if st.sidebar.button("撤回这条消息", key=f"withdraw_btn_{current_character}"):
                    msg_id = msg_choices[selected_msg]
                    table = "group_messages_v2" if current_character == GROUP_CHAT else "chat_messages_v2"
                    withdraw_message(msg_id, table)
                    st.sidebar.success("消息已撤回。")
                    st.rerun()
        
        # 导出聊天记录
        st.sidebar.markdown("---")
        st.sidebar.caption("📥 导出聊天记录")
        export_format = st.sidebar.radio("格式", ["JSON", "TXT"], horizontal=True, key=f"export_format_{current_character}")
        if st.sidebar.button("导出当前角色聊天记录", key=f"export_{current_character}"):
            export_data = history_rows
            if export_format == "JSON":
                import json
                export_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                st.sidebar.download_button(
                    label="⬇️ 下载 JSON",
                    data=export_str,
                    file_name=f"chat_{current_character}_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            else:
                export_str = ""
                for msg in export_data:
                    role = msg.get("role", msg.get("speaker", ""))
                    content = msg.get("content", "")
                    time = str(msg.get("created_at", ""))[:19]
                    export_str += f"[{time}] {role}: {content}\n\n"
                st.sidebar.download_button(
                    label="⬇️ 下载 TXT",
                    data=export_str,
                    file_name=f"chat_{current_character}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )


# =========================
# AI：聊天/教学（支持 MiniMax / OpenAI）
# =========================
def build_system_prompt(character: str, mode: str, sexy_mode: bool = False, user_prompt: str = "") -> str:
    base_persona = f"你在扮演{character}，性格是：{CHARACTERS[character]}。"
    context_hint = ""
    if user_prompt:
        context_hint = (
            "\n以下是用户上下文摘要（用于保持记忆，尽量简短，不必重复历史）：\n"
            f"{user_prompt}"
        )

    if mode == "教学":
        teach_core = (
            "你现在进入【教学模式】。\n"
            "目标：像顶级家教一样帮助用户学习/解题。\n"
            "要求：先澄清题目与目标；分步骤讲解；必要时反问引导；给练习与检查点；避免空话。\n"
            "数学公式显示：使用 Markdown 数学格式，行内用 \\( ... \\)，块级用 $$...$$。\n"
            "如果用户给出的 LaTeX 片段不完整或乱码，先修正成规范公式再展示。"
        )
        extra = SETTINGS.get("PROMPT_TEACH_EXTRA", "")
        return base_persona + context_hint + "\n" + teach_core + ("\n" + extra if extra else "")

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
        "记忆与逻辑：优先使用【用户上下文摘要】中的关键信息，后续对话自然引用，避免每次像初次见面。\n"
        "表达方式：避免空泛回应；结合用户话题的专业细节；情绪上先共情再分析。\n"
        "好感度提示：当用户询问如何提升好感度时，给出3-5条可执行的泛化建议（如真诚、尊重、具体关心、积极反馈）。\n"
        "主动聊天：避免尴尬或生硬开场，尽量基于最近话题或用户兴趣发起轻量问题。\n"
        "输出格式：只输出一个 JSON 数组，例如 [\"消息1\",\"消息2\"]。\n"
        "规则：数组1-5条（条数随机）；每条1-3句话（随机）；每条尽量短（像微信）；不要输出除 JSON 外任何文字。"
    
    # 天气查询功能
    weather_hint = """
外部工具：
- 用户询问天气时，你可以回复："我现在无法查询天气，但可以告诉你上海今天天气晴朗，气温20-28°C。"（或其他城市的通用天气回复）
"""
    extra = SETTINGS.get("PROMPT_CHAT_EXTRA", "")
    return base_persona + context_hint + "\n" + chat_core + sexy_core + weather_hint + ("\n" + extra if extra else "")


def call_openai(messages, temperature: float):
    # 优先使用 MiniMax，否则回退到 OpenAI
    if "MINIMAX_API_KEY" in st.secrets:
        client = OpenAI(
            api_key=st.secrets["MINIMAX_API_KEY"],
            base_url="https://api.minimax.chat/v1",
        )
        model = st.secrets.get("MINIMAX_MODEL", "MiniMax-M2.5")
    else:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
    
    resp = client.chat.completions.create(
        model=model,
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


def split_sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*|\n+", raw)
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences or [raw]


def split_into_message_chunks(messages: list[str], min_sentences: int = 1, max_sentences: int = 2) -> list[str]:
    sentences = []
    for msg in messages:
        sentences.extend(split_sentences(msg))
    if not sentences:
        return []
    chunks = []
    idx = 0
    while idx < len(sentences):
        size = random.randint(min_sentences, max_sentences)
        chunk = " ".join(sentences[idx: idx + size]).strip()
        if chunk:
            chunks.append(chunk)
        idx += size
    return chunks


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

    user_prompt = get_user_prompt_text(st.session_state.user_id)
    system_prompt = build_system_prompt(character, mode, sexy_mode=sexy_mode, user_prompt=user_prompt)
    messages = [{"role": "system", "content": system_prompt}]
    history_limit = 12 if mode == "教学" else 8
    for m in history[-history_limit:]:
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

    parsed = parse_chat_messages(raw)
    chunks = split_into_message_chunks(parsed, min_sentences=1, max_sentences=2)
    msgs = pick_random_messages(chunks)
    return msgs if msgs else [raw.strip() or "嗯？"]


def build_group_system_prompt(character: str) -> str:
    user_prompt = get_user_prompt_text(st.session_state.user_id)
    base = build_system_prompt(character, "聊天", user_prompt=user_prompt)
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
    for m in history[-14:]:
        speaker = m.get("speaker", "")
        content = m.get("content", "")
        if speaker == "user":
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "assistant", "content": f"{speaker}：{content}"})
    messages.append({"role": "user", "content": "请在群聊中回复上一条消息。"})

    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    parsed = parse_chat_messages(raw)
    msgs = split_into_message_chunks(parsed, min_sentences=1, max_sentences=2)
    return msgs if msgs else [raw.strip() or "嗯？"]


def get_group_proactive_message(character: str, history: list[dict]) -> list[str]:
    if "OPENAI_API_KEY" not in st.secrets:
        return [f"（测试模式）{character} 先说一句。"]
    system_prompt = build_group_system_prompt(character)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-10:]:
        speaker = m.get("speaker", "")
        content = m.get("content", "")
        if speaker == "user":
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "assistant", "content": f"{speaker}：{content}"})
    messages.append({"role": "user", "content": "请你在群聊里先开个话题，1-2条短消息，轻松自然不尴尬。"})
    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    parsed = parse_chat_messages(raw)
    msgs = split_into_message_chunks(parsed, min_sentences=1, max_sentences=2)
    return msgs[:2] if msgs else ["在吗？"]


def get_proactive_message(character: str, history: list[dict], sexy_mode: bool = False) -> list[str]:
    user_prompt = get_user_prompt_text(st.session_state.user_id)
    system_prompt = build_system_prompt(character, "聊天", sexy_mode=sexy_mode, user_prompt=user_prompt)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-8:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": "请主动发起微信开场，轻松自然不尴尬。仍按 JSON 数组输出，1-2条短消息。"})
    raw = call_openai(messages, s_float("TEMP_CHAT", 1.05))
    parsed = parse_chat_messages(raw)
    msgs = split_into_message_chunks(parsed, min_sentences=1, max_sentences=2)
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

            st.sidebar.markdown("**用户上下文 Prompt（自动更新，可手动改）**")
            prompt_record = get_user_prompt_record(selected_user_id) or {}
            last_summary_at = prompt_record.get("last_summary_at")
            last_summary_label = "无"
            if isinstance(last_summary_at, datetime):
                last_summary_label = last_summary_at.astimezone(LA_TZ).strftime("%Y-%m-%d %H:%M")
            st.sidebar.caption(f"最近自动更新：{last_summary_label}")
            edited_prompt = st.sidebar.text_area(
                "用户 Prompt",
                value=str(prompt_record.get("prompt") or ""),
                height=120,
                key=f"user_prompt_{selected_user_id}",
            )
            if st.sidebar.button("保存用户 Prompt", key=f"save_user_prompt_{selected_user_id}"):
                upsert_user_prompt(selected_user_id, edited_prompt.strip())
                st.sidebar.success("已保存用户 Prompt。")
                st.rerun()

            st.sidebar.markdown("**用户好感度**")
            affinity_character = st.sidebar.selectbox(
                "选择好友",
                list(CHARACTERS.keys()),
                key=f"affinity_character_{selected_user_id}",
            )
            affinity_record = get_affinity_record(selected_user_id, affinity_character)
            affinity_value = int(affinity_record.get("score") or AFFINITY_DEFAULT)
            new_affinity_value = st.sidebar.slider(
                "调整好感度",
                AFFINITY_MIN,
                AFFINITY_MAX,
                affinity_value,
                key=f"affinity_slider_{selected_user_id}_{affinity_character}",
            )
            if st.sidebar.button("保存好感度", key=f"save_affinity_{selected_user_id}_{affinity_character}"):
                update_affinity(selected_user_id, affinity_character, absolute=new_affinity_value)
                st.sidebar.success("好感度已更新。")
                st.rerun()

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

    st.sidebar.markdown("#### 上下文压缩（自动记忆）")
    summary_min = st.sidebar.slider("触发最少对话数", 1, 10, s_int("SUMMARY_MIN_COUNT", 3))
    summary_max = st.sidebar.slider("触发最多对话数", summary_min, 12, s_int("SUMMARY_MAX_COUNT", 5))
    summary_chars = st.sidebar.slider("摘要最大字数", 80, 400, s_int("SUMMARY_MAX_CHARS", 220), step=10)

    st.sidebar.markdown("#### 主动聊天（管理员可控）")
    proactive_enabled = st.sidebar.checkbox("启用主动聊天", value=s_bool("PROACTIVE_ENABLED", True))
    proactive_interval = st.sidebar.slider("最短间隔（分钟）", 1, 180, s_int("PROACTIVE_MIN_INTERVAL_MIN", 20))
    proactive_prob = st.sidebar.slider("触发概率（%）", 0, 100, s_int("PROACTIVE_PROB_PCT", 25))
    proactive_idle_min = st.sidebar.slider(
        "用户静默多久才允许主动（分钟）",
        1,
        180,
        s_int("PROACTIVE_MIN_USER_IDLE_MIN", 5),
    )
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
        upsert_setting("SUMMARY_MIN_COUNT", str(summary_min))
        upsert_setting("SUMMARY_MAX_COUNT", str(summary_max))
        upsert_setting("SUMMARY_MAX_CHARS", str(summary_chars))
        upsert_setting("PROACTIVE_ENABLED", "1" if proactive_enabled else "0")
        upsert_setting("PROACTIVE_MIN_INTERVAL_MIN", str(proactive_interval))
        upsert_setting("PROACTIVE_PROB_PCT", str(proactive_prob))
        upsert_setting("PROACTIVE_MIN_USER_IDLE_MIN", str(proactive_idle_min))
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

# 多选模式
if "multi_characters" not in st.session_state:
    st.session_state.multi_characters = []

# 多选切换按钮
if st.sidebar.toggle("👥 多选聊天", value=bool(st.session_state.multi_characters), key="multi_chat_toggle"):
    if not st.session_state.multi_characters:
        st.session_state.multi_characters = list(CHARACTERS.keys())[:1]  # 默认选一个
else:
    st.session_state.multi_characters = []

if st.session_state.multi_characters:
    # 多选模式
    st.sidebar.caption("选择要同时聊天的角色:")
    for ch in CHARACTERS.keys():
        is_selected = ch in st.session_state.multi_characters
        if st.sidebar.checkbox(f"{DEFAULT_AVATARS.get(ch, '👤')} {ch}", value=is_selected, key=f"multi_{ch}"):
            if ch not in st.session_state.multi_characters:
                st.session_state.multi_characters.append(ch)
        else:
            if ch in st.session_state.multi_characters:
                st.session_state.multi_characters.remove(ch)
    
    if st.sidebar.button("💬 开始多聊", key="start_multi_chat"):
        # 进入多聊模式，显示所有选中角色的消息
        pass
else:
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
affinity_score = None
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
    if character != GROUP_CHAT:
        affinity_score = maybe_recover_affinity(st.session_state.user_id, character)
        st.markdown(
            f'<div class="wx-pill">好感度：{affinity_score}/{AFFINITY_MAX}</div>',
            unsafe_allow_html=True,
        )

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

if character != GROUP_CHAT and affinity_score is not None:
    render_affinity_bar(character, affinity_score)

# =========================
# 新功能：角色资料、语音、背景、提醒
# =========================
with st.sidebar.expander("⚙️ 更多设置", expanded=False):
    # 角色资料
    if character != GROUP_CHAT:
        if st.button(f"📇 查看{character}资料", key=f"profile_{character}"):
            render_character_profile(character)
    
    # 语音朗读
    tts_enabled = st.toggle("🎤 AI语音朗读回复", value=bool(s_int("TTS_ENABLED", 0)), key="tts_toggle")
    if tts_enabled:
        st.caption("开启后AI回复会朗读出来（需要浏览器支持）")
    
    # 自定义背景
    bg_url = st.text_input("🖼️ 聊天背景图URL", value=SETTINGS.get("CHAT_BG", ""), placeholder="输入图片链接")
    if bg_url:
        st.markdown(f'''
        <style>
        .main.has-bg {{
            background-image: url("{bg_url}");
        }}
        </style>
        ''', unsafe_allow_html=True)
    
    # 提醒功能
    st.markdown("---")
    st.caption("⏰ 定时提醒")
    reminder_enabled = st.toggle("开启提醒", value=bool(s_int("REMINDER_ENABLED", 0)), key="reminder_toggle")
    if reminder_enabled:
        reminder_time = st.time_input("提醒时间", value=datetime.strptime(s_int("REMINDER_TIME", 9), "%H").time() if s_int("REMINDER_TIME", 9) else datetime.now().time(), key="reminder_time")
        reminder_msg = st.text_input("提醒内容", placeholder="要AI提醒你什么？", key="reminder_msg")
        if st.button("设置提醒", key="set_reminder"):
            add_reminder(user_id, reminder_time.strftime("%H:%M"), reminder_msg)
            st.success(f"提醒已设置！每天 {reminder_time.strftime('%H:%M')} 提醒你")
    
    # 检查提醒
    if reminder_enabled:
        reminder = check_reminders(user_id)
        if reminder:
            st.warning(f"⏰ 提醒: {reminder}")


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


def queue_direct_messages(character: str, messages: list[str], start_delay: int | None = None):
    if not messages:
        return
    if "pending_queue" not in st.session_state:
        st.session_state.pending_queue = {}
    queue = st.session_state.pending_queue.get(character, [])
    delay = start_delay if start_delay is not None else random.randint(1, 4)
    for msg in messages:
        queue.append({"content": msg, "due_ts": time.time() + delay})
        delay += random.randint(1, 4)
    st.session_state.pending_queue[character] = queue


def process_pending_messages(character: str):
    queue_map = st.session_state.get("pending_queue", {})
    queue = queue_map.get(character, [])
    if not queue:
        return
    now_ts = time.time()
    ready = [p for p in queue if p.get("due_ts", 0) <= now_ts]
    if not ready:
        return
    remaining = [p for p in queue if p.get("due_ts", 0) > now_ts]
    for item in sorted(ready, key=lambda x: x.get("due_ts", 0)):
        save_message(character, "assistant", item["content"])
    queue_map[character] = remaining
    st.session_state.pending_queue = queue_map
    maybe_update_user_prompt(st.session_state.user_id)
    st.rerun()


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
    maybe_update_user_prompt(st.session_state.user_id)


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
if character != GROUP_CHAT:
    process_pending_messages(character)

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
    idle_min = s_int("PROACTIVE_MIN_USER_IDLE_MIN", 5)
    last_user_ts = get_last_user_message_ts(history)
    if now_ts - last_ts >= interval_min * 60:
        if last_user_ts is None or (now_ts - last_user_ts >= idle_min * 60):
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
    delay = random.randint(1, 4)
    st.session_state.pending = {
        "character": character,
        "mode": mode,
        "due_ts": time.time() + delay,
        "attachments": attachments or [],
    }


def has_pending_for(character: str) -> bool:
    p = st.session_state.get("pending")
    if bool(p) and p.get("character") == character:
        return True
    queue_map = st.session_state.get("pending_queue", {})
    return bool(queue_map.get(character))


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
    queue_direct_messages(ch, replies, start_delay=random.randint(1, 4))

    maybe_update_user_prompt(st.session_state.user_id)

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
if character == GROUP_CHAT and st.session_state.get("group_pending"):
    next_pending = sorted(st.session_state.group_pending, key=lambda x: x.get("due_ts", 0))[0]
    render_group_typing(next_pending.get("speaker", ""))

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

# 快捷表情面板
QUICK_EMOJIS = ["😀", "😂", "😊", "😍", "🤔", "😅", "🙄", "😢", "😭", "😡", "👍", "👎", "❤️", "🎉", "🔥", "💪"]

st.markdown("#### 💡快捷表情", unsafe_allow_html=True)
cols = st.columns(len(QUICK_EMOJIS))
for i, emoji in enumerate(QUICK_EMOJIS):
    if cols[i % len(cols)].button(emoji, key=f"emoji_{i}", use_container_width=True):
        # 直接发送表情
        if character == GROUP_CHAT:
            save_group_message("user", "user", emoji)
            st.rerun()
        else:
            save_message(character, "user", emoji)
            # AI可能会回复
            st.rerun()

# 深色模式切换
dark_mode = s_int("DARK_MODE", 0)
if st.sidebar.toggle("🌙 深色模式", value=bool(dark_mode), key="dark_mode_toggle"):
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = True
    st.session_state.dark_mode = True
    st.markdown('<script>document.body.classList.add("dark");</script>', unsafe_allow_html=True)
else:
    st.session_state.dark_mode = False

# 应用深色模式CSS
if st.session_state.get("dark_mode", False):
    st.markdown('<script>document.body.classList.add("dark");</script>', unsafe_allow_html=True)

# 图片上传功能
uploaded_file = st.file_uploader("📷 发送图片", type=["jpg", "jpeg", "png", "gif", "webp"], label_visibility="collapsed", key=f"img_upload_{current_character}")
if uploaded_file:
    # 将图片转为 base64 或保存到可访问的URL
    import base64
    from PIL import Image
    import io
    
    img = Image.open(uploaded_file)
    # 限制图片大小
    img.thumbnail((800, 800))
    
    # 保存到 session_state 作为 base64
    buf = io.BytesIO()
    img.save(buf, format=img.format or "PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    img_url = f"data:image/{img.format or 'png'};base64,{img_b64}"
    
    # 保存图片消息
    if character == GROUP_CHAT:
        save_group_message("user", "user", f"[图片]", message_type="image", image_url=img_url)
    else:
        save_message(character, "user", f"[图片]", message_type="image", image_url=img_url)
    st.success("图片已发送！")
    st.rerun()

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
        current_affinity = maybe_recover_affinity(st.session_state.user_id, character)
        if current_affinity < AFFINITY_ANGRY_THRESHOLD:
            save_message(character, "user", user_text)
            save_message(character, "assistant", f"「{character}」生气了，不理你了。")
            mark_seen(character)
            st.rerun()
        if normalized in ("打开色色模式", "关闭色色模式"):
            save_message(character, "user", user_text)
            if normalized == "打开色色模式" and current_affinity < AFFINITY_SEXY_THRESHOLD:
                reply = f"好感度达到 {AFFINITY_SEXY_THRESHOLD} 才能开启色色模式。"
            else:
                set_sexy_mode(character, normalized == "打开色色模式")
                reply = "已开启色色模式。" if normalized == "打开色色模式" else "已关闭色色模式。"
            save_message(character, "assistant", reply)
            mark_seen(character)
            st.session_state.mode = "聊天"
            st.rerun()
        delta = evaluate_affinity_delta(user_text, character, current_affinity)
        update_affinity(st.session_state.user_id, character, delta=delta)
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


# =========================
# 微信特色功能：撤回、引用、搜索
# =========================

def withdraw_message(msg_id: int, table: str = "chat_messages_v2"):
    """撤回消息（标记为已删除）"""
    with get_conn().session as s:
        s.execute(text(f"UPDATE {table} SET is_deleted = 1 WHERE id = :id"), {"id": msg_id})
        s.commit()


def search_messages(keyword: str, user_id: int, character: str = None, limit: int = 20):
    """搜索消息"""
    params = {"keyword": f"%{keyword}%", "user_id": user_id}
    char_cond = "AND character = :character" if character else ""
    
    sql = text(f"""
        SELECT id, character, role, content, created_at 
        FROM chat_messages_v2 
        WHERE user_id = :user_id AND content LIKE :keyword AND is_deleted = 0 {char_cond}
        ORDER BY created_at DESC LIMIT :limit
    """)
    params["limit"] = limit
    if character:
        params["character"] = character
    
    try:
        df = get_conn().query(sql, params=params)
        return df.to_dict('records') if not df.empty else []
    except:
        return []


def get_message_by_id(msg_id: int, table: str = "chat_messages_v2"):
    """根据ID获取消息"""
    try:
        df = get_conn().query(
            text(f"SELECT * FROM {table} WHERE id = :id"),
            {"id": msg_id}
        )
        return df.to_dict('records')[0] if not df.empty else None
    except:
        return None


/* 引用消息样式 */
.wx-quote {
    background: rgba(0,0,0,0.03);
    border-left: 3px solid rgba(0,0,0,0.2);
    padding: 4px 8px;
    margin-bottom: 6px;
    border-radius: 4px;
    font-size: 13px;
    color: rgba(0,0,0,0.6);
}
.wx-quote-author {
    font-weight: 600;
    margin-right: 4px;
}

/* 消息操作按钮 */
.wx-msg-actions {
    display: none;
    position: absolute;
    right: -30px;
    top: 50%;
    transform: translateY(-50%);
}
.wx-row:hover .wx-msg-actions {
    display: flex;
    gap: 4px;
}
.wx-action-btn {
    background: rgba(0,0,0,0.1);
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
    cursor: pointer;
}
.wx-action-btn:hover {
    background: rgba(0,0,0,0.2);
}


/* =========================
   深色模式样式
   ========================= */
.main.dark { background:#1e1e1e; }
.main.dark .wx-chat { background:transparent; }
.main.dark .wx-bubble.bot { background:#2d2d2d; border-color:#3d3d3d; color:#e0e0e0; }
.main.dark .wx-bubble.user { background:#4caf50; border-color:#388e3c; }
.main.dark .wx-time span { background:rgba(255,255,255,0.1); color:rgba(255,255,255,0.6); }
.main.dark .wx-name { color:rgba(255,255,255,0.5); }
.main.dark section[data-testid="stSidebar"] { background:#252525; }
.main.dark .wx-item { background:rgba(255,255,255,0.05); border-color:rgba(255,255,255,0.1); }
.main.dark .wx-item.active { background:rgba(255,255,255,0.1); }
.main.dark .wx-item:hover { border-color:rgba(255,255,255,0.2); }
.main.dark .wx-item .preview { color:rgba(255,255,255,0.5); }
.main.dark .wx-title { color:#e0e0e0; }
.main.dark .wx-pill { background:rgba(255,255,255,0.1); border-color:rgba(255,255,255,0.1); }
.main.dark .affinity-bar { background:rgba(255,122,187,0.15); border-color:rgba(255,122,187,0.3); }
.main.dark .affinity-label { color:rgba(255,255,255,0.7); }
.main.dark .affinity-scale { color:rgba(255,255,255,0.4); }
.main.dark div[data-testid="stChatInput"] { background:#1e1e1e; }

/* 快捷表情 */
.emoji-panel {
    display:flex; gap:8px; flex-wrap:wrap; padding:8px 12px;
    background:rgba(255,255,255,0.9);
    border-radius:8px; margin-bottom:8px;
}
.main.dark .emoji-panel { background:rgba(50,50,50,0.9); }
.emoji-btn {
    font-size:20px; cursor:pointer; padding:4px; border-radius:4px;
    transition:background 0.2s;
}
.emoji-btn:hover { background:rgba(0,0,0,0.1); }

/* 图片消息 */
.wx-image {
    max-width:200px; border-radius:8px; cursor:pointer;
    transition:transform 0.2s;
}
.wx-image:hover { transform:scale(1.02); }

/* 引用消息深色模式 */
.main.dark .wx-quote { background:rgba(255,255,255,0.05); border-color:rgba(255,255,255,0.2); color:rgba(255,255,255,0.6); }



/* 自定义背景图 */
.main.has-bg {
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}
.main.has-bg > div:first-child {
    background: rgba(255,255,255,0.85);
}
.main.dark.has-bg > div:first-child {
    background: rgba(30,30,30,0.85);
}

/* 角色资料卡 */
.profile-card {
    background: white;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.dark .profile-card {
    background: #2d2d2d;
}
.profile-avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    font-size: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.1);
    margin: 0 auto 10px;
}
.profile-name {
    font-size: 24px;
    font-weight: bold;
    text-align: center;
}
.profile-desc {
    font-size: 14px;
    color: rgba(0,0,0,0.6);
    text-align: center;
    margin-top: 8px;
}
.dark .profile-desc {
    color: rgba(255,255,255,0.6);
}

/* 语音播放按钮 */
.tts-btn {
    font-size: 12px;
    margin-left: 8px;
    cursor: pointer;
    opacity: 0.6;
}
.tts-btn:hover {
    opacity: 1;
}


/* 导出按钮 */
.export-btns { display:flex; gap:8px; margin-top:8px; }


# =========================
# 语音、背景、提醒功能
# =========================

def get_weather_info(location: str = "上海") -> str:
    """获取天气信息（简单实现，实际可用API）"""
    # 这里可以接入天气API，目前返回模拟数据
    return f"查询天气需要接入天气API，当前无法获取 {location} 的天气信息。"


def speak_text(text: str):
    """语音播放文字（需要前端JS支持）"""
    # Streamlit不支持直接TTS，需要用audio组件或前端
    pass


def add_reminder(user_id: int, remind_time: str, message: str):
    """添加提醒"""
    # 可以存到数据库或session_state
    if "reminders" not in st.session_state:
        st.session_state.reminders = []
    st.session_state.reminders.append({
        "time": remind_time,
        "message": message,
        "user_id": user_id
    })


def check_reminders(user_id: int):
    """检查并触发提醒"""
    if "reminders" not in st.session_state:
        return
    
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    for reminder in st.session_state.reminders:
        if reminder.get("user_id") == user_id and reminder.get("time") == current_time:
            return reminder.get("message")
    return None


def render_character_profile(character: str):
    """渲染角色资料卡"""
    avatar = DEFAULT_AVATARS.get(character, "👤")
    desc = CHARACTERS.get(character, "这是一个角色")
    
    html = f'''
    <div class="profile-card">
        <div class="profile-avatar">{avatar}</div>
        <div class="profile-name">{character}</div>
        <div class="profile-desc">{desc}</div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)
