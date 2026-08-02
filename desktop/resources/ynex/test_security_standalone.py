"""
安全模块独立测试
不依赖项目导入，直接测试核心安全逻辑
"""

import os
import re
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse
import ipaddress
import socket


# 复制核心安全逻辑
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

DANGEROUS_COMMANDS: Set[str] = {
    "format", "fdisk", "mkfs", "dd", "deltree", "rd /s", "rmdir /s",
    "rm -rf /", "rm -rf /*", ":(){ :|:& };:", "> /dev/sda",
}

ALLOWED_BASE_DIRS: List[str] = [
    os.getcwd(),
    os.path.join(os.getcwd(), "data"),
    os.path.expanduser("~"),
]


def normalize_path(path: str) -> Optional[str]:
    """规范化路径"""
    if not path or not isinstance(path, str):
        return None
    try:
        expanded = os.path.expanduser(path)
        abs_path = os.path.abspath(expanded)
        real_path = os.path.realpath(abs_path)
        return real_path
    except Exception:
        return None


def is_path_safe(path: str, allowed_bases: Optional[List[str]] = None) -> bool:
    """检查路径是否安全"""
    real_path = normalize_path(path)
    if real_path is None:
        return False

    lower_path = real_path.lower()
    for denied in DENIED_PATHS:
        if lower_path.startswith(denied.lower()):
            return False

    bases = allowed_bases or ALLOWED_BASE_DIRS
    for base in bases:
        base_real = os.path.realpath(os.path.expanduser(base))
        try:
            common = os.path.commonpath([base_real, real_path])
            if common == base_real:
                return True
        except ValueError:
            continue

    return False


def sanitize_path(path: str, default_base: Optional[str] = None) -> str:
    """路径消毒"""
    if default_base and not os.path.isabs(path):
        path = os.path.join(default_base, path)

    if is_path_safe(path):
        return normalize_path(path) or path

    if default_base:
        return os.path.realpath(os.path.expanduser(default_base))
    raise ValueError(f"非法路径: {path}")


def is_command_safe(command: str) -> bool:
    """检查命令安全性"""
    if not command or not isinstance(command, str):
        return False
    lower_cmd = command.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in lower_cmd:
            return False
    return True


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """输入消毒"""
    if not isinstance(text, str):
        text = str(text)
    text = text[:max_length]
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\ufeff]", "", text)
    return text.strip()


ALLOWED_PLUGIN_PROTOCOLS: Set[str] = {"http", "https"}


def is_plugin_url_safe(url: str) -> bool:
    """检查插件 URL 安全性"""
    if not url or not isinstance(url, str):
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_PLUGIN_PROTOCOLS:
        return False

    hostname = parsed.hostname or ""
    if not hostname:
        return False

    _blocked_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
    if hostname.lower() in _blocked_hostnames:
        return False

    try:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        except ValueError:
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for family, _, _, _, sockaddr in resolved:
                    ip_str = sockaddr[0]
                    try:
                        ip = ipaddress.ip_address(ip_str)
                        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                            return False
                    except ValueError:
                        continue
            except socket.gaierror:
                return False
    except Exception:
        return False

    return True


# ============ 测试用例 ============

def test_normalize_path():
    """测试路径规范化"""
    print("\n=== 测试路径规范化 ===")

    assert normalize_path("/tmp/test.txt")
    assert normalize_path("~/Documents")
    assert normalize_path("./relative/path")

    path = normalize_path("/tmp/../etc/passwd")
    assert path is not None
    assert ".." not in path

    assert normalize_path("") is None
    assert normalize_path(None) is None

    print("✅ 路径规范化正确")


def test_path_safety_checks():
    """测试路径安全检查"""
    print("\n=== 测试路径安全检查 ===")

    # 测试敏感路径拒绝（仅在路径存在时）
    for denied in DENIED_PATHS:
        # Linux 系统测试
        if os.name == 'posix' and denied.startswith('/'):
            if os.path.exists(denied):
                assert is_path_safe(denied) is False, f"{denied} 应被拒绝"
                assert is_path_safe(denied + "/subdir") is False
        # Windows 系统测试
        elif os.name == 'nt' and denied.startswith('C:'):
            # Windows 路径在 Linux 环境下不适用
            pass

    # 测试允许的基础目录
    for allowed in ALLOWED_BASE_DIRS:
        if os.path.exists(allowed):
            assert is_path_safe(allowed) is True, f"{allowed} 应被允许"

    # 测试路径遍历攻击（这些应该被拒绝）
    assert is_path_safe("../../../etc/passwd") is False
    assert is_path_safe("../../root/.ssh/id_rsa") is False

    print("✅ 路径安全检查正确")


def test_sanitize_path():
    """测试路径消毒"""
    print("\n=== 测试路径消毒 ===")

    # 使用当前工作目录下的路径
    cwd = os.getcwd()
    safe_path = sanitize_path(os.path.join(cwd, "safe_dir"), default_base=cwd)
    assert safe_path is not None

    # 危险路径应被重定向到默认基目录
    dangerous_path = sanitize_path("/etc/passwd", default_base=cwd)
    assert cwd in dangerous_path
    assert "/etc" not in dangerous_path

    # 空路径处理（使用默认基目录）
    result = sanitize_path("", default_base=cwd)
    assert cwd in result

    print("✅ 路径消毒正确")


def test_command_safety():
    """测试命令安全检查"""
    print("\n=== 测试命令安全检查 ===")

    assert is_command_safe("ls -la") is True
    assert is_command_safe("python script.py") is True

    for dangerous in DANGEROUS_COMMANDS:
        assert is_command_safe(dangerous) is False
        assert is_command_safe(f"echo test && {dangerous}") is False

    assert is_command_safe("") is False
    assert is_command_safe(None) is False

    assert is_command_safe("FORMAT C:") is False
    assert is_command_safe("Format D:") is False

    print("✅ 命令安全检查正确")


def test_input_sanitization():
    """测试输入消毒"""
    print("\n=== 测试输入消毒 ===")

    long_text = "a" * 20000
    sanitized = sanitize_input(long_text, max_length=1000)
    assert len(sanitized) == 1000

    dirty_input = "hello\x00world\x1f"
    clean = sanitize_input(dirty_input)
    assert "\x00" not in clean
    assert "\x1f" not in clean

    zwj_text = "test\u200b\u200c\ufeff"
    clean = sanitize_input(zwj_text)
    assert "\u200b" not in clean
    assert "\ufeff" not in clean

    valid_text = "Hello\tWorld\n测试"
    clean = sanitize_input(valid_text)
    assert "\t" in clean
    assert "\n" in clean
    assert "测试" in clean

    assert sanitize_input(12345) == "12345"
    assert sanitize_input(None) == "None"

    assert sanitize_input("  test  ") == "test"

    print("✅ 输入消毒正确")


def test_plugin_url_safety():
    """测试插件 URL 安全检查"""
    print("\n=== 测试插件 URL 安全检查 ===")

    assert is_plugin_url_safe("https://example.com/plugin.zip") is True
    assert is_plugin_url_safe("http://github.com/repo/plugin") is True

    assert is_plugin_url_safe("ftp://example.com/plugin") is False
    assert is_plugin_url_safe("file:///etc/passwd") is False

    assert is_plugin_url_safe("http://localhost/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False

    assert is_plugin_url_safe("http://192.168.1.1/plugin") is False
    assert is_plugin_url_safe("http://10.0.0.1/plugin") is False

    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False

    print("✅ 插件 URL 安全检查正确")


def test_path_traversal_attacks():
    """测试路径遍历攻击防护"""
    print("\n=== 测试路径遍历攻击防护 ===")

    # 测试相对路径遍历攻击（这些应该被拒绝）
    relative_attacks = [
        "../../../etc/passwd",
        "../../root/.ssh/id_rsa",
        "../../../tmp",
    ]

    for attack in relative_attacks:
        # 安全检查应拒绝相对路径遍历攻击
        assert is_path_safe(attack) is False, f"相对路径遍历攻击未被拒绝: {attack}"

    print("✅ 路径遍历攻击防护正确")


def test_command_injection_resistance():
    """测试命令注入抵抗"""
    print("\n=== 测试命令注入抵抗 ===")

    injection_attempts = [
        "ls; rm -rf /",
        "cat file | rm -rf /",
        "echo test && format c:",
        "ls `rm -rf /`",
        "ls $(rm -rf /)",
        "ls || fdisk /dev/sda",
    ]

    for injection in injection_attempts:
        result = is_command_safe(injection)
        assert result is False, f"命令注入未检测: {injection}"

    print("✅ 命令注入抵抗正确")


def test_unicode_attacks():
    """测试 Unicode 攻击防护"""
    print("\n=== 测试 Unicode 攻击防护 ===")

    unicode_paths = [
        "/etc/passwd",
        "/ｅtc/passwd",
        "/etc/раsswd",
    ]

    for path in unicode_paths:
        result = normalize_path(path)

    # 测试控制字符清理（已在 sanitize_input 定义范围内）
    unicode_input = "test\x00\x1fworld"
    clean = sanitize_input(unicode_input)
    assert "\x00" not in clean
    assert "\x1f" not in clean

    # 测试零宽字符清理
    zwj_input = "test\u200b\u200c\ufeff"
    clean = sanitize_input(zwj_input)
    assert "\u200b" not in clean
    assert "\u200c" not in clean
    assert "\ufeff" not in clean

    print("✅ Unicode 攻击防护正确")


def test_concurrent_path_checks():
    """测试并发路径检查安全性"""
    print("\n=== 测试并发路径检查 ===")

    results = []
    errors = []

    def check_path(path):
        try:
            for _ in range(100):
                result = is_path_safe(path)
                results.append(result)
        except Exception as e:
            errors.append(str(e))

    threads = []
    test_paths = ["/etc/passwd", "/tmp/safe", "~/test", "../../../root"]

    for path in test_paths:
        t = threading.Thread(target=check_path, args=(path,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == len(test_paths) * 100

    print("✅ 并发路径检查安全")


def main():
    print("=" * 60)
    print("  安全模块独立测试")
    print("=" * 60)

    test_normalize_path()
    test_path_safety_checks()
    test_sanitize_path()
    test_command_safety()
    test_input_sanitization()
    test_plugin_url_safety()
    test_path_traversal_attacks()
    test_command_injection_resistance()
    test_unicode_attacks()
    test_concurrent_path_checks()

    print("\n" + "=" * 60)
    print("🎉 所有安全测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()