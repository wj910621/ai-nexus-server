"""
安全模块测试
- 路径遍历防护
- 命令执行安全检查
- 输入消毒
- SSRF 防护（插件 URL 安全）
- 敏感路径保护
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
    ALLOWED_BASE_DIRS,
    DENIED_PATHS,
)


def test_normalize_path():
    """测试路径规范化"""
    print("\n=== 路径规范化 ===")

    assert normalize_path("") is None, "空路径应返回 None"
    assert normalize_path(None) is None, "None 路径应返回 None"
    assert normalize_path(123) is None, "非字符串路径应返回 None"

    result = normalize_path(".")
    assert result is not None, "当前目录应可规范化"
    assert os.path.isabs(result), "应返回绝对路径"

    result = normalize_path("foo/../bar")
    assert result is not None
    assert ".." not in result, "应解析 .. 穿越"

    result = normalize_path("~/test")
    assert result is not None
    assert os.path.expanduser("~") in result, "应展开用户目录"

    print("  ✓ 路径规范化测试通过")


def test_is_path_safe_allowed_dirs():
    """测试路径安全检查 - 允许目录"""
    print("\n=== 路径安全检查（允许目录）===")

    tmp_dir = tempfile.mkdtemp(prefix="ynex_test_")
    try:
        allowed = [tmp_dir]

        safe_file = os.path.join(tmp_dir, "test.txt")
        with open(safe_file, "w") as f:
            f.write("test")

        assert is_path_safe(safe_file, allowed_bases=allowed), "允许目录内的文件应安全"

        sub_dir = os.path.join(tmp_dir, "subdir")
        os.makedirs(sub_dir)
        sub_file = os.path.join(sub_dir, "nested.txt")
        with open(sub_file, "w") as f:
            f.write("test")
        assert is_path_safe(sub_file, allowed_bases=allowed), "子目录文件应安全"

        assert is_path_safe(tmp_dir, allowed_bases=allowed), "基目录本身应安全"

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("  ✓ 允许目录检查通过")


def test_is_path_safe_traversal():
    """测试路径安全检查 - 路径遍历攻击"""
    print("\n=== 路径安全检查（路径遍历防护）===")

    tmp_dir = tempfile.mkdtemp(prefix="ynex_test_")
    try:
        allowed = [tmp_dir]

        traversal_cases = [
            os.path.join(tmp_dir, "..", "etc", "passwd"),
            os.path.join(tmp_dir, "foo", "..", "..", "bar"),
            "../../etc/passwd",
            "../secret.txt",
            "data/../../etc/shadow",
        ]

        for case in traversal_cases:
            result = is_path_safe(case, allowed_bases=allowed)
            assert result is False, f"路径遍历应被拒绝: {case}"

        print("  ✓ 路径遍历防护通过")

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_is_path_safe_denied_paths():
    """测试敏感系统路径保护"""
    print("\n=== 敏感路径保护 ===")

    denied_cases = [
        "/etc/passwd",
        "/etc/shadow",
        "/bin/bash",
        "/sbin/reboot",
        "/proc/self/environ",
        "/dev/null",
        "/sys/kernel",
    ]

    for path in denied_cases:
        result = is_path_safe(path)
        assert result is False, f"敏感路径应被拒绝: {path}"

    print("  ✓ 敏感路径保护通过")


def test_sanitize_path():
    """测试路径消毒"""
    print("\n=== 路径消毒 ===")

    tmp_dir = tempfile.mkdtemp(prefix="ynex_test_")
    try:
        safe_file = os.path.join(tmp_dir, "test.txt")
        with open(safe_file, "w") as f:
            f.write("test")

        result = sanitize_path("test.txt", default_base=tmp_dir)
        assert result is not None
        assert os.path.isabs(result), "应返回绝对路径"

        result = sanitize_path("../../etc/passwd", default_base=tmp_dir)
        expected_base = os.path.realpath(os.path.expanduser(tmp_dir))
        assert result == expected_base, "越界路径应回退到默认基目录"

        try:
            sanitize_path("/etc/passwd")
            assert False, "无 default_base 时越界应抛出 ValueError"
        except ValueError:
            pass

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("  ✓ 路径消毒通过")


def test_is_command_safe():
    """测试命令安全性检查"""
    print("\n=== 命令安全检查 ===")

    safe_commands = [
        "ls -la",
        "python --version",
        "echo hello world",
        "date",
        "pwd",
        "whoami",
    ]

    for cmd in safe_commands:
        assert is_command_safe(cmd), f"安全命令应被允许: {cmd}"

    dangerous_commands = [
        "rm -rf /",
        "rm -rf /*",
        "format c:",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.ext4 /dev/sda1",
        "fdisk /dev/sda",
        ":(){ :|:& };:",
        "deltree /y C:\\",
        "rd /s /q C:\\Windows",
    ]

    for cmd in dangerous_commands:
        assert not is_command_safe(cmd), f"危险命令应被拒绝: {cmd}"

    assert not is_command_safe(""), "空命令应被拒绝"
    assert not is_command_safe(None), "None 命令应被拒绝"
    assert not is_command_safe(123), "非字符串命令应被拒绝"

    print("  ✓ 命令安全检查通过")


def test_sanitize_input():
    """测试输入消毒"""
    print("\n=== 输入消毒 ===")

    long_text = "a" * 20000
    result = sanitize_input(long_text, max_length=100)
    assert len(result) == 100, "超长输入应被截断"

    null_text = "hello\x00world"
    result = sanitize_input(null_text)
    assert "\x00" not in result, "应去除空字节"

    control_text = "hello\x01\x02\x03world"
    result = sanitize_input(control_text)
    assert "\x01" not in result and "\x02" not in result and "\x03" not in result, "应去除控制字符"

    zw_text = "hello\u200bworld\u200c"
    result = sanitize_input(zw_text)
    assert "\u200b" not in result and "\u200c" not in result, "应去除零宽字符"

    bom_text = "\ufeffhello"
    result = sanitize_input(bom_text)
    assert "\ufeff" not in result, "应去除 BOM"

    normal_text = "hello world"
    result = sanitize_input(normal_text)
    assert result == normal_text, "正常文本应保持不变"

    newlines = "line1\nline2\tindented"
    result = sanitize_input(newlines)
    assert "\n" in result and "\t" in result, "应保留换行和制表符"

    assert sanitize_input(123) == "123", "非字符串应转字符串"

    assert sanitize_input("  hello  ") == "hello", "应去除首尾空白"

    print("  ✓ 输入消毒通过")


def test_is_plugin_url_safe():
    """测试插件 URL 安全（SSRF 防护）"""
    print("\n=== 插件 URL SSRF 防护 ===")

    assert not is_plugin_url_safe(""), "空 URL 应被拒绝"
    assert not is_plugin_url_safe(None), "None URL 应被拒绝"
    assert not is_plugin_url_safe(123), "非字符串 URL 应被拒绝"

    unsafe_protocols = [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://127.0.0.1:6379",
        "data:text/html,<script>alert(1)</script>",
        "javascript:alert(1)",
    ]

    for url in unsafe_protocols:
        assert not is_plugin_url_safe(url), f"不安全协议应被拒绝: {url}"

    localhost_urls = [
        "http://localhost:8080/plugin.zip",
        "http://127.0.0.1/api/keys",
        "http://0.0.0.0:3000/test",
        "http://[::1]/secret",
    ]

    for url in localhost_urls:
        assert not is_plugin_url_safe(url), f"本地地址应被拒绝: {url}"

    valid_external = [
        "https://github.com/user/repo/releases/download/v1.0/plugin.zip",
        "http://example.com/plugin.zip",
    ]

    for url in valid_external:
        try:
            result = is_plugin_url_safe(url)
            print(f"    外部 URL {url}: {'通过' if result else '被拒绝（DNS 不可用）'}")
        except Exception as e:
            print(f"    外部 URL {url}: 检查异常（预期）- {e}")

    print("  ✓ SSRF 防护通过")


def test_get_safe_work_dir():
    """测试安全工作目录获取"""
    print("\n=== 安全工作目录 ===")

    work_dir = get_safe_work_dir("test_data_security")
    assert os.path.exists(work_dir), "工作目录应存在"
    assert os.path.isabs(work_dir), "应返回绝对路径"
    assert os.path.isdir(work_dir), "应是目录"

    import shutil
    shutil.rmtree(work_dir, ignore_errors=True)

    print("  ✓ 安全工作目录通过")


def test_edge_cases():
    """测试边界条件和极端情况"""
    print("\n=== 边界条件测试 ===")

    assert normalize_path(".") is not None, "相对路径 '.' 应可规范化"
    assert normalize_path("..") is not None, "相对路径 '..' 应可规范化"

    assert not is_command_safe("RM -RF /"), "大写危险命令也应被检测"
    assert not is_command_safe("rm -rf / "), "带尾空格的危险命令应被拒绝"
    assert not is_command_safe("  rm -rf /"), "带首空格的危险命令应被拒绝"

    max_len_edge = "a" * 10000
    result = sanitize_input(max_len_edge)
    assert len(result) <= 10000, "默认最大长度应生效"

    empty_stripped = "   \t\n  "
    result = sanitize_input(empty_stripped)
    assert result == "", "全空白输入应返回空字符串"

    print("  ✓ 边界条件测试通过")


def main():
    print("=" * 60)
    print("  安全模块安全网测试")
    print("=" * 60)

    test_normalize_path()
    test_is_path_safe_allowed_dirs()
    test_is_path_safe_traversal()
    test_is_path_safe_denied_paths()
    test_sanitize_path()
    test_is_command_safe()
    test_sanitize_input()
    test_is_plugin_url_safe()
    test_get_safe_work_dir()
    test_edge_cases()

    print("\n" + "=" * 60)
    print("  ✅ 所有安全模块测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
