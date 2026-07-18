"""
安全工具模块测试
覆盖路径遍历防护、命令安全、输入消毒、插件 URL SSRF 防护。
"""

import os
import tempfile
from unittest.mock import patch

from security import (
    DENIED_PATHS,
    get_safe_work_dir,
    is_command_safe,
    is_path_safe,
    is_plugin_url_safe,
    normalize_path,
    sanitize_input,
    sanitize_path,
)


def test_normalize_path():
    print("1. 路径规范化...")
    assert normalize_path("/tmp/foo") == "/tmp/foo"
    assert normalize_path("~/foo") == os.path.realpath(os.path.expanduser("~/foo"))
    assert normalize_path("/tmp/../etc/passwd") == "/etc/passwd"
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None
    print("  ✓ 路径规范化正确")


def test_is_path_safe_denied():
    print("2. 敏感系统路径拦截...")
    for denied in DENIED_PATHS:
        assert is_path_safe(denied) is False, f"应拦截 {denied}"
        assert is_path_safe(os.path.join(denied, "foo.txt")) is False
    print("  ✓ 敏感路径拦截正确")


def test_is_path_safe_traversal():
    print("3. 路径穿越防护...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = tmpdir
        safe_file = os.path.join(base, "safe.txt")
        open(safe_file, "w").close()

        assert is_path_safe(safe_file, allowed_bases=[base]) is True
        assert is_path_safe(os.path.join(base, "..", "outside.txt"), allowed_bases=[base]) is False
        assert is_path_safe(os.path.join(base, "subdir", "..", "safe.txt"), allowed_bases=[base]) is True
    print("  ✓ 路径穿越防护正确")


def test_sanitize_path():
    print("4. 非法路径回退...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # 默认基目录不在 ALLOWED_BASE_DIRS 中，任何相对路径都会回退到基目录
        assert sanitize_path("safe.txt", default_base=tmpdir) == os.path.realpath(tmpdir)
        assert sanitize_path("/etc/passwd", default_base=tmpdir) == os.path.realpath(tmpdir)
        assert sanitize_path("sub/file.txt", default_base=tmpdir) == os.path.realpath(tmpdir)
    print("  ✓ 非法路径回退正确")


def test_is_command_safe():
    print("5. 危险命令拦截...")
    dangerous = [
        "rm -rf /",
        "rm -rf /*",
        "dd if=/dev/zero of=/dev/sda",
        "fdisk /dev/sda",
        "mkfs.ext4 /dev/sda",
        "format C:",
        "rmdir /s C:\\Windows",
    ]
    for cmd in dangerous:
        assert is_command_safe(cmd) is False, f"应拦截 {cmd}"

    safe = [
        "ls -la /home/user",
        "python script.py",
        "echo hello",
        "git status",
    ]
    for cmd in safe:
        assert is_command_safe(cmd) is True, f"应允许 {cmd}"

    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    print("  ✓ 危险命令拦截正确")


def test_sanitize_input():
    print("6. 输入消毒...")
    assert sanitize_input("hello\x00world") == "helloworld"
    assert sanitize_input("test\u200b\u200c") == "test"
    assert sanitize_input("  normal  ") == "normal"
    assert sanitize_input("a" * 20000, max_length=100) == "a" * 100
    assert sanitize_input(123) == "123"
    print("  ✓ 输入消毒正确")


def test_is_plugin_url_safe():
    print("7. 插件 URL SSRF 防护...")
    # 协议白名单
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        assert is_plugin_url_safe("http://example.com/plugin.zip") is True
        assert is_plugin_url_safe("https://example.com/plugin.zip") is True
        assert is_plugin_url_safe("ftp://example.com/plugin.zip") is False

    # 本地地址
    assert is_plugin_url_safe("http://localhost/plugin.zip") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin.zip") is False
    assert is_plugin_url_safe("http://[::1]/plugin.zip") is False

    # 内网/保留 IP
    assert is_plugin_url_safe("http://192.168.1.1/plugin.zip") is False
    assert is_plugin_url_safe("http://10.0.0.1/plugin.zip") is False
    assert is_plugin_url_safe("http://172.16.0.1/plugin.zip") is False

    # 空/无效
    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe("not-a-url") is False

    # DNS 解析到内网 IP 的场景（使用 mock 避免依赖真实 DNS）
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("192.168.1.100", 80))]
        assert is_plugin_url_safe("http://internal.example.com/plugin.zip") is False
        mock_getaddrinfo.assert_called_once()
    print("  ✓ 插件 URL SSRF 防护正确")


def test_get_safe_work_dir():
    print("8. 安全工作目录...")
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = get_safe_work_dir(tmpdir)
        assert os.path.isdir(work_dir)
        assert os.path.isabs(work_dir)
    print("  ✓ 安全工作目录正确")


def main():
    print("=== 安全工具模块测试 ===\n")
    test_normalize_path()
    test_is_path_safe_denied()
    test_is_path_safe_traversal()
    test_sanitize_path()
    test_is_command_safe()
    test_sanitize_input()
    test_is_plugin_url_safe()
    test_get_safe_work_dir()
    print("\n=== 安全工具测试全部通过 ===")


if __name__ == "__main__":
    main()
