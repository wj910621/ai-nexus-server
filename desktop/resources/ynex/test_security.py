"""
安全模块测试
- 路径遍历防护
- 命令执行黑名单
- 输入消毒
- 插件URL SSRF防护
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
    ALLOWED_BASE_DIRS,
    DENIED_PATHS,
    DANGEROUS_COMMANDS,
)


class TestNormalizePath(unittest.TestCase):
    """路径规范化测试"""

    def test_empty_path_returns_none(self):
        self.assertIsNone(normalize_path(""))
        self.assertIsNone(normalize_path(None))

    def test_non_string_returns_none(self):
        self.assertIsNone(normalize_path(123))
        self.assertIsNone(normalize_path([]))

    def test_absolute_path_normalized(self):
        path = normalize_path("/tmp/test")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isabs(path))

    def test_relative_path_resolved(self):
        path = normalize_path("./test")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isabs(path))

    def test_user_expansion(self):
        path = normalize_path("~/test")
        self.assertIsNotNone(path)
        self.assertIn(os.path.expanduser("~"), path)

    def test_dotdot_resolved(self):
        base = os.getcwd()
        path = normalize_path(os.path.join(base, "subdir", ".."))
        self.assertIsNotNone(path)
        self.assertEqual(path, base)


class TestIsPathSafe(unittest.TestCase):
    """路径安全检查测试"""

    def test_current_dir_is_safe(self):
        self.assertTrue(is_path_safe(os.getcwd()))

    def test_subdir_is_safe(self):
        subdir = os.path.join(os.getcwd(), "data")
        self.assertTrue(is_path_safe(subdir))

    def test_sensitive_path_denied(self):
        for denied in ["/etc/passwd", "/etc/shadow", "/bin/ls", "/usr/bin/test",
                       "/proc/self/environ", "/dev/null"]:
            self.assertFalse(is_path_safe(denied), f"{denied} 应被拒绝")

    def test_path_traversal_denied(self):
        traversal = os.path.join(os.getcwd(), "..", "..", "etc", "passwd")
        self.assertFalse(is_path_safe(traversal))

    def test_dotdot_traversal_denied(self):
        self.assertFalse(is_path_safe("../../etc/passwd"))

    def test_custom_allowed_bases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertTrue(is_path_safe(tmpdir, allowed_bases=[tmpdir]))
            outside = os.path.join(os.path.dirname(tmpdir), "other")
            self.assertFalse(is_path_safe(outside, allowed_bases=[tmpdir]))

    def test_symlink_outside_base_denied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = "/etc/passwd"
            link = os.path.join(tmpdir, "link")
            try:
                os.symlink(target, link)
                self.assertFalse(is_path_safe(link, allowed_bases=[tmpdir]))
            except (OSError, AttributeError):
                self.skipTest("符号链接不可用")


class TestSanitizePath(unittest.TestCase):
    """路径消毒测试"""

    def test_safe_path_returned(self):
        path = sanitize_path(os.getcwd())
        self.assertEqual(path, os.path.realpath(os.getcwd()))

    def test_relative_with_default_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_path("subdir", default_base=tmpdir)
            self.assertTrue(result.startswith(os.path.realpath(tmpdir)))

    def test_unsafe_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_path("../../etc/passwd", default_base=tmpdir)
            self.assertEqual(result, os.path.realpath(tmpdir))

    def test_unsafe_no_default_raises(self):
        with self.assertRaises(ValueError):
            sanitize_path("../../etc/passwd")


class TestIsCommandSafe(unittest.TestCase):
    """命令安全检查测试"""

    def test_empty_command_unsafe(self):
        self.assertFalse(is_command_safe(""))
        self.assertFalse(is_command_safe(None))
        self.assertFalse(is_command_safe(123))

    def test_dangerous_commands_blocked(self):
        for cmd in DANGEROUS_COMMANDS:
            self.assertFalse(is_command_safe(cmd), f"'{cmd}' 应被拦截")
            self.assertFalse(is_command_safe(cmd.upper()), f"'{cmd.upper()}' 应被拦截（大小写不敏感）")
            self.assertFalse(is_command_safe(f"sudo {cmd}"), f"'sudo {cmd}' 应被拦截")

    def test_safe_commands_allowed(self):
        for cmd in ["ls", "echo hello", "cat /tmp/test", "python script.py"]:
            self.assertTrue(is_command_safe(cmd), f"'{cmd}' 应被允许")

    def test_fork_bomb_blocked(self):
        self.assertFalse(is_command_safe(":(){ :|:& };:"))


class TestSanitizeInput(unittest.TestCase):
    """输入消毒测试"""

    def test_max_length_enforced(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text, max_length=100)
        self.assertEqual(len(result), 100)

    def test_control_chars_removed(self):
        text = "hello\x00\x01\x02world"
        result = sanitize_input(text)
        self.assertEqual(result, "helloworld")

    def test_newlines_tabs_preserved(self):
        text = "hello\n\tworld"
        result = sanitize_input(text)
        self.assertIn("\n", result)
        self.assertIn("\t", result)

    def test_zero_width_chars_removed(self):
        text = "hello\u200bworld\u200c!"
        result = sanitize_input(text)
        self.assertEqual(result, "helloworld!")

    def test_non_string_input(self):
        result = sanitize_input(12345)
        self.assertEqual(result, "12345")

    def test_strip_whitespace(self):
        result = sanitize_input("  hello  ")
        self.assertEqual(result, "hello")

    def test_bom_removed(self):
        text = "\ufeffhello"
        result = sanitize_input(text)
        self.assertEqual(result, "hello")


class TestPluginUrlSafe(unittest.TestCase):
    """插件URL SSRF防护测试"""

    def test_empty_url_unsafe(self):
        self.assertFalse(is_plugin_url_safe(""))
        self.assertFalse(is_plugin_url_safe(None))

    def test_file_protocol_blocked(self):
        self.assertFalse(is_plugin_url_safe("file:///etc/passwd"))

    def test_ftp_protocol_blocked(self):
        self.assertFalse(is_plugin_url_safe("ftp://example.com/file"))

    def test_localhost_blocked(self):
        self.assertFalse(is_plugin_url_safe("http://localhost:8080/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://127.0.0.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://0.0.0.0/plugin.zip"))

    def test_ipv6_loopback_blocked(self):
        self.assertFalse(is_plugin_url_safe("http://[::1]/plugin.zip"))

    def test_private_ip_blocked(self):
        self.assertFalse(is_plugin_url_safe("http://192.168.1.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://10.0.0.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://172.16.0.1/plugin.zip"))

    def test_link_local_blocked(self):
        self.assertFalse(is_plugin_url_safe("http://169.254.1.1/plugin.zip"))

    def test_multicast_blocked(self):
        self.assertFalse(is_plugin_url_safe("http://224.0.0.1/plugin.zip"))

    def test_valid_external_url_allowed(self):
        self.assertTrue(is_plugin_url_safe("https://github.com/user/repo/raw/main/plugin.zip"))
        self.assertTrue(is_plugin_url_safe("http://example.com/plugin.zip"))

    def test_no_hostname_rejected(self):
        self.assertFalse(is_plugin_url_safe("https:///plugin.zip"))


class TestGetSafeWorkDir(unittest.TestCase):
    """安全工作目录测试"""

    def test_returns_absolute_path(self):
        path = get_safe_work_dir("test_data")
        self.assertTrue(os.path.isabs(path))

    def test_creates_directory(self):
        import shutil
        test_dir_name = "_test_safe_work_dir"
        test_path = os.path.join(os.getcwd(), test_dir_name)
        if os.path.exists(test_path):
            shutil.rmtree(test_path)
        try:
            path = get_safe_work_dir(test_dir_name)
            self.assertTrue(os.path.isdir(path))
        finally:
            if os.path.exists(test_path):
                shutil.rmtree(test_path)


def main():
    print("=== 安全模块测试 ===\n")
    unittest.main(verbosity=2, exit=False)
    print("\n=== 安全模块测试完成 ===")


if __name__ == "__main__":
    main()
