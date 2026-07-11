"""
安全模块测试
覆盖路径安全检查、命令过滤、输入消毒、SSRF 防护
"""

import os
from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
)


def main():
    print("=== 安全模块测试 ===\n")

    print("1. 路径规范化...")
    assert normalize_path("/a/b/../c") is not None
    assert normalize_path("") is None
    assert normalize_path(None) is None
    print("  ✓ 规范化正确")

    print("\n2. 路径安全检查...")
    assert is_path_safe("/etc/passwd") is False
    assert is_path_safe("/bin/bash") is False
    
    assert is_path_safe("./data/test.txt") is True
    assert is_path_safe(os.path.join(os.getcwd(), "data", "test.txt")) is True
    
    assert is_path_safe("../etc/passwd") is False
    assert is_path_safe("../../etc/passwd") is False
    
    if os.name == "nt":
        assert is_path_safe("C:\\Windows\\system32") is False
        assert is_path_safe("C:\\Program Files\\") is False
    print("  ✓ 路径安全检查正确")

    print("\n3. 路径消毒...")
    sanitized = sanitize_path("/etc/passwd", default_base="./data")
    assert "etc" not in sanitized
    
    sanitized = sanitize_path("test.txt", default_base="./data")
    assert os.path.basename(sanitized) == "test.txt"
    print("  ✓ 路径消毒正确")

    print("\n4. 命令安全检查...")
    assert is_command_safe("ls -l") is True
    assert is_command_safe("pwd") is True
    
    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("format C:") is False
    assert is_command_safe(":(){ :|:& };:") is False
    assert is_command_safe("> /dev/sda") is False
    
    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    print("  ✓ 命令安全检查正确")

    print("\n5. 输入消毒...")
    test_input = "hello\x00world\x0btest"
    sanitized = sanitize_input(test_input)
    assert "\x00" not in sanitized
    assert "\x0b" not in sanitized
    assert sanitized == "helloworldtest"
    
    long_input = "a" * 20000
    sanitized = sanitize_input(long_input, max_length=100)
    assert len(sanitized) == 100
    
    assert sanitize_input(123) == "123"
    print("  ✓ 输入消毒正确")

    print("\n6. 插件 URL 安全检查（SSRF 防护）...")
    assert is_plugin_url_safe("https://github.com/test/plugin.git") is True
    assert is_plugin_url_safe("http://github.com/test/plugin.git") is True
    
    assert is_plugin_url_safe("https://localhost:8080/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False
    assert is_plugin_url_safe("http://[::1]/plugin") is False
    
    assert is_plugin_url_safe("file:///etc/passwd") is False
    assert is_plugin_url_safe("ftp://example.com/plugin") is False
    
    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False
    print("  ✓ SSRF 防护正确")

    print("\n=== 安全模块测试完成 ===")


if __name__ == "__main__":
    main()