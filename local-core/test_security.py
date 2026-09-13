"""
security.py 安全边界测试
覆盖范围：
- normalize_path：非法输入、空值、异常
- is_path_safe：目录穿越、符号链接穿透、敏感系统路径、自定义基目录
- sanitize_path：越界 fallback、默认基目录拼接、非法路径 ValueError
- is_command_safe：黑名单命中（含大小写、子串）、空值、None、边界安全命令
- sanitize_input：超长截断、控制字符、零宽/U+FEFF、非字符串输入
- is_plugin_url_safe：协议白名单、localhost/127.0.0.1 拦截、内网 IP 拦截、公网域名放行
"""
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import security


class TestNormalizePath(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_empty_and_invalid(self):
        self.assertIsNone(security.normalize_path(""))
        self.assertIsNone(security.normalize_path(None))
        self.assertIsNone(security.normalize_path(123))

    def test_normalizes_relative(self):
        r = security.normalize_path("foo/bar.txt")
        self.assertEqual(r, os.path.realpath(os.path.join(self.tmpdir, "foo", "bar.txt")))

    def test_resolves_parent_traversal(self):
        base = Path(self.tmpdir)
        (base / "a").mkdir()
        (base / "outside.txt").write_text("x")
        r = security.normalize_path("a/../outside.txt")
        self.assertEqual(r, str((base / "outside.txt").resolve()))

    def test_expands_tilde(self):
        r = security.normalize_path("~")
        self.assertEqual(r, os.path.realpath(os.path.expanduser("~")))


class TestIsPathSafe(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_simple_file_within_cwd(self):
        f = Path(self.tmpdir) / "ok.txt"
        f.write_text("x")
        self.assertTrue(security.is_path_safe(str(f), allowed_bases=[self.tmpdir]))

    def test_escapes_base_via_parent(self):
        base = Path(self.tmpdir) / "base"
        base.mkdir()
        escapee = Path(self.tmpdir) / "secret.txt"
        escapee.write_text("x")
        attack = str(base / ".." / "secret.txt")
        self.assertFalse(security.is_path_safe(attack, allowed_bases=[str(base)]))

    def test_blocked_denied_paths(self):
        self.assertFalse(security.is_path_safe("/etc/passwd", allowed_bases=["/tmp"]))
        self.assertFalse(security.is_path_safe("/usr/bin/ls", allowed_bases=["/tmp"]))

    def test_symlink_escape(self):
        base = Path(self.tmpdir) / "base"
        base.mkdir()
        outside = Path(self.tmpdir) / "secret"
        outside.write_text("x")
        link = base / "evil"
        os.symlink(str(outside), str(link))
        self.assertFalse(security.is_path_safe(str(link), allowed_bases=[str(base)]))

    def test_empty_path_unsafe(self):
        self.assertFalse(security.is_path_safe("", allowed_bases=["/tmp"]))

    def test_custom_allowed_bases_respected(self):
        other = Path(self.tmpdir) / "other"
        other.mkdir()
        self.assertTrue(security.is_path_safe(str(other), allowed_bases=[str(other)]))


class TestSanitizePath(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_within_allowed_base(self):
        safe_dir = Path(self.tmpdir) / "data"
        safe_dir.mkdir()
        safe = safe_dir / "a.txt"
        safe.write_text("x")
        # ALLOWED_BASE_DIRS 在 import 时固化为原 cwd，这里临时扩展
        with patch.object(security, "ALLOWED_BASE_DIRS",
                          list(security.ALLOWED_BASE_DIRS) + [str(safe_dir)]):
            out = security.sanitize_path(str(safe))
        self.assertEqual(out, str(safe.resolve()))

    def test_outside_base_falls_back_to_default(self):
        default = str((Path(self.tmpdir) / "default"))
        Path(default).mkdir()
        out = security.sanitize_path("../../etc/passwd", default_base=default)
        self.assertEqual(out, str(Path(default).resolve()))

    def test_outside_base_no_default_raises(self):
        self.assertRaises(ValueError, security.sanitize_path, "../../etc/passwd")


class TestIsCommandSafe(unittest.TestCase):
    def test_known_dangerous_blocked(self):
        samples = [
            "rm -rf /",
            "RM -RF /tmp/*",
            "echo hello; rm -rf /*",
            ":(){ :|:& };:",
            "> /dev/sda",
            "format C:",
            "dd if=/dev/zero of=/dev/sda",
        ]
        for cmd in samples:
            self.assertFalse(security.is_command_safe(cmd), f"expected block: {cmd!r}")

    def test_empty_and_invalid(self):
        self.assertFalse(security.is_command_safe(""))
        self.assertFalse(security.is_command_safe(None))
        self.assertFalse(security.is_command_safe(123))

    def test_harmless_allowed(self):
        ok_samples = [
            "echo hello",
            "ls -la",
            "python3 -m pytest",
            "git status",
            "npm run build",
            "cat README.md",
        ]
        for cmd in ok_samples:
            self.assertTrue(security.is_command_safe(cmd), f"expected allow: {cmd!r}")


class TestSanitizeInput(unittest.TestCase):
    def test_removes_control_and_zero_width(self):
        raw = "hello\u0000\u0001\u200B\uFEFF\u007fworld"
        out = security.sanitize_input(raw)
        self.assertEqual(out, "helloworld")

    def test_preserves_newline_tab(self):
        raw = "line1\nline2\there\tthere"
        self.assertEqual(security.sanitize_input(raw), raw)

    def test_truncates(self):
        long_str = "a" * 20000
        out = security.sanitize_input(long_str, max_length=100)
        self.assertEqual(len(out), 100)

    def test_non_string_coerced(self):
        self.assertEqual(security.sanitize_input(42), "42")
        self.assertEqual(security.sanitize_input(None), "None")

    def test_strips(self):
        self.assertEqual(security.sanitize_input("  \n  hi  \n "), "hi")


class TestIsPluginUrlSafe(unittest.TestCase):
    def test_rejects_bad_scheme(self):
        bad = ["file:///etc/passwd", "ftp://example.com/x", "data:text/html,<script/>", None, ""]
        for u in bad:
            self.assertFalse(security.is_plugin_url_safe(u), f"expected block: {u!r}")

    def test_rejects_localhost_family(self):
        bad = [
            "http://localhost/x",
            "http://127.0.0.1/x",
            "http://0.0.0.0/x",
            "http://[::1]/x",
            "https://127.0.0.1:8080/x",
        ]
        for u in bad:
            self.assertFalse(security.is_plugin_url_safe(u), f"expected block: {u!r}")

    def test_rejects_private_ip_literal(self):
        bad = [
            "http://10.0.0.1/x",
            "http://192.168.1.1/x",
            "http://172.16.0.1/x",
            "http://169.254.1.1/x",
            "http://224.0.0.1/x",
            "http://203.0.113.1/x",
        ]
        for u in bad:
            self.assertFalse(security.is_plugin_url_safe(u), f"expected block: {u!r}")

    @patch.object(socket, "getaddrinfo")
    def test_rejects_dns_resolving_to_private(self, mock_gai):
        mock_gai.return_value = [(None, None, None, None, ("127.0.0.1", 80))]
        self.assertFalse(security.is_plugin_url_safe("http://rebind.example.com/x"))

    def test_allows_public_ip_literal(self):
        self.assertTrue(security.is_plugin_url_safe("https://8.8.8.8/x"))

    @patch.object(socket, "getaddrinfo")
    def test_allows_public_domain(self, mock_gai):
        mock_gai.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        self.assertTrue(security.is_plugin_url_safe("https://example.com/x"))

    @patch.object(socket, "getaddrinfo")
    def test_dns_error_rejected(self, mock_gai):
        mock_gai.side_effect = socket.gaierror("NXDOMAIN")
        self.assertFalse(security.is_plugin_url_safe("http://nxdomain.example/x"))


class TestGetSafeWorkDir(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_creates_dir_and_returns_realpath(self):
        out = security.get_safe_work_dir("subdir")
        self.assertTrue(os.path.isdir(out))
        self.assertEqual(out, os.path.realpath(out))


def main():
    unittest.main(verbosity=2)


if __name__ == "__main__":
    main()
