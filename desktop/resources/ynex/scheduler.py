"""
定时任务调度器
基于 APScheduler，支持提醒、日报、自定义定时任务
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import settings
from logger import logger


_scheduler: Optional[BackgroundScheduler] = None
_reminder_callback: Optional[Callable[[str], None]] = None


def _get_db_path() -> str:
    return os.path.join(os.path.dirname(settings.memory_db), "scheduler.db")


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一设置 WAL + busy_timeout）"""
    os.makedirs(os.path.dirname(_get_db_path()), exist_ok=True)
    conn = sqlite3.connect(_get_db_path(), timeout=30)
    # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _init_db():
    """初始化定时任务数据库"""
    os.makedirs(os.path.dirname(_get_db_path()), exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            trigger_time TEXT,
            cron_expr TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            executed BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def get_scheduler() -> BackgroundScheduler:
    """获取或创建后台调度器"""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.start()
    return _scheduler


def set_reminder_callback(callback: Callable[[str], None]):
    """设置提醒触发时的回调函数（用于语音播报）"""
    global _reminder_callback
    _reminder_callback = callback


def _notify(task: str):
    """触发提醒：日志 + 回调 + 系统通知"""
    msg = f"先生，提醒：{task}"
    logger.info(msg)

    if _reminder_callback:
        try:
            _reminder_callback(msg)
        except Exception as e:
            logger.error(f"提醒回调失败：{e}")

    # Windows 系统通知
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast("Y·NEX提醒", task, duration=5, threaded=True)
    except Exception:
        pass


def add_one_time_reminder(task: str, trigger_time: datetime) -> str:
    """添加一次性提醒"""
    _init_db()
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO reminders (task, trigger_time) VALUES (?, ?)",
        (task, trigger_time.isoformat())
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()

    scheduler = get_scheduler()
    scheduler.add_job(
        func=_notify,
        trigger=DateTrigger(run_date=trigger_time),
        args=[task],
        id=f"reminder_{reminder_id}",
        replace_existing=True
    )

    logger.info(f"添加一次性提醒 [{reminder_id}]：{task} @ {trigger_time}")
    return f"已设置提醒：{trigger_time.strftime('%Y-%m-%d %H:%M')} {task}"


def add_cron_reminder(task: str, cron_expr: str) -> str:
    """
    添加周期性提醒
    cron_expr: APScheduler 的 cron 表达式，例如 '0 9 * * 1-5' 表示工作日 9 点
    """
    _init_db()
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO reminders (task, cron_expr) VALUES (?, ?)",
        (task, cron_expr)
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 解析 cron 表达式：minute hour day month day_of_week
    parts = cron_expr.split()
    if len(parts) != 5:
        return "先生，cron 表达式格式不正确，应为：分 时 日 月 周"

    scheduler = get_scheduler()
    scheduler.add_job(
        func=_notify,
        trigger=CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        ),
        args=[task],
        id=f"reminder_{reminder_id}",
        replace_existing=True
    )

    logger.info(f"添加周期提醒 [{reminder_id}]：{task} @ {cron_expr}")
    return f"已设置周期提醒：{cron_expr} {task}"


def list_active_reminders() -> str:
    """列出未执行的提醒"""
    _init_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, task, trigger_time, cron_expr FROM reminders WHERE executed = 0 ORDER BY id DESC"
    ).fetchall()
    conn.close()

    if not rows:
        return "先生，当前没有待执行的提醒。"

    lines = []
    for r in rows:
        time_str = r[2] if r[2] else "周期"
        lines.append(f"[{r[0]}] {time_str} - {r[1]}")
    return "先生，当前提醒：\n" + "\n".join(lines)


def cancel_reminder(reminder_id: int) -> str:
    """取消提醒"""
    _init_db()
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted:
        scheduler = get_scheduler()
        try:
            scheduler.remove_job(f"reminder_{reminder_id}")
        except Exception:
            pass
        logger.info(f"取消提醒 [{reminder_id}]")
        return f"先生，提醒 [{reminder_id}] 已取消。"
    return f"先生，未找到提醒 [{reminder_id}]。"


def add_daily_report_job(hour: int = 9, minute: int = 0):
    """添加每日早报任务"""
    def _daily_report():
        from skills import get_weather, get_time
        weather = get_weather()
        time_str = get_time()
        report = f"先生，早安。{time_str}\n{weather}\n今日请多保重。"
        _notify(report)

    scheduler = get_scheduler()
    scheduler.add_job(
        func=_daily_report,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_report",
        replace_existing=True
    )
    logger.info(f"添加每日早报：{hour:02d}:{minute:02d}")


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        _scheduler = None
