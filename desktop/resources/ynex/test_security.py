"""
安全模块测试
覆盖：路径遍历防护、敏感路径拦截、命令注入检测、输入消毒、插件 URL SSRF 防护
"""

import os
import sys
import pytest

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(__file__))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    DENIED_PATHS,
    ALLOWED_BASE_DIRS,
)


# ===========================================================================
# normalize_path
# ===========================================================================
class TestNormalizePath:
    def test_valid_absolute_path(self):
        result = normalize_path("/tmp/test")
        assert result is not None
        assert os.path.isabs(result)

    def test_valid_relative_path(self):
        result = normalize_path("data/test")
        assert result is not None

    def test_empty_string(self):
        assert normalize_path("") is None

    def test_none_input(self):
        assert normalize_path(None) is None

    def test_non_string_input(self):
        assert normalize_path(123) is None

    def test_home_expansion(self):
        result = normalize_path("~/test_dir")
        assert result is not None
        assert "~" not in result  # 应被展开

    def test_dotdot_traversal(self):
        """路径中的 .. 应被解析（不再包含 ..）"""
        result = normalize_path("/tmp/../etc/passwd")
        assert result is not None
        assert ".." not in result


# ===========================================================================
# is_path_safe
# ===========================================================================
class TestIsPathSafe:
    def test_denied_path_etc(self):
        assert is_path_safe("/etc/passwd") is False

    def test_denied_path_proc(self):
        assert is_path_safe("/proc/1/status") is False

    def test_denied_path_sys(self):
        assert is_path_safe("/sys/kernel") is False

    def test_denied_path_dev(self):
        assert is_path_safe("/dev/null") is False

    def test_denied_path_bin(self):
        assert is_path_safe("/bin/bash") is False

    def test_denied_path_sbin(self):
        assert is_path_safe("/sbin/iptables") is False

    def test_denied_path_windows_system(self):
        """Windows 系统路径在 Linux 上可能无法检测（路径不解析为 /etc 等）"""
        # 在 Linux 上，C:\Windows 会被解析为相对路径，不会命中 DENIED_PATHS
        # 跳过该测试，仅在 Windows 环境下有意义
        if os.name != "nt":
            pytest.skip("Windows 路径检测仅在 Windows 上有效")
        assert is_path_safe("C:\\Windows\\System32") is False

    def test_cwd_subdir_allowed(self):
        """当前工作目录下的子目录应被允许"""
        safe_path = os.path.join(os.getcwd(), "data", "test.txt")
        assert is_path_safe(safe_path) is True

    def test_home_dir_allowed(self):
        """用户主目录应被允许"""
        home = os.path.expanduser("~")
        assert is_path_safe(os.path.join(home, "test.txt")) is True

    def test_random_outside_path_denied(self):
        """不在允许基目录内的路径应被拒绝"""
        assert is_path_safe("/var/log/test") is False

    def test_dotdot_escape_denied(self):
        """使用 .. 逃逸出基目录的路径应被拒绝"""
        # 从 data 目录逃逸到 /etc
        escaped = os.path.join(os.getcwd(), "data", "..", "..", "etc", "passwd")
        assert is_path_safe(escaped) is False

    def test_none_path(self):
        assert is_path_safe(None) is False

    def test_empty_path(self):
        assert is_path_safe("") is False

    def test_custom_allowed_bases(self):
        """自定义允许基目录应生效"""
        custom_base = "/tmp"
        # /tmp 下的路径在自定义基下应被允许
        result = is_path_safe("/tmp/myfile.txt", allowed_bases=["/tmp"])
        # 注意：/tmp 可能不在 DENIED_PATHS 中，所以只要在 allowed_bases 内就应返回 True
        assert result is True

    def test_case_insensitive_denied(self):
        """敏感路径匹配应不区分大小写"""
        assert is_path_safe("/ETC/passwd") is False
        assert is_path_safe("/Bin/ls") is False


# ===========================================================================
# sanitize_path
# ===========================================================================
class TestSanitizePath:
    def test_safe_path_unchanged(self):
        """安全路径应原样返回（规范化后）"""
        safe = os.path.join(os.getcwd(), "data", "test.txt")
        result = sanitize_path(safe, default_base=os.path.join(os.getcwd(), "data"))
        assert result is not None

    def test_unsafe_path_fallback(self):
        """不安全路径应回退到 default_base"""
        result = sanitize_path("/etc/passwd", default_base=os.path.join(os.getcwd(), "data"))
        # 应该回退到 default_base
        assert "/etc" not in result

    def test_no_default_base_raises(self):
        """无 default_base 且不安全路径应抛出 ValueError"""
        with pytest.raises(ValueError, match="非法路径"):
            sanitize_path("/etc/passwd")

    def test_relative_path_with_base(self):
        """相对路径应结合 default_base"""
        result = sanitize_path("test.txt", default_base=os.path.join(os.getcwd(), "data"))
        assert result is not None


# ===========================================================================
# is_command_safe
# ===========================================================================
class TestIsCommandSafe:
    def test_safe_command_ls(self):
        assert is_command_safe("ls -la") is True

    def test_safe_command_echo(self):
        assert is_command_safe("echo hello") is True

    def test_dangerous_rm_rf(self):
        assert is_command_safe("rm -rf /") is False

    def test_dangerous_rm_rf_wildcard(self):
        assert is_command_safe("rm -rf /*") is False

    def test_dangerous_format(self):
        assert is_command_safe("format C:") is False

    def test_dangerous_fdisk(self):
        assert is_command_safe("fdisk /dev/sda") is False

    def test_dangerous_mkfs(self):
        assert is_command_safe("mkfs.ext4 /dev/sda1") is False

    def test_dangerous_dd(self):
        assert is_command_safe("dd if=/dev/zero of=/dev/sda") is False

    def test_dangerous_fork_bomb(self):
        assert is_command_safe(":(){ :|:& };:") is False

    def test_dangerous_dev_sda(self):
        assert is_command_safe("> /dev/sda") is False

    def test_dangerous_deltree(self):
        assert is_command_safe("deltree /y C:\\") is False

    def test_empty_command(self):
        assert is_command_safe("") is False

    def test_none_command(self):
        assert is_command_safe(None) is False

    def test_non_string_command(self):
        assert is_command_safe(123) is False

    def test_case_insensitive(self):
        """危险命令匹配应不区分大小写"""
        assert is_command_safe("RM -RF /") is False
        assert is_command_safe("Format C:") is False


# ===========================================================================
# sanitize_input
# ===========================================================================
class TestSanitizeInput:
    def test_normal_text(self):
        assert sanitize_input("hello world") == "hello world"

    def test_strip_whitespace(self):
        assert sanitize_input("  hello  ") == "hello"

    def test_max_length(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text, max_length=100)
        assert len(result) <= 100

    def test_default_max_length(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text)
        assert len(result) <= 10000

    def test_removes_control_chars(self):
        """控制字符应被移除"""
        text_with_ctrl = "hello\x00world\x07!"
        result = sanitize_input(text_with_ctrl)
        assert "\x00" not in result
        assert "\x07" not in result
        assert "hello" in result

    def test_removes_zero_width_chars(self):
        """零宽字符应被移除"""
        text_with_zw = "hello\u200bworld\ufeff!"
        result = sanitize_input(text_with_zw)
        assert "\u200b" not in result
        assert "\ufeff" not in result

    def test_preserves_newlines(self):
        """换行符应被保留"""
        assert sanitize_input("hello\nworld") == "hello\nworld"

    def test_preserves_tabs(self):
        """制表符应被保留"""
        assert sanitize_input("hello\tworld") == "hello\tworld"

    def test_non_string_input(self):
        """非字符串输入应被转为字符串"""
        result = sanitize_input(123)
        assert result == "123"


# ===========================================================================
# is_plugin_url_safe
# ===========================================================================
class TestIsPluginUrlSafe:
    def test_valid_https_url(self):
        assert is_plugin_url_safe("https://example.com/plugin.zip") is True

    def test_valid_http_url(self):
        assert is_plugin_url_safe("http://example.com/plugin.zip") is True

    def test_ftp_scheme_denied(self):
        assert is_plugin_url_safe("ftp://example.com/plugin.zip") is False

    def test_file_scheme_denied(self):
        assert is_plugin_url_safe("file:///etc/passwd") is False

    def test_javascript_scheme_denied(self):
        assert is_plugin_url_safe("javascript:alert(1)") is False

    def test_localhost_denied(self):
        assert is_plugin_url_safe("http://localhost:8080/plugin") is False

    def test_127_denied(self):
        assert is_plugin_url_safe("http://127.0.0.1:8080/plugin") is False

    def test_empty_url_denied(self):
        assert is_plugin_url_safe("") is False

    def test_none_url_denied(self):
        assert is_plugin_url_safe(None) is False

    def test_non_string_url_denied(self):
        assert is_plugin_url_safe(123) is False

    def test_no_hostname_denied(self):
        assert is_plugin_url_safe("https:///plugin.zip") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
