"""
安全工具模块测试
覆盖路径遍历防护、命令黑名单、输入消毒、插件 URL 安全（SSRF 防护）。
"""

import os
import sys
import tempfile

import security


def test_normalize_path():
    """路径规范化"""
    print("\n=== 路径规范化 ===")

    assert security.normalize_path("/etc/passwd") == "/etc/passwd"
    assert security.normalize_path("~/test") == os.path.expanduser("~/test")
    assert security.normalize_path("/foo/../bar") == "/bar"
    assert security.normalize_path("") is None
    assert security.normalize_path(None) is None
    assert security.normalize_path(123) is None
    print("  ✅ 路径规范化正确")


def test_is_path_safe():
    """路径安全检查"""
    print("\n=== 路径安全检查 ===")

    # 敏感路径应被拒绝
    assert security.is_path_safe("/etc/passwd") is False
    assert security.is_path_safe("/bin/bash") is False
    # Windows 敏感路径仅在 Windows 环境下通过绝对路径匹配；Linux 下字符串不匹配
    if os.name == "nt":
        assert security.is_path_safe("C:\\Windows\\System32") is False

    # 允许目录内的路径应通过
    cwd = os.getcwd()
    assert security.is_path_safe(cwd) is True
    assert security.is_path_safe(os.path.join(cwd, "data", "file.txt")) is True

    # 越界路径应被拒绝
    assert security.is_path_safe("/tmp/../../etc/passwd") is False

    # 自定义允许基目录
    with tempfile.TemporaryDirectory() as tmp:
        assert security.is_path_safe(tmp, allowed_bases=[tmp]) is True
        assert security.is_path_safe("/tmp/other", allowed_bases=[tmp]) is False
    print("  ✅ 路径安全检查正确")


def test_sanitize_path():
    """路径消毒与 fallback"""
    print("\n=== 路径消毒 ===")

    cwd = os.getcwd()
    assert security.sanitize_path("safe.txt", default_base=cwd) == os.path.join(cwd, "safe.txt")

    # 越界时应 fallback 到默认基目录
    fallback = security.sanitize_path("/etc/passwd", default_base=cwd)
    assert fallback == cwd or fallback.startswith(cwd)

    # 无 default_base 且越界时应抛出异常
    try:
        security.sanitize_path("/etc/passwd")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        assert "非法路径" in str(e)
    print("  ✅ 路径消毒正确")


def test_is_command_safe():
    """命令黑名单检查"""
    print("\n=== 命令黑名单检查 ===")

    assert security.is_command_safe("rm -rf /") is False
    assert security.is_command_safe("format C:") is False
    assert security.is_command_safe("dd if=/dev/zero of=/dev/sda") is False
    assert security.is_command_safe(":(){ :|:& };:") is False

    assert security.is_command_safe("ls -la") is True
    assert security.is_command_safe("python script.py") is True

    assert security.is_command_safe("") is False
    assert security.is_command_safe(None) is False
    print("  ✅ 命令黑名单正确")


def test_sanitize_input():
    """输入消毒"""
    print("\n=== 输入消毒 ===")

    # 控制字符去除
    dirty = "hello\x00\x01world\u200b\ufeff"
    clean = security.sanitize_input(dirty)
    assert "\x00" not in clean
    assert "\u200b" not in clean
    assert "\ufeff" not in clean
    assert clean == "helloworld"

    # 长度限制
    long_text = "a" * 20000
    truncated = security.sanitize_input(long_text, max_length=100)
    assert len(truncated) == 100

    # 非字符串输入
    assert security.sanitize_input(12345) == "12345"
    print("  ✅ 输入消毒正确")


def test_is_plugin_url_safe():
    """插件 URL 安全（SSRF 防护）"""
    print("\n=== 插件 URL SSRF 防护 ===")

    # 协议检查
    assert security.is_plugin_url_safe("ftp://example.com/plugin.zip") is False
    assert security.is_plugin_url_safe("file:///etc/passwd") is False

    # 本地地址拒绝
    assert security.is_plugin_url_safe("http://localhost:8080/plugin.zip") is False
    assert security.is_plugin_url_safe("http://127.0.0.1/plugin.zip") is False
    assert security.is_plugin_url_safe("http://0.0.0.0/plugin.zip") is False
    assert security.is_plugin_url_safe("http://[::1]/plugin.zip") is False

    # 内网 IP 拒绝
    assert security.is_plugin_url_safe("http://192.168.1.1/plugin.zip") is False
    assert security.is_plugin_url_safe("http://10.0.0.1/plugin.zip") is False
    assert security.is_plugin_url_safe("http://172.16.0.1/plugin.zip") is False

    # 空/无效输入
    assert security.is_plugin_url_safe("") is False
    assert security.is_plugin_url_safe(None) is False
    assert security.is_plugin_url_safe("not-a-url") is False

    # 正常公网地址应通过（注意：若 DNS 解析失败会被拒绝，这里用知名公网域名）
    assert security.is_plugin_url_safe("https://github.com/user/repo.zip") is True
    print("  ✅ 插件 URL 安全检测正确")


def test_get_safe_work_dir():
    """安全工作目录获取"""
    print("\n=== 安全工作目录 ===")

    wd = security.get_safe_work_dir("test_work_dir")
    assert os.path.isdir(wd)
    assert os.path.isabs(wd)
    os.rmdir(wd)
    print("  ✅ 安全工作目录正确")


def main():
    print("=" * 60)
    print("  安全工具模块测试")
    print("=" * 60)

    test_normalize_path()
    test_is_path_safe()
    test_sanitize_path()
    test_is_command_safe()
    test_sanitize_input()
    test_is_plugin_url_safe()
    test_get_safe_work_dir()

    print("\n" + "=" * 60)
    print("  ✅ 全部安全测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
