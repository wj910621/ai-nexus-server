"""
安全模块测试
覆盖路径遍历防护、命令安全检查、输入消毒、SSRF防护等关键安全功能
"""

import os
import tempfile
from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
    ALLOWED_BASE_DIRS,
)


def test_normalize_path():
    print("1. 测试路径规范化...")
    
    assert normalize_path("/tmp/test") == os.path.realpath("/tmp/test")
    assert normalize_path("~/test") == os.path.realpath(os.path.expanduser("~/test"))
    assert normalize_path("../parent/child") == os.path.abspath("../parent/child")
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None
    
    print("  ✓ 路径规范化测试通过")


def test_is_path_safe():
    print("\n2. 测试路径安全检查...")
    
    assert is_path_safe(os.path.join(os.getcwd(), "data", "test.txt")) is True
    assert is_path_safe(os.path.join(os.getcwd(), "plugins", "example")) is True
    
    assert is_path_safe("/etc/passwd") is False
    assert is_path_safe("/bin/bash") is False
    assert is_path_safe("/dev/sda") is False
    assert is_path_safe("/usr/local/bin") is False
    
    assert is_path_safe("/tmp/../etc/passwd") is False
    assert is_path_safe("../../../etc/passwd") is False
    
    assert is_path_safe("") is False
    assert is_path_safe(None) is False
    
    custom_bases = [os.getcwd()]
    assert is_path_safe(os.path.join(os.getcwd(), "valid.txt"), custom_bases) is True
    assert is_path_safe("/tmp/other.txt", custom_bases) is False
    
    print("  ✓ 路径安全检查测试通过")


def test_sanitize_path():
    print("\n3. 测试路径消毒...")
    
    safe_path = os.path.join(os.getcwd(), "data")
    result = sanitize_path("valid.txt", safe_path)
    assert os.path.commonpath([safe_path, result]) == os.path.realpath(safe_path)
    
    result = sanitize_path("../../../etc/passwd", safe_path)
    assert result == os.path.realpath(safe_path)
    
    abs_safe = os.path.abspath(os.path.join(os.getcwd(), "data"))
    result = sanitize_path(abs_safe, os.getcwd())
    assert os.path.commonpath([os.path.realpath(os.getcwd()), result]) == os.path.realpath(os.getcwd())
    
    try:
        sanitize_path("/etc/passwd")
        assert False, "应抛出异常"
    except ValueError:
        pass
    
    print("  ✓ 路径消毒测试通过")


def test_is_command_safe():
    print("\n4. 测试命令安全检查...")
    
    assert is_command_safe("ls -la") is True
    assert is_command_safe("echo hello") is True
    assert is_command_safe("cat /tmp/file.txt") is True
    
    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("rm -rf /*") is False
    assert is_command_safe("format C:") is False
    assert is_command_safe("fdisk /dev/sda") is False
    assert is_command_safe("mkfs.ext4 /dev/sda") is False
    assert is_command_safe("dd if=/dev/zero of=/dev/sda") is False
    assert is_command_safe(":(){ :|:& };:\n") is False
    assert is_command_safe("> /dev/sda") is False
    
    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    assert is_command_safe(123) is False
    
    assert is_command_safe("RM -RF /") is False
    assert is_command_safe("Format c:") is False
    
    print("  ✓ 命令安全检查测试通过")


def test_sanitize_input():
    print("\n5. 测试输入消毒...")
    
    test_input = "normal text"
    assert sanitize_input(test_input) == "normal text"
    
    long_text = "a" * 20000
    result = sanitize_input(long_text)
    assert len(result) == 10000
    
    zero_width = "hello\u200bworld"
    result = sanitize_input(zero_width)
    assert "\u200b" not in result
    assert result == "helloworld"
    
    control_chars = "hello\x00world\x0btest"
    result = sanitize_input(control_chars)
    assert "\x00" not in result
    assert "\x0b" not in result
    assert "helloworldtest" in result
    
    mixed = "  text with spaces  "
    assert sanitize_input(mixed) == "text with spaces"
    
    non_str = 123
    assert sanitize_input(non_str) == "123"
    
    print("  ✓ 输入消毒测试通过")


def test_is_plugin_url_safe():
    print("\n6. 测试插件URL安全检查（SSRF防护）...")
    
    assert is_plugin_url_safe("https://github.com/example/plugin.git") is True
    assert is_plugin_url_safe("https://www.npmjs.com/package/example") is True
    
    assert is_plugin_url_safe("http://localhost:8080/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False
    assert is_plugin_url_safe("http://[::1]/plugin") is False
    assert is_plugin_url_safe("http://localhost/plugin") is False
    
    assert is_plugin_url_safe("http://10.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://192.168.1.1/plugin") is False
    assert is_plugin_url_safe("http://172.16.0.1/plugin") is False
    
    assert is_plugin_url_safe("ftp://github.com/plugin") is False
    assert is_plugin_url_safe("file:///etc/passwd") is False
    
    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False
    assert is_plugin_url_safe(123) is False
    
    assert is_plugin_url_safe("https://") is False
    assert is_plugin_url_safe("https://github.com") is True
    
    print("  ✓ 插件URL安全检查测试通过")


def test_get_safe_work_dir():
    print("\n7. 测试安全工作目录...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            work_dir = get_safe_work_dir("test_data")
            assert os.path.isdir(work_dir)
            assert "test_data" in work_dir
        finally:
            os.chdir(original_cwd)
    
    print("  ✓ 安全工作目录测试通过")


def main():
    print("=" * 60)
    print("  安全模块测试")
    print("=" * 60)
    
    test_normalize_path()
    test_is_path_safe()
    test_sanitize_path()
    test_is_command_safe()
    test_sanitize_input()
    test_is_plugin_url_safe()
    test_get_safe_work_dir()
    
    print("\n" + "=" * 60)
    print("🎉 安全模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()