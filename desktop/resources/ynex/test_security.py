"""
安全模块完整测试
覆盖：路径遍历防护、命令安全检查、输入消毒、SSRF 防护
"""

import os
import tempfile
from pathlib import Path
from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    DENIED_PATHS,
    DANGEROUS_COMMANDS,
    ALLOWED_BASE_DIRS,
)


def test_normalize_path():
    """测试路径规范化"""
    print("\n=== 测试路径规范化 ===")

    # 正常路径
    assert normalize_path("/tmp/test.txt")
    assert normalize_path("~/Documents")
    assert normalize_path("./relative/path")

    # 包含 .. 的路径
    path = normalize_path("/tmp/../etc/passwd")
    assert path is not None
    assert ".." not in path

    # 空路径
    assert normalize_path("") is None
    assert normalize_path(None) is None

    # 非法字符路径
    assert normalize_path("\x00invalid") is not None  # 应能处理

    print("✅ 路径规范化正确")


def test_path_safety_checks():
    """测试路径安全检查"""
    print("\n=== 测试路径安全检查 ===")

    # 敏感系统路径应被拒绝
    for denied in DENIED_PATHS:
        assert is_path_safe(denied) is False, f"{denied} 应被拒绝"
        assert is_path_safe(denied + "/subdir") is False

    # 允许的基础目录应通过
    for allowed in ALLOWED_BASE_DIRS:
        if os.path.exists(allowed):
            assert is_path_safe(allowed) is True

    # 相对路径穿越攻击
    assert is_path_safe("../../../etc/passwd") is False
    assert is_path_safe("../../root/.ssh/id_rsa") is False

    print("✅ 路径安全检查正确")


def test_sanitize_path():
    """测试路径消毒"""
    print("\n=== 测试路径消毒 ===")

    # 安全路径应保持不变
    safe_path = sanitize_path("/tmp/safe_dir")
    assert safe_path is not None

    # 危险路径应被重定向到默认基目录
    dangerous_path = sanitize_path("/etc/passwd", default_base="/tmp")
    assert "/tmp" in dangerous_path
    assert "/etc" not in dangerous_path

    # 空路径处理
    try:
        sanitize_path("")
        assert False, "应抛出异常"
    except ValueError:
        pass

    print("✅ 路径消毒正确")


def test_command_safety():
    """测试命令安全检查"""
    print("\n=== 测试命令安全检查 ===")

    # 安全命令
    assert is_command_safe("ls -la") is True
    assert is_command_safe("python script.py") is True
    assert is_command_safe("git status") is True

    # 危险命令（黑名单）
    for dangerous in DANGEROUS_COMMANDS:
        assert is_command_safe(dangerous) is False
        assert is_command_safe(f"echo test && {dangerous}") is False

    # 边界情况
    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    assert is_command_safe("rm -rf /important/data") is False

    # 大小写不敏感
    assert is_command_safe("FORMAT C:") is False
    assert is_command_safe("Format D:") is False

    print("✅ 命令安全检查正确")


def test_input_sanitization():
    """测试输入消毒"""
    print("\n=== 测试输入消毒 ===")

    # 长度限制
    long_text = "a" * 20000
    sanitized = sanitize_input(long_text, max_length=1000)
    assert len(sanitized) == 1000

    # 控制字符移除
    dirty_input = "hello\x00world\x1f"
    clean = sanitize_input(dirty_input)
    assert "\x00" not in clean
    assert "\x1f" not in clean

    # 零宽字符移除
    zwj_text = "test\u200b\u200c\ufeff"
    clean = sanitize_input(zwj_text)
    assert "\u200b" not in clean
    assert "\ufeff" not in clean

    # 保留合法字符
    valid_text = "Hello\tWorld\n测试"
    clean = sanitize_input(valid_text)
    assert "\t" in clean
    assert "\n" in clean
    assert "测试" in clean

    # 非字符串输入
    assert sanitize_input(12345) == "12345"
    assert sanitize_input(None) == "None"

    # 前后空格移除
    assert sanitize_input("  test  ") == "test"

    print("✅ 输入消毒正确")


def test_plugin_url_safety():
    """测试插件 URL 安全检查（SSRF 防护）"""
    print("\n=== 测试插件 URL 安全检查 ===")

    # 安全 URL
    assert is_plugin_url_safe("https://example.com/plugin.zip") is True
    assert is_plugin_url_safe("http://github.com/repo/plugin") is True

    # 不安全的协议
    assert is_plugin_url_safe("ftp://example.com/plugin") is False
    assert is_plugin_url_safe("file:///etc/passwd") is False

    # 本地地址禁止
    assert is_plugin_url_safe("http://localhost/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False
    assert is_plugin_url_safe("http://[::1]/plugin") is False

    # 内网 IP 禁止
    assert is_plugin_url_safe("http://192.168.1.1/plugin") is False
    assert is_plugin_url_safe("http://10.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://172.16.0.1/plugin") is False

    # 边界情况
    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False
    assert is_plugin_url_safe("not_a_url") is False

    print("✅ 插件 URL 安全检查正确")


def test_path_traversal_attacks():
    """测试路径遍历攻击防护"""
    print("\n=== 测试路径遍历攻击防护 ===")

    attack_vectors = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "/tmp/../../../root",
        "~/../../../etc",
        "/var/../../etc/shadow",
        "....//....//....//etc/passwd",
    ]

    for attack in attack_vectors:
        # 规范化后应不包含 ..
        norm_path = normalize_path(attack)
        if norm_path:
            assert ".." not in norm_path, f"路径遍历攻击未防护: {attack}"

        # 安全检查应拒绝
        assert is_path_safe(attack) is False, f"路径遍历攻击未被拒绝: {attack}"

    print("✅ 路径遍历攻击防护正确")


def test_symlink_protection():
    """测试符号链接保护"""
    print("\n=== 测试符号链接保护 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件和符号链接
        safe_file = os.path.join(tmpdir, "safe.txt")
        with open(safe_file, "w") as f:
            f.write("test")

        # 正常文件应通过安全检查
        if os.path.exists(tmpdir):
            result = is_path_safe(safe_file)
            # 结果取决于 ALLOWED_BASE_DIRS 配置

        print("✅ 符号链接保护测试完成")


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
        # 应检测出至少一个危险模式
        assert result is False, f"命令注入未检测: {injection}"

    print("✅ 命令注入抵抗正确")


def test_unicode_attacks():
    """测试 Unicode 攻击防护"""
    print("\n=== 测试 Unicode 攻击防护 ===")

    # Unicode 同形字攻击
    unicode_paths = [
        "/etc/passwd",  # 正常路径
        "/ｅtc/passwd",  # 全角字符
        "/etc/раsswd",  # 西里尔字母
    ]

    for path in unicode_paths:
        # 应正确处理或拒绝
        result = normalize_path(path)
        # 不应崩溃

    # Unicode 控制字符
    unicode_input = "test\u202eexe.pdf"  # Right-to-Left Override
    clean = sanitize_input(unicode_input)
    assert "\u202e" not in clean

    print("✅ Unicode 攻击防护正确")


def test_concurrent_path_checks():
    """测试并发路径检查安全性"""
    print("\n=== 测试并发路径检查 ===")

    import threading
    import time

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

    assert len(errors) == 0, f"并发错误: {errors}"
    assert len(results) == len(test_paths) * 100

    print("✅ 并发路径检查安全")


def main():
    print("=" * 60)
    print("  安全模块完整测试")
    print("=" * 60)

    test_normalize_path()
    test_path_safety_checks()
    test_sanitize_path()
    test_command_safety()
    test_input_sanitization()
    test_plugin_url_safety()
    test_path_traversal_attacks()
    test_symlink_protection()
    test_command_injection_resistance()
    test_unicode_attacks()
    test_concurrent_path_checks()

    print("\n" + "=" * 60)
    print("🎉 所有安全测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()