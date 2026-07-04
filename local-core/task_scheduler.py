"""
Y·NEX任务调度器
- 持久化 SuperAgent 任务到 SQLite
- 支持后台异步执行、重试、取消、进度查询
- 服务重启后可恢复未完成任务
"""
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable

from logger import logger
from config import settings


DB_PATH = "data/tasks.db"


@dataclass
class ScheduledTask:
    id: str
    request: str
    status: str = "pending"  # pending / running / completed / failed / cancelled
    plan_json: str = ""
    result: str = ""
    error: str = ""
    created_at: float = 0
    updated_at: float = 0
    retry_count: int = 0
    max_retries: int = 2


class TaskScheduler:
    """任务调度器（单例）"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable]] = {}
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（统一设置 WAL + busy_timeout）"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _init_db(self):
        """初始化 SQLite 表"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    request TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    plan_json TEXT DEFAULT '',
                    result TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    created_at REAL DEFAULT 0,
                    updated_at REAL DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_updated ON tasks(updated_at)")
            conn.commit()
        finally:
            conn.close()

    def _to_task(self, row) -> ScheduledTask:
        return ScheduledTask(
            id=row[0],
            request=row[1],
            status=row[2],
            plan_json=row[3] or "",
            result=row[4] or "",
            error=row[5] or "",
            created_at=row[6] or 0,
            updated_at=row[7] or 0,
            retry_count=row[8] or 0,
            max_retries=row[9] or 2,
        )

    def create_task(self, request: str, max_retries: int = 2) -> ScheduledTask:
        """创建新任务"""
        task = ScheduledTask(
            id=str(uuid.uuid4())[:12],
            request=request,
            status="pending",
            created_at=time.time(),
            updated_at=time.time(),
            max_retries=max_retries,
        )
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO tasks (id, request, status, plan_json, result, error, created_at, updated_at, retry_count, max_retries)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.id, task.request, task.status, task.plan_json, task.result, task.error,
                 task.created_at, task.updated_at, task.retry_count, task.max_retries),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info(f"创建任务 {task.id}: {request[:60]}...")
        return task

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._to_task(row) if row else None
        finally:
            conn.close()

    def list_tasks(self, status: str = None, limit: int = 50) -> List[ScheduledTask]:
        """列出任务"""
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._to_task(r) for r in rows]
        finally:
            conn.close()

    def update_task(self, task_id: str, **kwargs):
        """更新任务字段"""
        allowed = {"status", "plan_json", "result", "error", "retry_count", "max_retries"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [task_id]
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务（仅 pending/running 可取消）
        安全：使用原子条件 UPDATE 避免 TOCTOU 竞态。
        """
        now = time.time()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "UPDATE tasks SET status = 'cancelled', updated_at = ? "
                "WHERE id = ? AND status IN ('pending', 'running')",
                (now, task_id),
            )
            conn.commit()
            cancelled = cur.rowcount > 0
        finally:
            conn.close()
        if cancelled:
            logger.info(f"取消任务 {task_id}")
        return cancelled

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        conn = self._get_conn()
        try:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_pending_tasks(self) -> List[ScheduledTask]:
        """获取待执行或需重试的任务"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM tasks WHERE status IN ('pending', 'failed')
                   AND retry_count < max_retries
                   ORDER BY created_at ASC LIMIT 10"""
            ).fetchall()
            return [self._to_task(r) for r in rows]
        finally:
            conn.close()


# 全局单例
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def execute_task_background(task_id: str, scheduler: TaskScheduler = None):
    """后台执行单个任务"""
    scheduler = scheduler or get_scheduler()
    task = scheduler.get_task(task_id)
    if not task or task.status != "pending":
        return

    scheduler.update_task(task_id, status="running")
    logger.info(f"开始执行任务 {task_id}")

    try:
        from super_agent import get_super_agent
        agent = get_super_agent()
        result = agent.execute(task.request)
        scheduler.update_task(task_id, status="completed", result=result, error="")
        logger.info(f"任务 {task_id} 完成")
    except Exception as e:
        logger.error(f"任务 {task_id} 失败: {e}")
        retry_count = task.retry_count + 1
        if retry_count >= task.max_retries:
            scheduler.update_task(task_id, status="failed", error=str(e), retry_count=retry_count)
        else:
            scheduler.update_task(task_id, status="pending", error=str(e), retry_count=retry_count)


def start_worker(check_interval: int = 5):
    """启动后台任务执行线程"""
    def worker_loop():
        scheduler = get_scheduler()
        while True:
            try:
                tasks = scheduler.get_pending_tasks()
                for task in tasks:
                    if task.status == "pending" or task.retry_count < task.max_retries:
                        threading.Thread(
                            target=execute_task_background,
                            args=(task.id, scheduler),
                            daemon=True,
                        ).start()
            except Exception as e:
                logger.error(f"任务调度器异常: {e}")
            time.sleep(check_interval)

    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    logger.info("任务调度器已启动")
    return t


if __name__ == "__main__":
    scheduler = get_scheduler()
    task = scheduler.create_task("帮我在桌面上创建一个名为 'hello.txt' 的文件")
    print(f"创建任务: {task.id}")
    execute_task_background(task.id)
