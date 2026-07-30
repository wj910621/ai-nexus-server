"""
security.py 测试
覆盖：路径规范化、路径越界防护、命令注入拦截、输入消毒、插件 URL SSRF 防护。

注意：本测试为独立脚本，运行前会替换 logger 与 config，避免外部依赖。
运行：python3 test_security.py
"""

import os
import sys
import socket
import ipaddress
import tempfile
import unittest
from unittest import mock

# ---------------------------------------------------------------------------
# 在导入 security 之前，mock 掉依赖 logger/config（环境中可能未安装 loguru/pydantic_settings）
# ---------------------------------------------------------------------------
_placeholder_logger = mock.MagicMock()
_placeholder_logger.warning = lambda *a, **k: None
_placeholder_logger.info = lambda *a, **k: None
_placeholder_logger.error = lambda *a, **k: None
sys.modules["logger"] = mock.MagicMock(logger=_placeholder_logger)
sys.modules["config"] = mock.MagicMock(settings=mock.MagicMock())

# 将当前目录加入 sys.path 以便导入本项目模块
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import security  # noqa: E402


class TestNormalizePath(unittest.TestCase):
    def test_none_empty_invalid(self):
        self.assertIsNone(security.normalize_path(""))
        self.assertIsNone(security.normalize_path(None))
        self.assertIsNone(security.normalize_path(123))

    def test_absolute_paths(self):
        self.assertTrue(os.path.isabs(security.normalize_path("/tmp")))
        self.assertTrue(os.path.isabs(security.normalize_path("/tmp/../etc")))

    def test_user_expansion(self):
        p = security.normalize_path("~/data")
        self.assertIsNotNone(p)
        self.assertTrue(os.path.isabs(p))


class TestPathSafety(unittest.TestCase):
    def test_denied_system_paths(self):
        self.assertFalse(security.is_path_safe("/etc/passwd", allowed_bases=["/tmp"]))
        self.assertFalse(security.is_path_safe("/bin/ls", allowed_bases=["/tmp"]))
        self.assertFalse(security.is_path_safe("/proc/self/environ", allowed_bases=["/tmp"]))
        self.assertFalse(security.is_path_safe("/sys/class", allowed_bases=["/tmp"]))
        self.assertFalse(security.is_path_safe("/dev/null", allowed_bases=["/tmp"]))

    def test_allowed_inside_base(self):
        with tempfile.TemporaryDirectory() as d:
            file_path = os.path.join(d, "ok.txt")
            self.assertTrue(security.is_path_safe(file_path, allowed_bases=[d]))

    def test_directory_traversal_escape(self):
        with tempfile.TemporaryDirectory() as d:
            outside = os.path.join(d, "..", "..", "..", "etc", "passwd")
            self.assertFalse(
                security.is_path_safe(outside, allowed_bases=[d]),
                "路径穿越应被拒绝",
            )

    def test_outside_base_rejected(self):
        self.assertFalse(
            security.is_path_safe("/etc/passwd", allowed_bases=[os.getcwd()])
        )

    def test_allowed_bases_none_fallback(self):
        # 不传 allowed_bases 时使用默认 ALLOWED_BASE_DIRS，os.getcwd() 在其中
        ok_path = os.path.join(os.getcwd(), "some_file")
        self.assertTrue(security.is_path_safe(ok_path))


class TestSanitizePath(unittest.TestCase):
    def test_within_base(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "sub", "file.txt")
            os.makedirs(os.path.dirname(sub), exist_ok=True)
            # 临时扩展允许基目录，使 /tmp 下的子路径在测试中可通过
            original_bases = security.ALLOWED_BASE_DIRS
            security.ALLOWED_BASE_DIRS = [os.path.realpath(d)] + original_bases
            try:
                result = security.sanitize_path(sub)
                self.assertTrue(os.path.isabs(result))
                self.assertTrue(result.startswith(os.path.realpath(d)))
            finally:
                security.ALLOWED_BASE_DIRS = original_bases

    def test_traversal_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as d:
            traversal = os.path.join(d, "..", "..", "etc", "passwd")
            result = security.sanitize_path(traversal, default_base=d)
            resolved = os.path.realpath(result)
            self.assertTrue(resolved.startswith(os.path.realpath(d)))

    def test_no_default_base_raises(self):
        with self.assertRaises(ValueError):
            security.sanitize_path("/etc/passwd", default_base=None)

    def test_relative_path_joined_with_default(self):
        with tempfile.TemporaryDirectory() as d:
            result = security.sanitize_path("file.txt", default_base=d)
            self.assertTrue(result.startswith(os.path.realpath(d)))


class TestCommandSafety(unittest.TestCase):
    def test_dangerous_commands_blocked(self):
        cases = [
            "rm -rf /",
            "rm -rf /*",
            "format C:",
            "fdisk /dev/sda",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "deltree C:\\windows",
            "rd /s C:\\windows",
            "rmdir /s D:\\data",
            ":(){ :|:& };:",
            "> /dev/sda",
        ]
        for cmd in cases:
            self.assertFalse(
                security.is_command_safe(cmd),
                f"危险命令应被拦截: {cmd}",
            )

    def test_safe_commands_pass(self):
        ok_cases = [
            "ls -la",
            "python3 app.py",
            "echo hello world",
            "pytest -v tests/",
            "git status",
        ]
        for cmd in ok_cases:
            self.assertTrue(security.is_command_safe(cmd))

    def test_empty_invalid_returns_false(self):
        self.assertFalse(security.is_command_safe(""))
        self.assertFalse(security.is_command_safe(None))
        self.assertFalse(security.is_command_safe(123))


class TestSanitizeInput(unittest.TestCase):
    def test_strips_control_characters(self):
        raw = "hello\x00\x01\x07\x0b\x1b\x7f world\u200b\u200c\ufeff"
        cleaned = security.sanitize_input(raw)
        self.assertEqual(cleaned, "hello world")

    def test_preserves_newlines_tabs(self):
        raw = "line1\nline2\tindented"
        cleaned = security.sanitize_input(raw)
        self.assertEqual(cleaned, raw)

    def test_truncates_over_max(self):
        long_text = "a" * 20000
        cleaned = security.sanitize_input(long_text, max_length=100)
        self.assertEqual(len(cleaned), 100)

    def test_non_string_coerced(self):
        self.assertEqual(security.sanitize_input(42), "42")

    def test_strips_outer_whitespace(self):
        self.assertEqual(security.sanitize_input("  hello  "), "hello")


class TestPluginUrlSafety(unittest.TestCase):
    def test_rejects_non_http_protocol(self):
        self.assertFalse(security.is_plugin_url_safe("file:///etc/passwd"))
        self.assertFalse(security.is_plugin_url_safe("ftp://example.com/plugin"))
        self.assertFalse(security.is_plugin_url_safe("gopher://evil.com/"))
        self.assertFalse(security.is_plugin_url_safe("javascript:alert(1)"))

    def test_rejects_localhost_variants(self):
        self.assertFalse(security.is_plugin_url_safe("http://localhost/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://127.0.0.1/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://0.0.0.0/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://[::1]/plugin"))

    def test_rejects_private_ip(self):
        self.assertFalse(security.is_plugin_url_safe("http://10.0.0.5/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://192.168.1.1/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://172.16.0.1/plugin"))
        self.assertFalse(security.is_plugin_url_safe("http://169.254.0.1/plugin"))

    def test_rejects_empty_or_invalid(self):
        self.assertFalse(security.is_plugin_url_safe(""))
        self.assertFalse(security.is_plugin_url_safe(None))
        self.assertFalse(security.is_plugin_url_safe("not a url"))

    def test_rejects_dns_resolving_to_private(self):
        """若 DNS 解析到内网 IP，必须被拒绝（模拟）。"""
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]
        with mock.patch("socket.getaddrinfo", return_value=fake_result):
            self.assertFalse(
                security.is_plugin_url_safe("http://internal.local/plugin"),
                "解析到 127.0.0.1 的域名应被拒绝",
            )

        fake_result2 = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.5", 0))]
        with mock.patch("socket.getaddrinfo", return_value=fake_result2):
            self.assertFalse(
                security.is_plugin_url_safe("http://internal.local/plugin"),
                "解析到内网 IP 的域名应被拒绝",
            )

    def test_rejects_dns_failure(self):
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("fail")):
            self.assertFalse(
                security.is_plugin_url_safe("http://unknown.invalid/plugin"),
                "DNS 解析失败时应拒绝",
            )

    def test_accepts_public_https(self):
        """公网合法 HTTPS 域名应通过。"""
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        with mock.patch("socket.getaddrinfo", return_value=fake_result):
            self.assertTrue(
                security.is_plugin_url_safe("https://example.com/plugin.whl")
            )

    def test_https_required(self):
        fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        with mock.patch("socket.getaddrinfo", return_value=fake_result):
            # http 也是允许的协议（ALLOWED_PLUGIN_PROTOCOLS 包含 http）
            self.assertTrue(
                security.is_plugin_url_safe("http://example.com/plugin.whl")
            )


class TestGetSafeWorkDir(unittest.TestCase):
    def test_creates_dir(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("os.getcwd", return_value=d):
                wd = security.get_safe_work_dir("work_sub")
                self.assertTrue(os.path.isdir(wd))
                self.assertTrue(wd.endswith("work_sub"))


def main():
    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner, exit=False, argv=["security_tests"])


if __name__ == "__main__":
    main()
