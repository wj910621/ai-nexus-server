"""
安全模块测试
- 路径遍历防护
- 命令执行黑名单
- 输入消毒
- SSRF 防护（插件 URL）
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
)


# ---------------------------------------------------------------------------
# 路径规范化
# ---------------------------------------------------------------------------

def test_normalize_path():
    """路径规范化：展开、绝对化、符号链接解析"""
    # 绝对路径
    assert normalize_path("/tmp/test") == os.path.realpath("/tmp/test")

    # 用户目录展开
    home = os.path.expanduser("~")
    assert normalize_path("~/test") == os.path.realpath(os.path.join(home, "test"))

    # 相对路径转绝对
    assert normalize_path("data/file.txt") == os.path.realpath("data/file.txt")

    # 非法输入
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None


# ---------------------------------------------------------------------------
# 路径安全检查
# ---------------------------------------------------------------------------

def test_is_path_safe():
    """路径安全：敏感路径拒绝 + 基目录边界"""
    cwd = os.getcwd()

    # 当前工作目录及子目录应安全
    assert is_path_safe(cwd) is True
    assert is_path_safe(os.path.join(cwd, "data", "test.txt")) is True

    # 敏感系统路径应被拒绝
    assert is_path_safe("/etc/passwd") is False
    assert is_path_safe("/etc/shadow") is False
    assert is_path_safe("/proc/1/status") is False
    assert is_path_safe("/bin/sh") is False
    assert is_path_safe("/dev/null") is False

    # 自定义 allowed_bases
    tmp = tempfile.mkdtemp()
    assert is_path_safe(os.path.join(tmp, "file.txt"), allowed_bases=[tmp]) is True
    # 路径不在自定义基目录内
    assert is_path_safe("/etc/passwd", allowed_bases=[tmp]) is False


def test_is_path_safe_traversal():
    """路径遍历（.. 穿越）防护"""
    cwd = os.getcwd()
    tmp = tempfile.mkdtemp()

    # 在允许目录内使用 .. 最终仍解析到允许目录 → 安全
    safe_path = os.path.join(tmp, "..", os.path.basename(tmp))
    assert is_path_safe(safe_path, allowed_bases=[tmp]) is True

    # 使用 .. 穿出到允许目录外 → 不安全
    outside = os.path.join(tmp, "..", "outside_file")
    assert is_path_safe(outside, allowed_bases=[tmp]) is False


def test_sanitize_path():
    """路径限制：越界时回退或抛异常"""
    cwd = os.getcwd()

    # 安全路径 → 规范化后返回
    result = sanitize_path(os.path.join(cwd, "test.txt"))
    assert result == os.path.realpath(os.path.join(cwd, "test.txt"))

    # 越界 + 有 default_base → 回退到默认基目录
    fallback = sanitize_path("/etc/passwd", default_base=cwd)
    assert fallback == os.path.realpath(cwd)

    # 越界 + 无 default_base → 抛 ValueError
    try:
        sanitize_path("/etc/passwd")
        assert False, "应抛出 ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# 命令安全
# ---------------------------------------------------------------------------

def test_is_command_safe():
    """危险命令黑名单拦截"""
    # 安全命令
    assert is_command_safe("ls -la") is True
    assert is_command_safe("python script.py") is True
    assert is_command_safe("echo hello") is True

    # 危险命令（黑名单中的每一项都应被拦截）
    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("rm -rf /*") is False
    assert is_command_safe("format C:") is False
    assert is_command_safe("mkfs.ext4 /dev/sda1") is False
    assert is_command_safe("dd if=/dev/zero of=/dev/sda") is False
    assert is_command_safe(":(){ :|:& };:") is False

    # 空值/非字符串
    assert is_command_safe("") is False
    assert is_command_safe(None) is False


# ---------------------------------------------------------------------------
# 输入消毒
# ---------------------------------------------------------------------------

def test_sanitize_input():
    """控制字符移除、长度限制、空白裁剪"""
    # 控制字符移除（保留换行 \n 和制表符 \t）
    assert sanitize_input("hello\x00world") == "helloworld"
    assert sanitize_input("test\x07\x08ring") == "testring"
    assert sanitize_input("line1\nline2\ttab") == "line1\nline2\ttab"

    # 零宽字符移除
    assert sanitize_input("abc\u200bdef") == "abcdef"
    assert sanitize_input("\ufeffheader") == "header"

    # 长度限制
    long_text = "a" * 20000
    result = sanitize_input(long_text, max_length=100)
    assert len(result) == 100

    # 非字符串输入自动转换
    assert sanitize_input(12345) == "12345"

    # 首尾空白裁剪
    assert sanitize_input("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# SSRF 防护（插件 URL）
# ---------------------------------------------------------------------------

def test_is_plugin_url_safe_protocols():
    """不安全协议拦截"""
    assert is_plugin_url_safe("file:///etc/passwd") is False
    assert is_plugin_url_safe("ftp://example.com/file") is False
    assert is_plugin_url_safe("javascript:alert(1)") is False


def test_is_plugin_url_safe_local():
    """本地/回环地址拦截"""
    assert is_plugin_url_safe("http://localhost/plugin") is False
    assert is_plugin_url_safe("http://127.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://0.0.0.0/plugin") is False
    assert is_plugin_url_safe("http://[::1]/plugin") is False


def test_is_plugin_url_safe_private_ip():
    """内网/保留 IP 拦截"""
    assert is_plugin_url_safe("http://192.168.1.1/plugin") is False
    assert is_plugin_url_safe("http://10.0.0.1/plugin") is False
    assert is_plugin_url_safe("http://172.16.0.1/plugin") is False


def test_is_plugin_url_safe_empty():
    """空值/无效 URL"""
    assert is_plugin_url_safe("") is False
    assert is_plugin_url_safe(None) is False
    assert is_plugin_url_safe("http://") is False


# ---------------------------------------------------------------------------
# 运行入口
# ---------------------------------------------------------------------------

def main():
    tests = [
        ("路径规范化", test_normalize_path),
        ("路径安全检查", test_is_path_safe),
        ("路径遍历防护", test_is_path_safe_traversal),
        ("路径限制", test_sanitize_path),
        ("命令安全", test_is_command_safe),
        ("输入消毒", test_sanitize_input),
        ("SSRF-协议拦截", test_is_plugin_url_safe_protocols),
        ("SSRF-本地地址", test_is_plugin_url_safe_local),
        ("SSRF-内网IP", test_is_plugin_url_safe_private_ip),
        ("SSRF-空值", test_is_plugin_url_safe_empty),
    ]

    print("=== 安全模块测试 ===\n")
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
        except Exception as e:
            print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

    print(f"\n{'✅' if passed == len(tests) else '⚠'} 安全模块测试: {passed}/{len(tests)} 通过")
    return passed == len(tests)


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
