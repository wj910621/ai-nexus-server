"""
安全工具模块测试
覆盖：路径遍历防护、敏感路径拒绝、命令注入拦截、输入消毒、SSRF 防护
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_normalize_path_valid():
    """合法路径规范化"""
    import security

    result = security.normalize_path("/tmp/test.txt")
    assert result is not None
    assert os.path.isabs(result)

    # 用户目录展开
    result2 = security.normalize_path("~/Documents")
    assert result2 is not None
    assert "~" not in result2

    print("  ✓ 合法路径规范化正确")


def test_normalize_path_invalid():
    """非法路径返回 None"""
    import security

    assert security.normalize_path("") is None
    assert security.normalize_path(None) is None
    assert security.normalize_path(123) is None

    print("  ✓ 非法路径返回 None")


def test_normalize_path_traversal():
    """路径穿越 (..) 被解析为绝对路径"""
    import security

    result = security.normalize_path("/tmp/../etc/passwd")
    # normalize_path 会解析 .. 并返回真实路径，但 is_path_safe 会阻止
    assert result is not None  # 规范化本身不拒绝
    assert "/etc/" in result or "\\etc\\" in result

    print("  ✓ 路径穿越被规范化解析")


def test_is_path_safe_denied_paths():
    """敏感系统路径被拒绝"""
    import security

    assert security.is_path_safe("/etc/passwd") is False
    assert security.is_path_safe("/bin/ls") is False
    assert security.is_path_safe("/usr/bin/python") is False
    assert security.is_path_safe("/proc/self") is False
    assert security.is_path_safe("/dev/null") is False
    assert security.is_path_safe("/sys/kernel") is False

    # Windows 路径在 Linux 上会被 resolve 为实际路径（可能在允许目录下），
    # 仅在 Windows 环境下测试 Windows 路径拒绝
    if os.name == "nt":
        assert security.is_path_safe("C:\\Windows\\System32") is False
        assert security.is_path_safe("C:\\Program Files\\App") is False

    print("  ✓ 敏感系统路径被正确拒绝")


def test_is_path_safe_allowed_dirs():
    """允许目录内的路径通过"""
    import security

    # 当前工作目录应允许
    cwd = os.getcwd()
    assert security.is_path_safe(os.path.join(cwd, "data", "test.txt")) is True

    # 用户主目录应允许
    home = os.path.expanduser("~")
    assert security.is_path_safe(os.path.join(home, "Documents", "file.txt")) is True

    print("  ✓ 允许目录内路径通过")


def test_is_path_safe_traversal_blocked():
    """路径穿越越界被阻止"""
    import security

    cwd = os.getcwd()
    # 从允许目录穿越到 /etc
    traversal = os.path.join(cwd, "data", "..", "..", "..", "etc", "passwd")
    assert security.is_path_safe(traversal) is False

    print("  ✓ 路径穿越越界被阻止")


def test_is_path_safe_custom_bases():
    """自定义允许基目录"""
    import security

    tmp_dir = tempfile.gettempdir() if os.name != "nt" else os.environ.get("TEMP", "/tmp")
    test_path = os.path.join(tmp_dir, "safe_file.txt")
    # 默认不允许 /tmp（除非它是 home 的子目录）
    default_result = security.is_path_safe(test_path)
    # 使用自定义基目录
    custom_result = security.is_path_safe(test_path, allowed_bases=[tmp_dir])
    assert custom_result is True

    print("  ✓ 自定义允许基目录正确")


def test_sanitize_path_safe():
    """安全路径原样返回"""
    import security

    cwd = os.getcwd()
    safe_path = os.path.join(cwd, "data", "file.txt")
    result = security.sanitize_path(safe_path)
    assert result is not None

    print("  ✓ 安全路径原样返回")


def test_sanitize_path_unsafe_fallback():
    """不安全路径回退到默认基目录"""
    import security

    result = security.sanitize_path("/etc/passwd", default_base=os.getcwd())
    assert result is not None
    # 应回退到 cwd
    assert result.startswith(os.path.realpath(os.getcwd()))

    print("  ✓ 不安全路径回退到默认基目录")


def test_sanitize_path_no_default_raises():
    """不安全路径无默认基目录时抛异常"""
    import security

    try:
        security.sanitize_path("/etc/passwd")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "非法路径" in str(e)

    print("  ✓ 无默认基目录时抛出 ValueError")


def test_is_command_safe_dangerous():
    """危险命令被拦截"""
    import security

    assert security.is_command_safe("rm -rf /") is False
    assert security.is_command_safe("format C:") is False
    assert security.is_command_safe("dd if=/dev/zero of=/dev/sda") is False
    assert security.is_command_safe("mkfs.ext4 /dev/sda1") is False
    assert security.is_command_safe(":(){ :|:& };:") is False

    print("  ✓ 危险命令被拦截")


def test_is_command_safe_normal():
    """正常命令通过"""
    import security

    assert security.is_command_safe("ls -la") is True
    assert security.is_command_safe("python script.py") is True
    assert security.is_command_safe("git status") is True
    assert security.is_command_safe("echo hello") is True

    print("  ✓ 正常命令通过")


def test_is_command_safe_edge_cases():
    """命令检查边界条件"""
    import security

    assert security.is_command_safe("") is False
    assert security.is_command_safe(None) is False
    assert security.is_command_safe(123) is False

    print("  ✓ 命令检查边界条件正确")


def test_sanitize_input_basic():
    """基础输入消毒"""
    import security

    # 正常文本不变
    assert security.sanitize_input("Hello World") == "Hello World"

    # 长度限制
    long_text = "A" * 20000
    result = security.sanitize_input(long_text, max_length=100)
    assert len(result) <= 100

    print("  ✓ 基础输入消毒正确")


def test_sanitize_input_control_chars():
    """控制字符被移除"""
    import security

    # 零宽字符
    assert security.sanitize_input("hello\u200bworld") == "helloworld"
    # 控制字符（保留换行和制表符）
    text = "line1\nline2\ttab\x00null"
    result = security.sanitize_input(text)
    assert "\x00" not in result
    assert "\n" in result
    assert "\t" in result

    print("  ✓ 控制字符被正确移除")


def test_sanitize_input_non_string():
    """非字符串输入被转换"""
    import security

    result = security.sanitize_input(12345)
    assert result == "12345"

    print("  ✓ 非字符串输入被转换")


def test_is_plugin_url_safe_valid():
    """合法插件 URL 通过"""
    import security
    from unittest.mock import patch

    # Mock DNS 解析以避免网络依赖
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 80))]):
        assert security.is_plugin_url_safe("https://github.com/user/plugin") is True
        assert security.is_plugin_url_safe("http://example.com/plugin.zip") is True

    print("  ✓ 合法插件 URL 通过")


def test_is_plugin_url_safe_blocked_protocols():
    """非 HTTP(S) 协议被拒绝"""
    import security

    assert security.is_plugin_url_safe("file:///etc/passwd") is False
    assert security.is_plugin_url_safe("ftp://example.com/file") is False
    assert security.is_plugin_url_safe("javascript:alert(1)") is False

    print("  ✓ 非 HTTP(S) 协议被拒绝")


def test_is_plugin_url_safe_localhost():
    """本地地址被拒绝（防 SSRF）"""
    import security

    assert security.is_plugin_url_safe("http://localhost/admin") is False
    assert security.is_plugin_url_safe("http://127.0.0.1/admin") is False
    assert security.is_plugin_url_safe("http://0.0.0.0/admin") is False
    assert security.is_plugin_url_safe("http://[::1]/admin") is False

    print("  ✓ 本地地址被拒绝（SSRF 防护）")


def test_is_plugin_url_safe_private_ip():
    """内网 IP 被拒绝（防 SSRF）"""
    import security

    # 直接使用内网 IP 地址
    assert security.is_plugin_url_safe("http://10.0.0.1/internal") is False
    assert security.is_plugin_url_safe("http://172.16.0.1/internal") is False
    assert security.is_plugin_url_safe("http://192.168.1.1/internal") is False

    print("  ✓ 内网 IP 被拒绝（SSRF 防护）")


def test_is_plugin_url_safe_empty():
    """空/无效 URL 被拒绝"""
    import security

    assert security.is_plugin_url_safe("") is False
    assert security.is_plugin_url_safe(None) is False
    assert security.is_plugin_url_safe(123) is False

    print("  ✓ 空/无效 URL 被拒绝")


def test_get_safe_work_dir():
    """安全工作目录获取"""
    import security

    work_dir = security.get_safe_work_dir("data")
    assert os.path.isabs(work_dir)
    assert "data" in work_dir

    print("  ✓ 安全工作目录获取正确")


def main():
    import tempfile

    print("=== 安全工具模块测试 ===\n")

    test_normalize_path_valid()
    test_normalize_path_invalid()
    test_normalize_path_traversal()
    test_is_path_safe_denied_paths()
    test_is_path_safe_allowed_dirs()
    test_is_path_safe_traversal_blocked()
    test_is_path_safe_custom_bases()
    test_sanitize_path_safe()
    test_sanitize_path_unsafe_fallback()
    test_sanitize_path_no_default_raises()
    test_is_command_safe_dangerous()
    test_is_command_safe_normal()
    test_is_command_safe_edge_cases()
    test_sanitize_input_basic()
    test_sanitize_input_control_chars()
    test_sanitize_input_non_string()
    test_is_plugin_url_safe_valid()
    test_is_plugin_url_safe_blocked_protocols()
    test_is_plugin_url_safe_localhost()
    test_is_plugin_url_safe_private_ip()
    test_is_plugin_url_safe_empty()
    test_get_safe_work_dir()

    print("\n=== 安全工具模块测试完成 ===")


if __name__ == "__main__":
    main()
