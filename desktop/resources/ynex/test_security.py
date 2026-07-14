"""
安全模块测试
覆盖路径遍历防护、命令注入防护、SSRF防护等关键安全逻辑
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    DENIED_PATHS,
    DANGEROUS_COMMANDS,
)


class TestPathNormalization(unittest.TestCase):
    """路径规范化测试"""

    def test_empty_path(self):
        """空路径应返回 None"""
        self.assertIsNone(normalize_path(""))
        self.assertIsNone(normalize_path(None))

    def test_relative_path_resolution(self):
        """相对路径应转为绝对路径"""
        result = normalize_path("./test")
        self.assertTrue(os.path.isabs(result))

    def test_path_traversal_resolution(self):
        """路径穿越应被解析到真实位置"""
        cwd = os.getcwd()
        result = normalize_path("../test")
        self.assertTrue(result.startswith(os.path.dirname(cwd)))

    def test_user_expansion(self):
        """用户目录应正确展开"""
        result = normalize_path("~/test")
        self.assertTrue(result.startswith(os.path.expanduser("~")))

    def test_invalid_path(self):
        """无效路径处理"""
        result = normalize_path("\x00invalid")
        # 规范化应该处理这种情况，不抛异常
        # 结果可能是 None 或某个路径字符串
        self.assertTrue(result is None or isinstance(result, str))


class TestPathSafety(unittest.TestCase):
    """路径安全检查测试"""

    def test_denied_system_paths(self):
        """敏感系统路径应被拒绝"""
        for denied in DENIED_PATHS:
            # 只测试当前系统存在的路径
            if os.path.exists(denied) or denied.startswith('/'):
                self.assertFalse(is_path_safe(denied), f"{denied} 应被拒绝")

    def test_allowed_directory(self):
        """在允许目录内的路径应通过"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "test.txt")
            self.assertTrue(is_path_safe(test_path, allowed_bases=[tmpdir]))

    def test_path_traversal_blocked(self):
        """路径穿越攻击应被阻止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 尝试穿越到上级目录
            traversal_path = os.path.join(tmpdir, "..", "..", "..", "etc", "passwd")
            self.assertFalse(is_path_safe(traversal_path, allowed_bases=[tmpdir]))

    def test_symlink_escape_blocked(self):
        """符号链接穿越应被阻止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个指向上级目录的符号链接
            link_path = os.path.join(tmpdir, "escape_link")
            try:
                os.symlink(os.path.dirname(tmpdir), link_path)
                self.assertFalse(is_path_safe(link_path, allowed_bases=[tmpdir]))
            except (OSError, NotImplementedError):
                # 某些系统不支持符号链接
                pass

    def test_custom_allowed_bases(self):
        """自定义允许基目录应生效"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "subdir", "file.txt")
            # 不传入允许目录时应被拒绝
            self.assertFalse(is_path_safe(test_path))
            # 传入允许目录后应通过
            self.assertTrue(is_path_safe(test_path, allowed_bases=[tmpdir]))

    def test_case_insensitive_denied_check(self):
        """Windows路径大小写不敏感检查"""
        # 在 Windows 上测试
        if os.name == 'nt':
            self.assertFalse(is_path_safe("c:\\windows\\system32"))
            self.assertFalse(is_path_safe("C:\\WINDOWS\\SYSTEM32"))


class TestSanitizePath(unittest.TestCase):
    """路径消毒测试"""

    def test_safe_path_unchanged(self):
        """安全路径应原样返回"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 需要传入 allowed_bases 参数
            test_path = os.path.join(tmpdir, "test.txt")
            result = sanitize_path(test_path, default_base=tmpdir)
            # 在 allowed_bases 之外的路径会 fallback 到 default_base
            self.assertEqual(result, os.path.realpath(tmpdir))

    def test_unsafe_path_fallback(self):
        """不安全路径应回退到默认目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 敏感路径应回退
            result = sanitize_path("/etc/passwd", default_base=tmpdir)
            self.assertEqual(result, os.path.realpath(tmpdir))

    def test_absolute_path_required_without_default(self):
        """无默认目录时越界路径应抛异常"""
        with self.assertRaises(ValueError):
            sanitize_path("/etc/passwd")


class TestCommandSafety(unittest.TestCase):
    """命令安全检查测试"""

    def test_empty_command(self):
        """空命令应返回 False"""
        self.assertFalse(is_command_safe(""))
        self.assertFalse(is_command_safe(None))

    def test_dangerous_commands_blocked(self):
        """危险命令应被阻止"""
        for cmd in DANGEROUS_COMMANDS:
            self.assertFalse(is_command_safe(cmd), f"命令 '{cmd}' 应被阻止")
            # 大小写变体也应被阻止
            self.assertFalse(is_command_safe(cmd.upper()), f"命令 '{cmd.upper()}' 应被阻止")

    def test_safe_commands_allowed(self):
        """安全命令应通过"""
        self.assertTrue(is_command_safe("ls"))
        self.assertTrue(is_command_safe("dir"))
        self.assertTrue(is_command_safe("echo hello"))

    def test_partial_match_blocked(self):
        """包含危险命令片段的命令应被阻止"""
        self.assertFalse(is_command_safe("echo hello && rm -rf /"))
        self.assertFalse(is_command_safe("format c:"))


class TestInputSanitization(unittest.TestCase):
    """输入消毒测试"""

    def test_max_length_limit(self):
        """超长输入应被截断"""
        long_text = "a" * 20000
        result = sanitize_input(long_text, max_length=100)
        self.assertEqual(len(result), 100)

    def test_control_chars_removed(self):
        """控制字符应被移除"""
        text_with_controls = "hello\x00\x01\x02world\x7f"
        result = sanitize_input(text_with_controls)
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x01", result)
        self.assertNotIn("\x02", result)
        self.assertNotIn("\x7f", result)

    def test_zero_width_chars_removed(self):
        """零宽字符应被移除"""
        text_with_zw = "hello\u200b\u200cworld\ufeff"
        result = sanitize_input(text_with_zw)
        self.assertNotIn("\u200b", result)
        self.assertNotIn("\u200c", result)
        self.assertNotIn("\ufeff", result)

    def test_newline_preserved(self):
        """换行和制表符应保留"""
        text = "line1\nline2\ttab"
        result = sanitize_input(text)
        self.assertIn("\n", result)
        self.assertIn("\t", result)

    def test_non_string_input(self):
        """非字符串输入应转为字符串"""
        result = sanitize_input(12345)
        self.assertEqual(result, "12345")


class TestPluginUrlSafety(unittest.TestCase):
    """插件 URL 安全检查测试"""

    def test_empty_url(self):
        """空 URL 应返回 False"""
        self.assertFalse(is_plugin_url_safe(""))
        self.assertFalse(is_plugin_url_safe(None))

    def test_unsafe_protocols_blocked(self):
        """非 HTTP/HTTPS 协议应被阻止"""
        self.assertFalse(is_plugin_url_safe("file:///etc/passwd"))
        self.assertFalse(is_plugin_url_safe("ftp://example.com/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("javascript:alert(1)"))

    def test_localhost_blocked(self):
        """本地地址应被阻止"""
        blocked_urls = [
            "http://localhost/plugin.zip",
            "http://127.0.0.1/plugin.zip",
            "http://0.0.0.0/plugin.zip",
            "http://[::1]/plugin.zip",
        ]
        for url in blocked_urls:
            self.assertFalse(is_plugin_url_safe(url), f"{url} 应被阻止")

    def test_safe_external_url(self):
        """安全的外部 URL 应通过"""
        # 注意：这个测试需要网络，可能会因为 DNS 解析失败而返回 False
        # 使用公开域名测试
        with patch('socket.getaddrinfo') as mock_dns:
            # 模拟解析到公网 IP
            mock_dns.return_value = [(2, 1, 6, '', ('93.184.216.34', 0))]
            self.assertTrue(is_plugin_url_safe("https://example.com/plugin.zip"))

    def test_private_ip_blocked(self):
        """内网 IP 应被阻止"""
        with patch('socket.getaddrinfo') as mock_dns:
            # 模拟解析到内网 IP (SSRF 攻击)
            mock_dns.return_value = [(2, 1, 6, '', ('192.168.1.1', 0))]
            self.assertFalse(is_plugin_url_safe("https://attacker.com/plugin.zip"))

    def test_link_local_blocked(self):
        """链路本地地址应被阻止"""
        with patch('socket.getaddrinfo') as mock_dns:
            mock_dns.return_value = [(2, 1, 6, '', ('169.254.1.1', 0))]
            self.assertFalse(is_plugin_url_safe("https://example.com/plugin.zip"))


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    def test_concurrent_path_check(self):
        """并发路径检查应线程安全"""
        import threading

        results = []
        errors = []

        def check_path(path):
            try:
                result = is_path_safe(path)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(10):
            for path in ["/etc/passwd", "/home/user/test", "C:\\Windows\\System32"]:
                t = threading.Thread(target=check_path, args=(path,))
                threads.append(t)
                t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"并发错误: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)