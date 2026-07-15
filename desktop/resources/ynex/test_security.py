"""
安全工具模块测试
覆盖路径遍历防护、命令执行安全、输入消毒、插件 URL 安全检查等核心功能
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
)


def main():
    print("=== 安全工具模块测试 ===\n")

    # 1. 路径规范化
    print("1. 路径规范化...")
    assert normalize_path("data/test.txt") is not None
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None
    print("  ✓ 路径规范化正确")

    # 2. 路径安全检查
    print("\n2. 路径安全检查...")
    assert is_path_safe("data/test.txt") is True
    assert is_path_safe("plugins/test.py") is True

    assert is_path_safe("/etc/passwd") is False
    assert is_path_safe("/bin/bash") is False
    assert is_path_safe("/sbin/init") is False
    print("  ✓ 敏感路径被拒绝")

    assert is_path_safe("../etc/passwd") is False
    assert is_path_safe("data/../../etc/passwd") is False
    assert is_path_safe("/tmp/../../etc/passwd") is False
    print("  ✓ 路径穿越被阻止")

    assert is_path_safe("~/documents/test.txt") is True
    print("  ✓ 用户目录访问允许")

    # 3. 路径消毒
    print("\n3. 路径消毒...")
    safe_path = sanitize_path("data/test.txt")
    assert "data" in safe_path
    print("  ✓ 正常路径返回原始路径")

    try:
        sanitize_path("/etc/passwd")
        assert False, "应抛出异常"
    except ValueError:
        print("  ✓ 非法路径抛出异常")

    fallback_path = sanitize_path("/etc/passwd", default_base="data")
    assert "data" in fallback_path
    assert "/etc" not in fallback_path
    print("  ✓ 越界路径回退到默认目录")

    # 4. 命令安全检查
    print("\n4. 命令安全检查...")
    assert is_command_safe("ls -la") is True
    assert is_command_safe("echo hello") is True
    assert is_command_safe("git status") is True

    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("rm -rf /*") is False
    assert is_command_safe("format C:") is False
    assert is_command_safe("fdisk /dev/sda") is False
    assert is_command_safe(":(){ :|:& };:\n") is False
    assert is_command_safe("> /dev/sda") is False
    print("  ✓ 危险命令被拦截")

    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    assert is_command_safe(123) is False
    print("  ✓ 无效输入处理正确")

    # 5. 输入消毒
    print("\n5. 输入消毒...")
    clean = sanitize_input("  hello world  ")
    assert clean == "hello world"

    long_text = "a" * 20000
    clean = sanitize_input(long_text)
    assert len(clean) == 10000
    print("  ✓ 长度限制生效")

    # 测试零宽字符
    with_zero_width = "hello\u200bworld"
    clean = sanitize_input(with_zero_width)
    assert "\u200b" not in clean
    assert clean == "helloworld"
    print("  ✓ 零宽字符被移除")

    # 测试控制字符
    with_control = "hello\x00world\x07test"
    clean = sanitize_input(with_control)
    assert "\x00" not in clean
    assert "\x07" not in clean
    assert clean == "helloworldtest"
    print("  ✓ 控制字符被移除")

    # 6. 插件 URL 安全检查
    print("\n6. 插件 URL 安全检查...")
    assert is_plugin_url_safe("https://github.com/user/plugin.git") is True
    assert is_plugin_url_safe("https://www.npmjs.com/package/some-plugin") is True
    print("  ✓ 合法外部 URL 通过")

    assert is_plugin_url_safe("http://localhost:3000/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False
    assert is_plugin_url_safe("http://[::1]/plugin") is False
    print("  ✓ 本地地址被拒绝")

    assert is_plugin_url_safe("http://192.168.1.100/plugin") is False
    assert is_plugin_url_safe("http://10.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://172.16.0.1/plugin") is False
    print("  ✓ 内网地址被拒绝")

    assert is_plugin_url_safe("ftp://example.com/plugin") is False
    assert is_plugin_url_safe("file:///etc/passwd") is False
    print("  ✓ 危险协议被拒绝")

    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False
    print("  ✓ 无效输入处理正确")

    # 7. 安全工作目录
    print("\n7. 安全工作目录...")
    work_dir = get_safe_work_dir("test_work")
    assert os.path.exists(work_dir)
    assert os.path.isabs(work_dir)
    print(f"  ✓ 工作目录创建成功: {work_dir}")

    os.rmdir(work_dir)

    print("\n=== 安全工具模块测试完成 ===")


if __name__ == "__main__":
    main()