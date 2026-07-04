import os
import sqlite3
from datetime import datetime
from config import settings


def _get_conn():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(settings.memory_db), exist_ok=True)
    conn = sqlite3.connect(settings.memory_db, timeout=30)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _init_db():
    """初始化记忆表"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_call_id TEXT,
            tool_calls_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 兼容旧数据库迁移
    for col in ["tool_call_id", "tool_calls_json"]:
        try:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_memory():
    """读取最近对话历史"""
    _init_db()
    conn = _get_conn()
    system = conn.execute(
        "SELECT role, content, tool_call_id, tool_calls_json FROM messages WHERE role = 'system' ORDER BY id DESC LIMIT 1"
    ).fetchall()
    others = conn.execute(
        "SELECT role, content, tool_call_id, tool_calls_json FROM messages WHERE role != 'system' ORDER BY id DESC LIMIT ?",
        (settings.max_history * 2,)
    ).fetchall()
    conn.close()

    def _build_row(m):
        row = {"role": m["role"], "content": m["content"]}
        if m["tool_call_id"]:
            row["tool_call_id"] = m["tool_call_id"]
        if m["tool_calls_json"]:
            import json
            row["tool_calls"] = json.loads(m["tool_calls_json"])
        return row

    messages = [_build_row(m) for m in system] + [_build_row(m) for m in reversed(others)]
    return messages


def save_memory(messages):
    """保存对话历史（追加模式，保留长期记忆）"""
    _init_db()
    conn = _get_conn()

    # 保留历史记录，仅覆盖最新的 system 消息（系统提示词通常每次会变化）
    system_done = False
    for m in messages:
        if m.get("role") == "system":
            if system_done:
                continue
            # 删除旧的 system 消息，仅保留最新一条
            conn.execute("DELETE FROM messages WHERE role = 'system'")
            system_done = True
        tool_calls_json = None
        if m.get("tool_calls"):
            import json
            tool_calls_json = json.dumps(m["tool_calls"])
        conn.execute(
            "INSERT INTO messages (role, content, tool_call_id, tool_calls_json) VALUES (?, ?, ?, ?)",
            (m.get("role"), m.get("content"), m.get("tool_call_id"), tool_calls_json)
        )

    # 控制历史长度，仅保留最近 max_history * 4 条非 system 记录，避免无限增长
    max_rows = settings.max_history * 4
    conn.execute(
        "DELETE FROM messages WHERE role != 'system' AND id NOT IN "
        "(SELECT id FROM messages WHERE role != 'system' ORDER BY id DESC LIMIT ?)",
        (max_rows,)
    )

    conn.commit()
    conn.close()


def get_profile(key: str, default=None):
    """读取用户画像"""
    _init_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM user_profile WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_profile(key: str, value: str):
    """设置用户画像"""
    _init_db()
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO user_profile (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (key, value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
