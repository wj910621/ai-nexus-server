"""
安全模块测试
覆盖：路径遍历防护、命令安全检查、输入消毒、插件URL SSRF防护
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
)


# ============================================================================
# normalize_path 测试
# ============================================================================

def test_normalize_path_basic():
    """基本路径规范化"""
    print("\n=== normalize_path 基本测试 ===")

    # 绝对路径
    result = normalize_path("/tmp/test")
    assert result is not None, "绝对路径应返回非 None"
    assert os.path.isabs(result), "结果应为绝对路径"
    print(f"  绝对路径: /tmp/test -> {result}")

    # 相对路径解析为绝对路径
    result = normalize_path("data/files")
    assert result is not None
    assert os.path.isabs(result), "相对路径应解析为绝对路径"
    print(f"  相对路径: data/files -> {result}")


def test_normalize_path_invalid():
    """非法输入"""
    print("\n=== normalize_path 非法输入 ===")

    assert normalize_path("") is None, "空字符串应返回 None"
    assert normalize_path(None) is None, "None 应返回 None"
    assert normalize_path(123) is None, "非字符串应返回 None"
    print("  空字符串、None、非字符串均返回 None")


def test_normalize_path_traversal():
    """路径穿越解析"""
    print("\n=== normalize_path 路径穿越 ===")

    result = normalize_path("/tmp/../etc/passwd")
    assert result is not None
    assert ".." not in result, "规范化后不应包含 .."
    # /tmp/../etc/passwd 应解析为 /etc/passwd
    assert "etc" in result, "路径穿越后应解析到真实路径"
    print(f"  /tmp/../etc/passwd -> {result}")


def test_normalize_path_user_expand():
    """用户目录展开"""
    print("\n=== normalize_path 用户目录展开 ===")

    result = normalize_path("~/documents")
    assert result is not None
    assert "~" not in result, "应展开 ~ 为用户目录"
    assert result.startswith(os.path.expanduser("~"))
    print(f"  ~/documents -> {result}")


# ============================================================================
# is_path_safe 测试
# ============================================================================

def test_is_path_safe_sensitive_paths():
    """敏感系统路径应被拒绝"""
    print("\n=== is_path_safe 敏感路径拒绝 ===")

    sensitive_paths = ["/etc/passwd", "/etc/shadow", "/usr/bin/python3"]
    for path in sensitive_paths:
        assert not is_path_safe(path), f"敏感路径 {path} 应被拒绝"
        print(f"  拒绝: {path}")


def test_is_path_safe_allowed_dirs():
    """允许的基目录内路径应被接受"""
    print("\n=== is_path_safe 允许目录 ===")

    # 用户主目录下的路径
    home = os.path.expanduser("~")
    result = is_path_safe(os.path.join(home, "documents"))
    assert result, f"用户目录下路径应被允许: {home}/documents"
    print(f"  允许: {home}/documents")

    # 使用自定义 allowed_bases
    with tempfile.TemporaryDirectory() as tmpdir:
        assert is_path_safe(os.path.join(tmpdir, "subdir"), allowed_bases=[tmpdir])
        print(f"  允许（自定义基目录）: {tmpdir}/subdir")


def test_is_path_safe_traversal_attack():
    """路径穿越攻击应被阻止"""
    print("\n=== is_path_safe 路径穿越攻击 ===")

    # 从允许目录穿越到敏感目录
    home = os.path.expanduser("~")
    attack_path = os.path.join(home, "../../etc/passwd")
    # 规范化后指向 /etc/passwd，应在敏感路径列表内
    assert not is_path_safe(attack_path), f"穿越攻击路径应被拒绝: {attack_path}"
    print(f"  拒绝穿越: {attack_path}")


def test_is_path_safe_custom_bases():
    """自定义基目录边界检查"""
    print("\n=== is_path_safe 自定义基目录边界 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "allowed")
        os.makedirs(subdir, exist_ok=True)

        # 基目录内的路径
        assert is_path_safe(os.path.join(subdir, "file.txt"), allowed_bases=[tmpdir])
        print(f"  允许: {subdir}/file.txt")

        # 基目录外的路径
        assert not is_path_safe("/etc/passwd", allowed_bases=[tmpdir])
        print(f"  拒绝基目录外路径: /etc/passwd")


def test_is_path_safe_invalid_input():
    """无效输入"""
    print("\n=== is_path_safe 无效输入 ===")

    assert not is_path_safe(""), "空字符串应不安全"
    assert not is_path_safe(None), "None 应不安全"
    print("  空字符串和 None 均判定为不安全")


# ============================================================================
# sanitize_path 测试
# ============================================================================

def test_sanitize_path_safe():
    """安全路径应原样返回"""
    print("\n=== sanitize_path 安全路径 ===")

    home = os.path.expanduser("~")
    result = sanitize_path(os.path.join(home, "test.txt"), default_base=home)
    assert result is not None
    print(f"  安全路径: {result}")


def test_sanitize_path_unsafe_fallback():
    """越界路径应回退到默认基目录"""
    print("\n=== sanitize_path 越界回退 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 越界路径应回退到 default_base
        result = sanitize_path("/etc/passwd", default_base=tmpdir)
        assert result is not None
        assert tmpdir in result, "越界路径应回退到 default_base"
        print(f"  越界回退: /etc/passwd -> {result}")


def test_sanitize_path_no_default_raises():
    """越界且无 default_base 应抛异常"""
    print("\n=== sanitize_path 越界无默认目录 ===")

    try:
        sanitize_path("/etc/passwd")
        assert False, "应抛出 ValueError"
    except ValueError:
        print("  正确抛出 ValueError")


def test_sanitize_path_relative():
    """相对路径应基于 default_base 解析"""
    print("\n=== sanitize_path 相对路径 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = sanitize_path("subdir/file.txt", default_base=tmpdir)
        assert result is not None
        # 规范化后路径应包含 tmpdir
        print(f"  相对路径解析: subdir/file.txt -> {result}")


# ============================================================================
# is_command_safe 测试
# ============================================================================

def test_command_safe_basic():
    """安全命令"""
    print("\n=== is_command_safe 安全命令 ===")

    assert is_command_safe("ls -la")
    assert is_command_safe("python --version")
    assert is_command_safe("echo hello")
    print("  ls, python, echo 均判定为安全")


def test_command_safe_dangerous():
    """危险命令应被拦截"""
    print("\n=== is_command_safe 危险命令 ===")

    dangerous = [
        "format C:",
        "fdisk /dev/sda",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "rm -rf /",
        "rm -rf /*",
        ":(){ :|:& };:",
        "> /dev/sda",
    ]
    for cmd in dangerous:
        assert not is_command_safe(cmd), f"危险命令应被拦截: {cmd}"
    print(f"  全部 {len(dangerous)} 个危险命令均被拦截")


def test_command_safe_empty():
    """空或无效输入"""
    print("\n=== is_command_safe 无效输入 ===")

    assert not is_command_safe(""), "空命令应不安全"
    assert not is_command_safe(None), "None 应不安全"
    assert not is_command_safe(123), "非字符串应不安全"
    print("  空字符串、None、非字符串均判定为不安全")


def test_command_safe_case_insensitive():
    """大小写不敏感"""
    print("\n=== is_command_safe 大小写不敏感 ===")

    assert not is_command_safe("FORMAT C:"), "FORMAT 大写应被拦截"
    assert not is_command_safe("Rm -Rf /"), "混合大小写应被拦截"
    print("  大小写混合的危险命令也被拦截")


# ============================================================================
# sanitize_input 测试
# ============================================================================

def test_sanitize_input_basic():
    """基本输入消毒"""
    print("\n=== sanitize_input 基本测试 ===")

    assert sanitize_input("hello world") == "hello world"
    print("  正常文本不变")


def test_sanitize_input_length_limit():
    """长度限制"""
    print("\n=== sanitize_input 长度限制 ===")

    long_text = "a" * 20000
    result = sanitize_input(long_text, max_length=1000)
    assert len(result) <= 1000, "应截断到 max_length"
    print(f"  输入 20000 字符 -> 截断到 {len(result)} 字符")


def test_sanitize_input_control_chars():
    """控制字符移除"""
    print("\n=== sanitize_input 控制字符 ===")

    text_with_control = "hello\x00world\x07test\x1fend"
    result = sanitize_input(text_with_control)
    assert "\x00" not in result, "NULL 字节应被移除"
    assert "\x07" not in result, "BEL 字符应被移除"
    assert "\x1f" not in result, "US 字符应被移除"
    assert "hello" in result and "world" in result
    print(f"  移除控制字符: {repr(text_with_control)} -> {repr(result)}")


def test_sanitize_input_zero_width():
    """零宽字符移除"""
    print("\n=== sanitize_input 零宽字符 ===")

    text_with_zw = "hello\u200bworld\ufefftest"
    result = sanitize_input(text_with_zw)
    assert "\u200b" not in result, "零宽空格应被移除"
    assert "\ufeff" not in result, "BOM 应被移除"
    print(f"  移除零宽字符: {repr(text_with_zw)} -> {repr(result)}")


def test_sanitize_input_preserve_newline():
    """保留换行和制表符"""
    print("\n=== sanitize_input 保留换行制表符 ===")

    text = "line1\nline2\ttab"
    result = sanitize_input(text)
    assert "\n" in result, "换行符应保留"
    assert "\t" in result, "制表符应保留"
    print("  换行和制表符正确保留")


def test_sanitize_input_non_string():
    """非字符串输入"""
    print("\n=== sanitize_input 非字符串 ===")

    result = sanitize_input(12345)
    assert isinstance(result, str)
    assert "12345" in result
    print(f"  数字输入转换为字符串: {result}")


# ============================================================================
# is_plugin_url_safe 测试
# ============================================================================

def test_plugin_url_safe_https():
    """HTTPS URL 应被允许（公网域名）"""
    print("\n=== is_plugin_url_safe HTTPS ===")

    # 注意：此测试需要 DNS 解析，可能因网络环境失败
    # 使用公网知名域名
    result = is_plugin_url_safe("https://github.com/user/plugin/archive/main.zip")
    print(f"  https://github.com/... -> {result}")
    # 不做 assert，因为网络可能不可用


def test_plugin_url_safe_blocked_protocols():
    """非 HTTP/HTTPS 协议应被拒绝"""
    print("\n=== is_plugin_url_safe 非法协议 ===")

    assert not is_plugin_url_safe("ftp://example.com/plugin.zip"), "FTP 应被拒绝"
    assert not is_plugin_url_safe("file:///etc/passwd"), "file:// 应被拒绝"
    assert not is_plugin_url_safe("javascript:alert(1)"), "javascript: 应被拒绝"
    print("  ftp, file, javascript 协议均被拒绝")


def test_plugin_url_safe_localhost():
    """本地地址应被拒绝（防 SSRF）"""
    print("\n=== is_plugin_url_safe 本地地址 ===")

    local_urls = [
        "http://localhost/plugin.zip",
        "http://127.0.0.1/plugin.zip",
        "http://0.0.0.0/plugin.zip",
        "http://[::1]/plugin.zip",
    ]
    for url in local_urls:
        assert not is_plugin_url_safe(url), f"本地地址应被拒绝: {url}"
    print(f"  全部 {len(local_urls)} 个本地地址均被拒绝")


def test_plugin_url_safe_invalid():
    """无效输入"""
    print("\n=== is_plugin_url_safe 无效输入 ===")

    assert not is_plugin_url_safe(""), "空字符串应不安全"
    assert not is_plugin_url_safe(None), "None 应不安全"
    assert not is_plugin_url_safe(123), "非字符串应不安全"
    assert not is_plugin_url_safe("http://"), "无 hostname 应不安全"
    print("  空字符串、None、非字符串、无 hostname 均判定为不安全")


# ============================================================================
# get_safe_work_dir 测试
# ============================================================================

def test_get_safe_work_dir():
    """安全工作目录创建"""
    print("\n=== get_safe_work_dir ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            result = get_safe_work_dir("test_data")
            assert os.path.isdir(result), "目录应已创建"
            assert "test_data" in result
            print(f"  工作目录: {result}")

            # 重复调用不应报错
            result2 = get_safe_work_dir("test_data")
            assert result == result2, "重复调用应返回相同路径"
            print("  重复调用正常")
        finally:
            os.chdir(old_cwd)


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 60)
    print("  安全模块测试")
    print("=" * 60)

    # normalize_path
    test_normalize_path_basic()
    test_normalize_path_invalid()
    test_normalize_path_traversal()
    test_normalize_path_user_expand()

    # is_path_safe
    test_is_path_safe_sensitive_paths()
    test_is_path_safe_allowed_dirs()
    test_is_path_safe_traversal_attack()
    test_is_path_safe_custom_bases()
    test_is_path_safe_invalid_input()

    # sanitize_path
    test_sanitize_path_safe()
    test_sanitize_path_unsafe_fallback()
    test_sanitize_path_no_default_raises()
    test_sanitize_path_relative()

    # is_command_safe
    test_command_safe_basic()
    test_command_safe_dangerous()
    test_command_safe_empty()
    test_command_safe_case_insensitive()

    # sanitize_input
    test_sanitize_input_basic()
    test_sanitize_input_length_limit()
    test_sanitize_input_control_chars()
    test_sanitize_input_zero_width()
    test_sanitize_input_preserve_newline()
    test_sanitize_input_non_string()

    # is_plugin_url_safe
    test_plugin_url_safe_https()
    test_plugin_url_safe_blocked_protocols()
    test_plugin_url_safe_localhost()
    test_plugin_url_safe_invalid()

    # get_safe_work_dir
    test_get_safe_work_dir()

    print("\n" + "=" * 60)
    print("  安全模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
