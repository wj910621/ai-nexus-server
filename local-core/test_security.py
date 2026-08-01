"""
安全工具模块测试
覆盖：
- normalize_path / is_path_safe / sanitize_path（路径遍历、敏感系统路径、越界访问）
- is_command_safe（危险命令黑名单匹配）
- sanitize_input（长度、控制字符、零宽字符）
- is_plugin_url_safe（SSRF 防护：协议、本地地址、内网 IP、DNS 解析）
- get_safe_work_dir（目录创建与 realpath）
"""

import os
import sys
import tempfile
from pathlib import Path

import security


def _section(title):
    print(f"\n--- {title} ---")


def test_normalize_path():
    _section("normalize_path")
    # 空/非法输入
    assert security.normalize_path("") is None, "空字符串应返回 None"
    assert security.normalize_path(None) is None, "None 应返回 None"
    assert security.normalize_path(123) is None, "非字符串应返回 None"

    # 正常路径
    r = security.normalize_path(".")
    assert r is not None and os.path.isabs(r), "应返回绝对路径"
    print("  ✓ 空值/非法值返回 None；正常路径返回绝对路径")


def test_is_path_safe_rejects_traversal_and_sensitive():
    _section("is_path_safe - 路径遍历与敏感路径")
    cwd = os.getcwd()

    # 允许：cwd 内合法路径
    inside = os.path.join(cwd, "data", "a.txt")
    # 先确保父目录存在
    os.makedirs(os.path.join(cwd, "data"), exist_ok=True)
    assert security.is_path_safe(inside), "cwd 内 data 子目录应安全"

    # 路径穿越
    traversal = os.path.join(cwd, "..", "etc", "passwd")
    assert not security.is_path_safe(traversal), ".. 穿越应被拒绝"

    # 敏感系统路径
    assert not security.is_path_safe("/etc/passwd"), "/etc 应被拒绝"
    assert not security.is_path_safe("/bin/ls"), "/bin 应被拒绝"
    assert not security.is_path_safe("/proc/self"), "/proc 应被拒绝"

    # 空/非法路径
    assert not security.is_path_safe(""), "空路径应不安全"
    assert not security.is_path_safe(None), "None 路径应不安全"

    print("  ✓ 路径穿越、敏感系统路径、非法输入均被拒绝")


def test_is_path_safe_with_custom_bases():
    _section("is_path_safe - 自定义基目录")
    with tempfile.TemporaryDirectory() as td:
        base = os.path.realpath(td)
        inside = os.path.join(base, "sub", "file.txt")
        os.makedirs(os.path.dirname(inside), exist_ok=True)
        with open(inside, "w", encoding="utf-8") as f:
            f.write("x")

        # 在自定义基目录内应允许
        assert security.is_path_safe(inside, allowed_bases=[base]), "自定义基目录内应允许"

        # 越出基目录应拒绝
        outside = os.path.join(base, "..", "outside.txt")
        assert not security.is_path_safe(outside, allowed_bases=[base]), "越出自定义基目录应拒绝"
    print("  ✓ 自定义基目录生效，越界访问被拒绝")


def test_sanitize_path_fallback_and_raise():
    _section("sanitize_path")
    cwd = os.getcwd()

    # 合法路径
    ok = security.sanitize_path(os.path.join(cwd, "README.md"))
    assert ok is not None and os.path.isabs(ok)

    # 非法相对路径 + 默认基目录 => 回退到默认基目录的 realpath
    bad_rel = "../../etc/passwd"
    result = security.sanitize_path(bad_rel, default_base=cwd)
    # 回退值应为 cwd 的 realpath
    assert result == os.path.realpath(cwd), f"越界时应回退到默认基目录, got {result}"

    # 非法路径 + 无默认基目录 => 抛 ValueError
    try:
        security.sanitize_path("/etc/shadow")
        raised = False
    except ValueError:
        raised = True
    assert raised, "非法路径且无 default_base 时应抛 ValueError"

    print("  ✓ sanitize_path 合法时通过、越界时回退、无默认值时抛异常")


def test_is_command_safe():
    _section("is_command_safe")
    assert security.is_command_safe("ls -la"), "普通命令应安全"
    assert security.is_command_safe("  echo hello  "), "含空白的普通命令应安全"

    # 命中危险关键词
    dangerous = [
        "rm -rf /",
        "DD if=/dev/zero of=/dev/sda",  # 大小写不敏感
        "format C:",
        "mkfs.ext4 /dev/sda1",
        ":(){ :|:& };:",  # fork 炸弹
    ]
    for cmd in dangerous:
        assert not security.is_command_safe(cmd), f"危险命令应被拦截: {cmd}"

    # 空/非字符串
    assert not security.is_command_safe(""), "空命令应视为不安全"
    assert not security.is_command_safe(None), "None 应视为不安全"

    print("  ✓ 危险命令被拦截，普通命令通过")


def test_sanitize_input():
    _section("sanitize_input")
    # 截断超长
    long_text = "a" * 20000
    out = security.sanitize_input(long_text, max_length=100)
    assert len(out) == 100, "超长文本应被截断"

    # 去除控制字符与零宽字符
    dirty = "hello\x00\x01\x7f\u200b\u200f\ufeff world"
    cleaned = security.sanitize_input(dirty)
    assert "\x00" not in cleaned
    assert "\u200b" not in cleaned
    assert cleaned.strip() == "hello world" or "hello" in cleaned and "world" in cleaned

    # 保留换行与制表符
    assert "\n" in security.sanitize_input("a\nb")
    assert "\t" in security.sanitize_input("a\tb")

    # 非字符串输入应被转字符串
    assert security.sanitize_input(42) == "42"

    print("  ✓ 长度截断、控制字符/零宽字符去除、保留换行制表符、类型鲁棒")


def test_is_plugin_url_safe():
    _section("is_plugin_url_safe - SSRF 防护")
    # 合法外网 HTTPS
    assert security.is_plugin_url_safe("https://example.com/plugin.json")
    assert security.is_plugin_url_safe("http://example.com/plugin.json")

    # 非法协议
    assert not security.is_plugin_url_safe("file:///etc/passwd")
    assert not security.is_plugin_url_safe("ftp://example.com/x")
    assert not security.is_plugin_url_safe("gopher://example.com/x")

    # 本地/回环/内网 IP
    local_cases = [
        "http://localhost/plugin.json",
        "http://127.0.0.1/plugin.json",
        "http://0.0.0.0/plugin.json",
        "http://[::1]/plugin.json",
        "http://10.0.0.1/plugin.json",
        "http://192.168.1.1/plugin.json",
        "http://169.254.169.254/latest/meta-data/",  # 云元数据
    ]
    for url in local_cases:
        assert not security.is_plugin_url_safe(url), f"内网/本地地址应被拒绝: {url}"

    # 非法/空输入
    assert not security.is_plugin_url_safe("")
    assert not security.is_plugin_url_safe(None)
    assert not security.is_plugin_url_safe("not a url")

    print("  ✓ 协议白名单、本地/内网/元数据地址阻断均生效")


def test_get_safe_work_dir():
    _section("get_safe_work_dir")
    with tempfile.TemporaryDirectory() as td:
        old_cwd = os.getcwd()
        try:
            os.chdir(td)
            data_dir = security.get_safe_work_dir("data")
            assert os.path.isdir(data_dir), "应自动创建子目录"
            assert data_dir == os.path.realpath(os.path.join(td, "data"))
        finally:
            os.chdir(old_cwd)
    print("  ✓ get_safe_work_dir 创建目录并返回 realpath")


def main():
    print("=== 安全工具模块测试 ===\n")
    test_normalize_path()
    test_is_path_safe_rejects_traversal_and_sensitive()
    test_is_path_safe_with_custom_bases()
    test_sanitize_path_fallback_and_raise()
    test_is_command_safe()
    test_sanitize_input()
    test_is_plugin_url_safe()
    test_get_safe_work_dir()
    print("\n✅ 所有安全测试通过")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
