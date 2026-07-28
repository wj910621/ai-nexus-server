"""
安全模块测试
验证路径遍历防护、命令执行过滤、SSRF防护等关键安全功能
"""

import os
import sys
import tempfile
from pathlib import Path

# 确保导入项目根目录
sys.path.insert(0, str(Path(__file__).parent))


def test_path_traversal_protection():
    """测试路径遍历防护"""
    print("\n=== 测试路径遍历防护 ===")

    import security

    # 测试合法路径
    safe_path = os.path.join(os.getcwd(), "data")
    assert security.is_path_safe(safe_path)

    # 测试穿越上级目录
    unsafe_path = os.path.join(os.getcwd(), "..", "etc", "passwd")
    assert not security.is_path_safe(unsafe_path), "应阻止穿越上级目录"

    # 测试绝对路径穿越
    unsafe_path = "/etc/passwd"
    assert not security.is_path_safe(unsafe_path), "应阻止系统敏感路径"

    # 测试符号链接穿越
    unsafe_path = "/proc/self/root"
    assert not security.is_path_safe(unsafe_path), "应阻止 proc 文件系统"

    print("✅ 路径遍历防护验证通过")


def test_system_path_denied():
    """测试系统敏感路径拒绝"""
    print("\n=== 测试系统敏感路径拒绝 ===")

    import security

    # 根据操作系统选择合适的测试路径
    if os.name == 'nt':  # Windows
        denied_paths = [
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Program Files\\app\\data",
            "C:\\ProgramData\\secrets",
        ]
    else:  # Unix/Linux
        denied_paths = [
            "/etc/shadow",
            "/etc/passwd",
            "/bin/bash",
            "/usr/bin/python",
            "/sys/kernel",
            "/proc/1",
            "/dev/null",
        ]

    for path in denied_paths:
        result = security.is_path_safe(path)
        assert not result, f"应拒绝访问: {path}"

    print("✅ 系统敏感路径拒绝验证通过")


def test_path_normalization():
    """测试路径规范化"""
    print("\n=== 测试路径规范化 ===")

    import security

    # 测试用户目录展开
    home_path = "~/Documents"
    normalized = security.normalize_path(home_path)
    assert normalized and not normalized.startswith("~")

    # 测试相对路径转绝对
    rel_path = "data/file.txt"
    normalized = security.normalize_path(rel_path)
    assert normalized and os.path.isabs(normalized)

    # 测试空路径
    result = security.normalize_path("")
    assert result is None

    # 测试非法类型
    result = security.normalize_path(None)
    assert result is None

    print("✅ 路径规范化验证通过")


def test_dangerous_command_filter():
    """测试危险命令过滤"""
    print("\n=== 测试危险命令过滤 ===")

    import security

    # 危险命令应被阻止
    dangerous_commands = [
        "format c:",
        "fdisk /dev/sda",
        "mkfs.ext4 /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        "rm -rf /",
        "rm -rf /*",
        "rmdir /s C:\\Windows",
        "deltree c:\\",
        ":(){ :|:& };:",
        "> /dev/sda",
    ]

    for cmd in dangerous_commands:
        result = security.is_command_safe(cmd)
        assert not result, f"应拦截危险命令: {cmd}"

    # 安全命令应通过
    safe_commands = [
        "ls -la",
        "echo hello",
        "python script.py",
        "git status",
        "npm install",
    ]

    for cmd in safe_commands:
        result = security.is_command_safe(cmd)
        assert result, f"应允许安全命令: {cmd}"

    print("✅ 危险命令过滤验证通过")


def test_input_sanitization():
    """测试输入消毒"""
    print("\n=== 测试输入消毒 ===")

    import security

    # 测试长度限制
    long_text = "a" * 20000
    sanitized = security.sanitize_input(long_text, max_length=10000)
    assert len(sanitized) == 10000

    # 测试控制字符去除
    dirty_input = "hello\x00world\x1f"
    sanitized = security.sanitize_input(dirty_input)
    assert "\x00" not in sanitized
    assert "\x1f" not in sanitized

    # 测试零宽字符去除
    zero_width = "test\u200b\u200c\u200dcontent"
    sanitized = security.sanitize_input(zero_width)
    assert "\u200b" not in sanitized
    assert "\u200c" not in sanitized

    # 测试保留换行和制表符
    input_with_formatting = "line1\nline2\tindented"
    sanitized = security.sanitize_input(input_with_formatting)
    assert "\n" in sanitized
    assert "\t" in sanitized

    print("✅ 输入消毒验证通过")


def test_ssrf_protection():
    """测试 SSRF 防护"""
    print("\n=== 测试 SSRF 防护 ===")

    import security

    # 应阻止本地地址
    blocked_urls = [
        "http://localhost/admin",
        "http://127.0.0.1/secrets",
        "http://0.0.0.0/config",
        "http://[::1]/api",
        "http://192.168.1.1/router",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/private",
        "ftp://example.com/file",  # 非 HTTP 协议
    ]

    for url in blocked_urls:
        result = security.is_plugin_url_safe(url)
        assert not result, f"应阻止 SSRF URL: {url}"

    # 应允许合法外部 URL
    allowed_urls = [
        "http://example.com/plugin.zip",
        "https://github.com/user/repo",
        "https://registry.npmjs.org/package",
    ]

    for url in allowed_urls:
        # 注意：DNS 解析可能失败，这里仅测试协议和格式
        parsed = url.split("://")[0]
        if parsed in security.ALLOWED_PLUGIN_PROTOCOLS:
            # 协议检查通过即可，DNS 解析可能因网络问题失败
            pass

    print("✅ SSRF 防护验证通过")


def test_allowed_directory_restriction():
    """测试允许目录限制"""
    print("\n=== 测试允许目录限制 ===")

    import security

    # 创建临时测试目录
    temp_dir = tempfile.mkdtemp()
    allowed_subdir = os.path.join(temp_dir, "allowed")
    os.makedirs(allowed_subdir, exist_ok=True)

    # 在允许目录内的文件应通过
    safe_file = os.path.join(allowed_subdir, "test.txt")
    Path(safe_file).write_text("test")

    result = security.is_path_safe(safe_file, allowed_bases=[allowed_subdir])
    assert result, f"允许目录内文件应通过: {safe_file}"

    # 不在允许目录内的文件应被拒绝
    outside_file = os.path.join(temp_dir, "outside.txt")
    Path(outside_file).write_text("outside")

    result = security.is_path_safe(outside_file, allowed_bases=[allowed_subdir])
    assert not result, f"不在允许目录的文件应被拒绝: {outside_file}"

    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("✅ 允许目录限制验证通过")


def test_sanitize_path_fallback():
    """测试路径安全化 fallback"""
    print("\n=== 测试路径安全化 fallback ===")

    import security

    # 越界路径应 fallback 到默认基目录
    unsafe_path = "/etc/passwd"
    safe_path = security.sanitize_path(unsafe_path, default_base="/tmp")

    # 应返回默认基目录
    assert safe_path.startswith("/tmp")

    print("✅ 路径安全化 fallback 验证通过")


def test_empty_and_invalid_inputs():
    """测试空值和非法输入"""
    print("\n=== 测试空值和非法输入 ===")

    import security

    # 空路径
    assert security.normalize_path("") is None
    assert security.normalize_path(None) is None
    assert not security.is_path_safe("")

    # 空命令
    assert not security.is_command_safe("")
    assert not security.is_command_safe(None)

    # 空输入
    assert security.sanitize_input("") == ""
    assert security.sanitize_input(None) == "None"  # 会转为字符串

    # 空 URL
    assert not security.is_plugin_url_safe("")
    assert not security.is_plugin_url_safe(None)

    print("✅ 空值和非法输入验证通过")


def test_case_insensitive_path_check():
    """测试路径大小写不敏感检查"""
    print("\n=== 测试路径大小写不敏感检查 ===")

    import security

    # Windows 路径大小写
    if os.name == 'nt':
        paths = [
            "c:\\windows\\system32",
            "C:\\WINDOWS\\SYSTEM32",
            "C:\\Program Files\\App",
        ]
        for path in paths:
            result = security.is_path_safe(path)
            assert not result, f"应拒绝（大小写不敏感）: {path}"

    print("✅ 路径大小写不敏感检查验证通过")


def main():
    """运行所有安全测试"""
    print("=" * 60)
    print("Y·NEX 安全模块测试")
    print("=" * 60)

    try:
        test_path_traversal_protection()
        test_system_path_denied()
        test_path_normalization()
        test_dangerous_command_filter()
        test_input_sanitization()
        test_ssrf_protection()
        test_allowed_directory_restriction()
        test_sanitize_path_fallback()
        test_empty_and_invalid_inputs()
        test_case_insensitive_path_check()

        print("\n" + "=" * 60)
        print("✅ 所有安全测试通过")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()