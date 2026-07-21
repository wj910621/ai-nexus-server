"""
安全工具模块测试
覆盖 security.py 中的关键防御路径：
  - 路径规范化与越界拦截
  - 危险系统命令黑名单
  - 输入消毒（控制字符、零宽字符、长度截断）
  - 插件 URL 防 SSRF（本地 / 内网 IP 拒绝）
  - get_safe_work_dir 自动建目录
"""

import os
import sys
import shutil
import tempfile
import traceback


# ---------------------------------------------------------------------------
# 路径相关
# ---------------------------------------------------------------------------

def test_normalize_path_basic():
    from security import normalize_path
    cwd = os.getcwd()
    # 相对路径被规范化为绝对路径
    assert normalize_path(".") == os.path.realpath(cwd)
    # 已绝对路径保持
    abs_in = os.path.abspath("foo")
    assert normalize_path(abs_in) == os.path.realpath(abs_in)
    # 非法类型 / 空字符串返回 None
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None
    print("  ✓ normalize_path 基本行为")


def test_is_path_safe_blocks_denied_system_paths():
    from security import is_path_safe
    # 关键安全断言：禁止访问 /etc 等系统敏感目录
    assert is_path_safe("/etc/passwd") is False
    assert is_path_safe("/usr/bin/something") is False
    assert is_path_safe("/bin") is False
    # 大小写不敏感也应拦截
    assert is_path_safe("/ETC/hosts") is False
    print("  ✓ 敏感系统路径被拒绝")


def test_is_path_safe_allows_normal_paths_and_blocks_traversal():
    from security import is_path_safe
    # 当前工作目录及其子路径应允许
    assert is_path_safe("data") is True
    # 路径穿越：使用 .. 试图逃出允许基目录
    assert is_path_safe("../../../etc/passwd") is False
    # 显式指定 allowed_bases 时，仅在该基目录下允许
    tmp = tempfile.mkdtemp(prefix="sec_allow_")
    try:
        allowed = [tmp]
        inside = os.path.join(tmp, "inside.txt")
        assert is_path_safe(inside, allowed) is True
        outside = os.path.join(tmp, "..", "etc", "shadow")
        assert is_path_safe(outside, allowed) is False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ 路径白名单与穿越防护")


def test_sanitize_path_fallback_and_raise():
    from security import sanitize_path
    # 越界路径在 default_base 给定时回退到 default_base
    fallback = os.path.realpath(tempfile.gettempdir())
    got = sanitize_path("/etc/passwd", default_base=fallback)
    assert got == fallback, f"越界时未回退到 default_base, got={got}"
    # 未给 default_base 时直接抛 ValueError
    try:
        sanitize_path("/etc/passwd")
    except ValueError:
        pass
    else:
        raise AssertionError("越界且无 default_base 应抛 ValueError")
    print("  ✓ sanitize_path 回退与异常分支")


# ---------------------------------------------------------------------------
# 命令白名单 / 黑名单
# ---------------------------------------------------------------------------

def test_is_command_safe_blocks_dangerous():
    from security import is_command_safe
    dangerous = [
        "rm -rf /", "rm -rf /*", "mkfs /dev/sda", "fdisk /dev/sdb",
        ":(){ :|:& };:", "> /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        "FORMAT C:",
    ]
    for cmd in dangerous:
        assert is_command_safe(cmd) is False, f"应被拦截的危险命令: {cmd}"
    print("  ✓ 危险命令被拦截")


def test_is_command_safe_allows_normal_and_handles_bad_input():
    from security import is_command_safe
    # 正常命令通过
    assert is_command_safe("ls -la") is True
    assert is_command_safe("echo hello") is True
    # 大小写混合黑名单也应命中（实现使用 lower() 比较）
    assert is_command_safe("RM -RF /") is False
    # 非字符串 / 空串应返回 False
    assert is_command_safe("") is False
    assert is_command_safe(None) is False
    print("  ✓ 正常命令放行 / 非法输入安全降级")


# ---------------------------------------------------------------------------
# 输入消毒
# ---------------------------------------------------------------------------

def test_sanitize_input_strips_control_and_zw_chars():
    from security import sanitize_input
    raw = "hello\x00\x07world\x1b[31m"
    cleaned = sanitize_input(raw)
    # 控制字符被剥离
    assert "\x00" not in cleaned
    assert "\x07" not in cleaned
    assert "\x1b" not in cleaned
    assert "hello" in cleaned and "world" in cleaned

    # 零宽字符 / BOM 被剥离
    zw = "A\u200bB\ufeffC"
    assert "\u200b" not in sanitize_input(zw)
    assert "\ufeff" not in sanitize_input(zw)
    # 换行和制表符保留
    assert "\n" in sanitize_input("a\nb")
    assert "\t" in sanitize_input("a\tb")
    print("  ✓ sanitize_input 控制字符与零宽字符剥离")


def test_sanitize_input_length_cap_and_non_str():
    from security import sanitize_input
    long_text = "x" * 200
    out = sanitize_input(long_text, max_length=10)
    assert len(out) == 10

    # 非字符串应被强制转字符串并返回
    out_int = sanitize_input(12345)
    assert isinstance(out_int, str) and "12345" in out_int
    print("  ✓ sanitize_input 长度截断与类型强转")


# ---------------------------------------------------------------------------
# 插件 URL SSRF 防护
# ---------------------------------------------------------------------------

def test_is_plugin_url_safe_rejects_local_and_private_ips():
    from security import is_plugin_url_safe
    # 不支持的协议
    assert is_plugin_url_safe("file:///etc/passwd") is False
    assert is_plugin_url_safe("ftp://example.com/foo") is False
    # 明确禁止的本地主机名
    assert is_plugin_url_safe("http://localhost/abc") is False
    assert is_plugin_url_safe("http://127.0.0.1/abc") is False
    assert is_plugin_url_safe("http://0.0.0.0/abc") is False
    # 内网私有 IP（字面量 IP 路径）
    assert is_plugin_url_safe("http://10.0.0.1/abc") is False
    assert is_plugin_url_safe("http://192.168.1.1/abc") is False
    assert is_plugin_url_safe("http://169.254.169.254/latest/meta-data/") is False  # AWS link-local
    # 没有主机名
    assert is_plugin_url_safe("http:///path") is False
    # 非字符串
    assert is_plugin_url_safe(None) is False
    assert is_plugin_url_safe("") is False
    print("  ✓ 插件 URL 本地/内网/危险协议被拦截")


# ---------------------------------------------------------------------------
# get_safe_work_dir
# ---------------------------------------------------------------------------

def test_get_safe_work_dir_creates_dir():
    from security import get_safe_work_dir
    # 不存在的子目录应自动创建
    sub = "_ynex_sec_test_tmp_subdir_xyz"
    full = get_safe_work_dir(sub)
    try:
        assert os.path.isdir(full)
        assert full.endswith(sub)
        # 再次调用应保持幂等
        again = get_safe_work_dir(sub)
        assert again == full
    finally:
        shutil.rmtree(full, ignore_errors=True)
    print("  ✓ get_safe_work_dir 自动建目录并幂等")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

CASES = [
    test_normalize_path_basic,
    test_is_path_safe_blocks_denied_system_paths,
    test_is_path_safe_allows_normal_paths_and_blocks_traversal,
    test_sanitize_path_fallback_and_raise,
    test_is_command_safe_blocks_dangerous,
    test_is_command_safe_allows_normal_and_handles_bad_input,
    test_sanitize_input_strips_control_and_zw_chars,
    test_sanitize_input_length_cap_and_non_str,
    test_is_plugin_url_safe_rejects_local_and_private_ips,
    test_get_safe_work_dir_creates_dir,
]


def main():
    print("=== security 模块测试 ===")
    failed = []
    for case in CASES:
        try:
            case()
        except Exception:
            failed.append((case.__name__, traceback.format_exc()))
            print(f"  ✗ {case.__name__}")
        else:
            print(f"  ✓ {case.__name__}")
    if failed:
        print("\n失败用例:")
        for name, tb in failed:
            print(f"--- {name} ---\n{tb}")
        sys.exit(1)
    print(f"\n全部 {len(CASES)} 个安全测试通过")


if __name__ == "__main__":
    main()
