"""
邮件与日历集成
支持 IMAP 读邮件、SMTP 发邮件、本地日历增删查
"""

import os
import re
import sqlite3
import imaplib
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import List, Optional

from config import settings
from logger import logger


# ============== 邮件 ==============

def _get_email_db_path() -> str:
    return os.path.join(os.path.dirname(settings.memory_db), "email_calendar.db")


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一设置 WAL + busy_timeout）"""
    os.makedirs(os.path.dirname(_get_email_db_path()), exist_ok=True)
    conn = sqlite3.connect(_get_email_db_path(), timeout=30)
    # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _init_db():
    os.makedirs(os.path.dirname(_get_email_db_path()), exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_time TIMESTAMP NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def read_emails(count: int = 5) -> str:
    """读取最近邮件（IMAP）"""
    email_user = os.environ.get("EMAIL_USER", "")
    email_pass = os.environ.get("EMAIL_PASS", "")
    imap_server = os.environ.get("IMAP_SERVER", "")

    if not (email_user and email_pass and imap_server):
        return "先生，未配置邮箱。请在 .env 或环境变量中设置 EMAIL_USER、EMAIL_PASS、IMAP_SERVER。"

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        recent_ids = ids[-count:]

        emails = []
        for eid in reversed(recent_ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            raw = msg_data[0][1]
            from email import message_from_bytes
            msg = message_from_bytes(raw)

            subject = _decode_header_str(msg["Subject"])
            from_addr = _decode_header_str(msg["From"])
            date = msg["Date"]
            emails.append(f"来自：{from_addr}\n主题：{subject}\n时间：{date}")

        mail.logout()
        return "先生，最近邮件：\n\n" + "\n\n---\n\n".join(emails)
    except Exception as e:
        logger.error(f"读取邮件失败：{e}")
        return f"先生，读取邮件失败：{e}"


def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件（SMTP）"""
    email_user = os.environ.get("EMAIL_USER", "")
    email_pass = os.environ.get("EMAIL_PASS", "")
    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not (email_user and email_pass and smtp_server):
        return "先生，未配置发件邮箱。请设置 EMAIL_USER、EMAIL_PASS、SMTP_SERVER、SMTP_PORT。"

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = email_user
        msg["To"] = to
        msg["Subject"] = subject

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, [to], msg.as_string())
        server.quit()

        logger.info(f"邮件已发送给 {to}，主题：{subject}")
        return f"先生，邮件已发送至 {to}。"
    except Exception as e:
        logger.error(f"发送邮件失败：{e}")
        return f"先生，发送邮件失败：{e}"


def _decode_header_str(value) -> str:
    """解码邮件头"""
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="ignore"))
        else:
            result.append(part)
    return "".join(result)


# ============== 日历 ==============

def add_event(title: str, time_str: str, description: str = "") -> str:
    """添加日程"""
    event_time = _parse_event_time(time_str)
    if not event_time:
        return f"先生，无法解析时间 {time_str}，请使用如“明天下午3点”的格式。"

    _init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO events (title, event_time, description) VALUES (?, ?, ?)",
        (title, event_time.isoformat(), description)
    )
    conn.commit()
    conn.close()

    logger.info(f"添加日程：{title} @ {event_time}")
    return f"先生，已添加日程《{title}》：{event_time.strftime('%Y-%m-%d %H:%M')}。"


def list_events(days: int = 7) -> str:
    """列出未来 N 天的日程"""
    _init_db()
    conn = _get_conn()
    start = datetime.now()
    end = start + timedelta(days=days)
    rows = conn.execute(
        "SELECT title, event_time, description FROM events WHERE event_time BETWEEN ? AND ? ORDER BY event_time",
        (start.isoformat(), end.isoformat())
    ).fetchall()
    conn.close()

    if not rows:
        return f"先生，未来 {days} 天没有日程。"

    lines = []
    for r in rows:
        t = datetime.fromisoformat(r[1])
        lines.append(f"{t.strftime('%m-%d %H:%M')} {r[0]}")
        if r[2]:
            lines.append(f"  备注：{r[2]}")
    return "先生，近期日程：\n" + "\n".join(lines)


def _parse_event_time(time_str: str) -> Optional[datetime]:
    """简单解析日程时间"""
    from skills import _parse_chinese_time
    return _parse_chinese_time(time_str)


# 统一技能入口
SKILL_MAP = {
    "read_emails": read_emails,
    "send_email": send_email,
    "add_event": add_event,
    "list_events": list_events,
}
