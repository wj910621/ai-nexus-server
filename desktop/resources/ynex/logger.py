"""
统一日志模块
使用 loguru，自动按日期轮转，支持结构化 JSON 日志
"""

import os
import sys
from loguru import logger


LOG_FORMAT = os.environ.get("YNEX_LOG_FORMAT", "plain").lower()  # plain 或 json
LOG_LEVEL = os.environ.get("YNEX_LOG_LEVEL", "INFO").upper()

# 确保日志目录存在（沙箱环境可能不可写，静默降级）
_log_file_ready = False
try:
    os.makedirs("data/logs", exist_ok=True)
    _log_file_ready = True
except (OSError, PermissionError):
    pass

# 移除默认的 stderr 处理器，避免重复
logger.remove()

# 控制台输出
if LOG_FORMAT == "json":
    console_format = "{\"time\":\"{time:YYYY-MM-DD HH:mm:ss}\",\"level\":\"{level}\",\"name\":\"{name}\",\"function\":\"{function}\",\"line\":{line},\"message\":\"{message}\"}"
else:
    console_format = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

logger.add(
    sink=sys.stderr,
    level=LOG_LEVEL,
    format=console_format,
    colorize=True if LOG_FORMAT != "json" else False,
)

# 文件日志，每天轮转
if _log_file_ready:
    file_format = (
        "{\"time\":\"{time:YYYY-MM-DD HH:mm:ss}\",\"level\":\"{level}\",\"name\":\"{name}\",\"function\":\"{function}\",\"line\":{line},\"message\":\"{message}\"}"
        if LOG_FORMAT == "json"
        else "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )
    logger.add(
        "data/logs/ynex_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        level=LOG_LEVEL,
        format=file_format,
    )


def log_request(request_id: str, method: str, path: str, ip: str, status_code: int = 0, extra: dict = None):
    """统一记录请求日志"""
    extra = extra or {}
    if LOG_FORMAT == "json":
        logger.bind(request_id=request_id, method=method, path=path, ip=ip, status=status_code, **extra).info("request")
    else:
        logger.info(f"[{request_id}] {method} {path} from {ip} -> {status_code}")


def log_error(request_id: str, error: str, extra: dict = None):
    """统一记录错误日志"""
    extra = extra or {}
    if LOG_FORMAT == "json":
        logger.bind(request_id=request_id, **extra).error(error)
    else:
        logger.error(f"[{request_id}] {error}")
