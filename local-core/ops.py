"""
Y·NEX运维工具箱 v1.0
- 启动配置校验报告
- 数据库/数据目录自动备份
- 系统健康度巡检
"""

import os
import sys
import json
import time
import zipfile
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from logger import logger
from config import settings


# =============================================================================
# 启动报告
# =============================================================================

@dataclass
class StartupReport:
    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.ok = False

    def add_info(self, key: str, value: Any):
        self.info[key] = value


def _detect_hardware() -> Dict[str, Any]:
    """简单硬件探测"""
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        ram_gb = None

    result = {"ram_gb": ram_gb, "has_gpu": False, "gpu_name": "", "vram_gb": 0}

    try:
        from local_llm import detect_hardware as _detect
        hw = _detect()
        result.update({
            "has_gpu": hw.has_gpu,
            "gpu_name": hw.gpu_name,
            "vram_gb": hw.vram_gb,
            "cpu_cores": hw.cpu_cores,
        })
    except Exception:
        pass

    return result


def _check_ollama() -> Dict[str, Any]:
    """检查 Ollama 是否可访问"""
    try:
        import urllib.request
        with urllib.request.urlopen(settings.local_base_url, timeout=2) as resp:
            return {"available": True, "status": resp.status}
    except Exception as e:
        return {"available": False, "error": str(e)}


def generate_startup_report() -> StartupReport:
    """生成服务启动配置校验报告"""
    report = StartupReport()

    # 配置校验
    from config import validate_config
    issues = validate_config()
    for issue in issues:
        report.add_error(issue)

    # 关键目录
    critical_dirs = [
        ("data", "data"),
        ("knowledge", settings.knowledge_dir),
        ("vectors", settings.vector_db_path),
        ("plugins", "plugins"),
        ("backups", "backups"),
    ]
    for name, d in critical_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            report.add_info(f"dir_{name}", os.path.abspath(d))
        except Exception as e:
            report.add_error(f"无法创建目录 {name}({d}): {e}")

    # 硬件信息
    hw = _detect_hardware()
    report.add_info("hardware", hw)
    if hw.get("ram_gb") and hw["ram_gb"] < 4:
        report.add_warning(f"内存仅 {hw['ram_gb']}GB，运行本地模型可能吃力")

    # LLM 后端
    report.add_info("ollama", _check_ollama())
    if settings.use_local_first and not _check_ollama()["available"]:
        report.add_warning(f"已启用本地优先，但 Ollama 未响应: {settings.local_base_url}")

    # API Key
    if not settings.deepseek_api_key:
        report.add_warning("未配置 DEEPSEEK_API_KEY，将完全依赖本地模型或模拟模式")
    else:
        masked = settings.deepseek_api_key[:4] + "****" + settings.deepseek_api_key[-4:]
        report.add_info("deepseek_api_key", masked)

    # 数据库文件
    for db_file in [settings.memory_db, "data/plugin_configs.json"]:
        path = Path(db_file)
        if path.exists():
            report.add_info(f"db_{path.name}", {"size_bytes": path.stat().st_size})
        else:
            report.add_info(f"db_{path.name}", {"exists": False})

    return report


def print_startup_report(report: StartupReport):
    """在控制台打印启动报告"""
    print("=" * 60)
    print("  Y·NEX启动配置校验报告")
    print("=" * 60)
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  状态: {'✅ 通过' if report.ok else '❌ 存在问题'}")
    print(f"  错误: {len(report.errors)} 个")
    for e in report.errors:
        print(f"    ❌ {e}")
    print(f"  警告: {len(report.warnings)} 个")
    for w in report.warnings:
        print(f"    ⚠ {w}")
    print("  关键信息:")
    for k, v in report.info.items():
        if k == "hardware":
            print(f"    • {k}: {v}")
        elif isinstance(v, dict):
            print(f"    • {k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            print(f"    • {k}: {v}")
    print("=" * 60)


# =============================================================================
# 数据库自动备份
# =============================================================================

@dataclass
class BackupRecord:
    id: str
    created_at: str
    path: str
    size_bytes: int
    source_paths: List[str]


class DatabaseBackupManager:
    """
    自动备份管理器。
    默认备份：SQLite 记忆数据库、插件配置、知识库元数据、ChromaDB。
    """

    def __init__(self, backup_dir: str = "backups", interval_hours: int = 24,
                 keep_count: int = 7):
        self.backup_dir = Path(backup_dir)
        self.interval_hours = interval_hours
        self.keep_count = keep_count
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def _backup_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _default_sources(self) -> List[str]:
        sources = []
        # 所有 SQLite 数据库文件（必须完整备份，否则数据丢失）
        db_files = [
            settings.memory_db,        # data/memory.db - 对话记忆
            "data/users.db",           # billing.py - 用户/余额/API Key
            "data/credits.db",         # credits_system.py - 积分系统
            "data/payments.db",        # payment_system.py - 支付订单
            "data/tasks.db",           # task_scheduler.py - SuperAgent 任务
            "data/scheduler.db",       # scheduler.py - 定时提醒
            "data/email_calendar.db",  # email_calendar.py - 邮件日历
            "data/database.sqlite",    # server_files/server.js - Web 平台主库
        ]
        for p in db_files:
            if os.path.exists(p):
                sources.append(p)
        # 配置文件
        for p in ["data/plugin_configs.json"]:
            if os.path.exists(p):
                sources.append(p)
        # 目录
        for d in [settings.knowledge_dir, settings.vector_db_path, "plugins"]:
            if os.path.exists(d):
                sources.append(d)
        return sources

    def _should_skip(self, path: Path) -> bool:
        """排除缓存、编译产物和临时文件"""
        parts = set(path.parts)
        if "__pycache__" in parts:
            return True
        name = path.name
        if name.endswith((".pyc", ".pyo", ".tmp", ".bak", ".log")):
            return True
        if name.startswith("."):
            return True
        return False

    def _backup_sqlite(self, db_path: Path, zf: zipfile.ZipFile, arcname: str) -> bool:
        """
        使用 SQLite Online Backup API 创建一致性快照。
        安全：直接复制正在写入的 .db 文件可能得到损坏的中间状态，
        尤其在启用 WAL 模式后，.db-wal/.db-shm 与 .db 分离。
        sqlite3.backup() 在源连接上获取读锁，确保快照一致性。
        """
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)
        try:
            src_conn = sqlite3.connect(str(db_path))
            dst_conn = sqlite3.connect(tmp_path)
            try:
                src_conn.backup(dst_conn)
            finally:
                src_conn.close()
                dst_conn.close()
            zf.write(tmp_path, arcname)
            return True
        except Exception as e:
            logger.warning(f"SQLite 热备份失败 {db_path}: {e}，回退到直接复制")
            try:
                zf.write(db_path, arcname)
                return True
            except Exception as e2:
                logger.error(f"SQLite 备份完全失败 {db_path}: {e2}")
                return False
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

    def backup(self, sources: List[str] = None) -> BackupRecord:
        """立即执行一次备份"""
        sources = sources or self._default_sources()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        backup_id = self._backup_id()
        zip_path = self.backup_dir / f"ynex_backup_{backup_id}.zip"

        written: List[str] = []
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in sources:
                src_path = Path(src)
                if not src_path.exists():
                    continue
                if self._should_skip(src_path):
                    continue
                if src_path.is_file():
                    arcname = f"data/{src_path.name}"
                    # SQLite 数据库使用 Online Backup API 避免热备份损坏
                    if src_path.suffix in (".db", ".sqlite", ".sqlite3"):
                        if self._backup_sqlite(src_path, zf, arcname):
                            written.append(str(src_path))
                    else:
                        zf.write(src_path, arcname)
                        written.append(str(src_path))
                elif src_path.is_dir():
                    for f in src_path.rglob("*"):
                        if f.is_file() and not self._should_skip(f):
                            arcname = f"{src_path.name}/{f.relative_to(src_path).as_posix()}"
                            # 目录内的 SQLite 文件同样使用热备份
                            if f.suffix in (".db", ".sqlite", ".sqlite3"):
                                if self._backup_sqlite(f, zf, arcname):
                                    written.append(str(f))
                            else:
                                zf.write(f, arcname)
                                written.append(str(f))

        size = zip_path.stat().st_size
        record = BackupRecord(
            id=backup_id,
            created_at=datetime.now().isoformat(),
            path=str(zip_path.absolute()),
            size_bytes=size,
            source_paths=written,
        )

        logger.info(f"数据库自动备份完成: {zip_path} ({size} bytes)")
        self._cleanup_old_backups()
        return record

    def _cleanup_old_backups(self):
        """只保留最近 keep_count 份备份"""
        try:
            files = sorted(
                self.backup_dir.glob("ynex_backup_*.zip"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old in files[self.keep_count:]:
                old.unlink()
                logger.info(f"删除过期备份: {old}")
        except Exception as e:
            logger.warning(f"清理过期备份失败: {e}")

    def list_backups(self) -> List[BackupRecord]:
        """列出所有备份"""
        records = []
        if not self.backup_dir.exists():
            return records
        for f in sorted(self.backup_dir.glob("ynex_backup_*.zip"), reverse=True):
            try:
                stat = f.stat()
                bid = f.stem.replace("ynex_backup_", "")
                records.append(BackupRecord(
                    id=bid,
                    created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    path=str(f.absolute()),
                    size_bytes=stat.st_size,
                    source_paths=[],
                ))
            except Exception:
                pass
        return records

    def restore(self, backup_id: str, target_dir: str = "restored") -> Dict[str, Any]:
        """解压指定备份到目标目录（不覆盖原数据，避免误操作）"""
        zip_path = self.backup_dir / f"ynex_backup_{backup_id}.zip"
        if not zip_path.exists():
            return {"ok": False, "error": "备份不存在"}

        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(target)
        return {"ok": True, "restored_to": str(target.absolute())}

    def start_auto_backup(self):
        """启动自动备份线程"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._auto_backup_loop,
            daemon=True,
            name="db-auto-backup"
        )
        self._thread.start()
        logger.info(f"数据库自动备份已启动，间隔 {self.interval_hours}h，保留 {self.keep_count} 份")

    def stop_auto_backup(self):
        """停止自动备份线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def _auto_backup_loop(self):
        interval_seconds = self.interval_hours * 3600
        while not self._stop_event.is_set():
            try:
                self.backup()
            except Exception as e:
                logger.error(f"自动备份失败: {e}")
            self._stop_event.wait(interval_seconds)


# 全局单例
_backup_manager: Optional[DatabaseBackupManager] = None


def get_backup_manager() -> DatabaseBackupManager:
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = DatabaseBackupManager(
            backup_dir=getattr(settings, "backup_dir", "backups"),
            interval_hours=getattr(settings, "backup_interval_hours", 24),
            keep_count=getattr(settings, "backup_keep_count", 7),
        )
    return _backup_manager


def backup_now() -> BackupRecord:
    return get_backup_manager().backup()


def list_backups() -> List[BackupRecord]:
    return get_backup_manager().list_backups()
