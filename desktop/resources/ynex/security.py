"""
Y·NEX安全工具模块
- 路径遍历防护
- 命令执行白名单/黑名单
- 敏感路径保护
- 输入消毒
"""
import os
import re
from pathlib import Path
from typing import List, Optional, Set

from logger import logger


# 默认允许文件操作的基础目录（可通过配置扩展）
ALLOWED_BASE_DIRS: List[str] = [
    os.getcwd(),
    os.path.join(os.getcwd(), "data"),
    os.path.join(os.getcwd(), "plugins"),
    os.path.join(os.getcwd(), "knowledge"),
    os.path.expanduser("~"),
]

# 敏感路径绝对禁止访问
DENIED_PATHS: Set[str] = {
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "/etc",
    "/usr/bin",
    "/bin",
    "/sbin",
    "/sys",
    "/proc",
    "/dev",
}

# 危险命令黑名单（部分匹配）
DANGEROUS_COMMANDS: Set[str] = {
    "format", "fdisk", "mkfs", "dd", "deltree", "rd /s", "rmdir /s",
    "rm -rf /", "rm -rf /*", ":(){ :|:& };:", "> /dev/sda",
}


def normalize_path(path: str) -> Optional[str]:
    """
    规范化路径，返回绝对路径或 None（如果路径非法）
    """
    if not path or not isinstance(path, str):
        return None
    try:
        # 先展开用户目录
        expanded = os.path.expanduser(path)
        # 转为绝对路径并解析 .. 等
        abs_path = os.path.abspath(expanded)
        # 再次真实路径解析（处理符号链接）
        real_path = os.path.realpath(abs_path)
        return real_path
    except Exception as e:
        logger.warning(f"路径规范化失败: {path} -> {e}")
        return None


def is_path_safe(path: str, allowed_bases: Optional[List[str]] = None) -> bool:
    """
    检查路径是否安全：
    1. 不能是敏感系统路径
    2. 必须在允许的基目录内
    3. 规范化后不能包含 .. 穿越
    """
    if not path or not isinstance(path, str):
        return False

    # 在非 Windows 平台拒绝 Windows 风格绝对路径，避免被 os.path.abspath 拼接到当前目录绕过
    if os.name != "nt" and len(path) >= 3 and path[1] == ":" and path[2] in {"\\", "/"}:
        logger.warning(f"Windows 风格绝对路径被拒绝: {path}")
        return False

    real_path = normalize_path(path)
    if real_path is None:
        return False

    # 检查敏感路径
    lower_path = real_path.lower()
    for denied in DENIED_PATHS:
        if lower_path.startswith(denied.lower()):
            logger.warning(f"访问敏感路径被拒绝: {real_path}")
            return False

    # 检查是否在允许目录内
    bases = allowed_bases or ALLOWED_BASE_DIRS
    for base in bases:
        base_real = os.path.realpath(os.path.expanduser(base))
        # 使用 commonpath 比较，避免字符串前缀误判
        try:
            common = os.path.commonpath([base_real, real_path])
            if common == base_real:
                return True
        except ValueError:
            continue

    logger.warning(f"路径越界访问被拒绝: {real_path}，允许基目录: {bases}")
    return False


def sanitize_path(path: str, default_base: Optional[str] = None) -> str:
    """
    将路径限制在默认基目录内，如果越界则返回默认基目录
    """
    if default_base and not os.path.isabs(path):
        path = os.path.join(default_base, path)

    if is_path_safe(path):
        return normalize_path(path) or path

    # 越界时 fallback 到默认基目录
    if default_base:
        return os.path.realpath(os.path.expanduser(default_base))
    raise ValueError(f"非法路径: {path}")


def is_command_safe(command: str) -> bool:
    """
    检查系统命令是否包含明显危险操作
    """
    if not command or not isinstance(command, str):
        return False
    lower_cmd = command.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in lower_cmd:
            logger.warning(f"危险命令被拦截: {command}")
            return False
    return True


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """
    基础输入消毒：限制长度、去除控制字符
    """
    if not isinstance(text, str):
        text = str(text)
    text = text[:max_length]
    # 去除零宽字符和控制字符（保留换行、制表符）
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\ufeff]", "", text)
    return text.strip()


# 插件安全：允许的 URL 协议与域名白名单
ALLOWED_PLUGIN_PROTOCOLS: Set[str] = {"http", "https"}


def is_plugin_url_safe(url: str) -> bool:
    """检查插件安装 URL 是否安全（防 SSRF）"""
    if not url or not isinstance(url, str):
        return False
    from urllib.parse import urlparse
    import ipaddress
    import socket
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_PLUGIN_PROTOCOLS:
        logger.warning(f"不安全的插件 URL 协议: {parsed.scheme}")
        return False
    hostname = parsed.hostname or ""
    if not hostname:
        return False

    # 禁止本地地址与内网地址
    _blocked_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
    if hostname.lower() in _blocked_hostnames:
        logger.warning(f"禁止从本地地址安装插件: {url}")
        return False

    # 尝试解析 hostname，校验所有解析结果不在内网/保留段
    try:
        # 如果 hostname 本身是 IP
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                logger.warning(f"禁止从内网/保留 IP 安装插件: {url}")
                return False
        except ValueError:
            # 不是 IP，做 DNS 解析
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for family, _, _, _, sockaddr in resolved:
                    ip_str = sockaddr[0]
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                            logger.warning(f"插件 URL 解析到内网 IP {ip_str}: {url}")
                            return False
                    except ValueError:
                        continue
            except socket.gaierror:
                logger.warning(f"插件 URL 域名解析失败: {url}")
                return False
    except Exception as e:
        logger.warning(f"插件 URL 安全检查异常: {url} -> {e}")
        return False

    return True


def get_safe_work_dir(sub_dir: str = "data") -> str:
    """获取安全的工作目录，如果不存在则创建"""
    work_dir = os.path.join(os.getcwd(), sub_dir)
    os.makedirs(work_dir, exist_ok=True)
    return os.path.realpath(work_dir)
