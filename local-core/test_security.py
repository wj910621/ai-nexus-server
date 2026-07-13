"""
安全模块测试
覆盖路径遍历防护、命令安全检查、输入消毒、URL 安全校验等核心安全功能
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestPathNormalization(unittest.TestCase):
    """路径规范化测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_normalize_path_absolute(self):
        """测试绝对路径规范化"""
        path = "/workspace/data/test.txt"
        result = self.security.normalize_path(path)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isabs(result))

    def test_normalize_path_relative(self):
        """测试相对路径规范化"""
        path = "data/test.txt"
        result = self.security.normalize_path(path)
        self.assertIsNotNone(result)
        # 相对路径应转为绝对路径
        self.assertTrue(os.path.isabs(result))

    def test_normalize_path_with_user_expansion(self):
        """测试用户目录展开"""
        path = "~/test.txt"
        result = self.security.normalize_path(path)
        self.assertIsNotNone(result)
        # 应展开 ~ 为用户目录
        self.assertNotIn("~", result)

    def test_normalize_path_with_dotdot(self):
        """测试路径穿越（..）规范化"""
        path = "/workspace/data/../test.txt"
        result = self.security.normalize_path(path)
        self.assertIsNotNone(result)
        # 应解析 .. 为正确路径
        self.assertNotIn("..", result)

    def test_normalize_path_empty(self):
        """测试空路径"""
        result = self.security.normalize_path("")
        self.assertIsNone(result)

    def test_normalize_path_none(self):
        """测试 None 输入"""
        result = self.security.normalize_path(None)
        self.assertIsNone(result)

    def test_normalize_path_non_string(self):
        """测试非字符串输入"""
        result = self.security.normalize_path(12345)
        self.assertIsNone(result)


class TestPathSafetyChecks(unittest.TestCase):
    """路径安全检查测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security
        cls.allowed_dirs = [os.getcwd()]

    def test_is_path_safe_allowed_dir(self):
        """测试允许目录内的路径"""
        path = os.path.join(os.getcwd(), "data", "test.txt")
        result = self.security.is_path_safe(path, self.allowed_dirs)
        self.assertTrue(result)

    def test_is_path_safe_denied_path(self):
        """测试敏感路径访问拒绝"""
        # Linux 系统路径（当前运行环境是 Linux）
        result = self.security.is_path_safe("/etc/passwd", self.allowed_dirs)
        self.assertFalse(result)

        result = self.security.is_path_safe("/bin/bash", self.allowed_dirs)
        self.assertFalse(result)

        result = self.security.is_path_safe("/usr/bin/python", self.allowed_dirs)
        self.assertFalse(result)

        result = self.security.is_path_safe("/proc/self", self.allowed_dirs)
        self.assertFalse(result)

    def test_is_path_safe_path_traversal(self):
        """测试路径穿越攻击"""
        # 尝试穿越到上级目录
        path = os.path.join(os.getcwd(), "data", "..", "..", "etc", "passwd")
        result = self.security.is_path_safe(path, self.allowed_dirs)
        self.assertFalse(result)

    def test_is_path_safe_symlink_escape(self):
        """测试符号链接逃逸（模拟）"""
        # 注意：实际符号链接需要文件系统支持，这里测试逻辑
        # 规范化路径不应允许通过符号链接逃逸
        result = self.security.is_path_safe("/proc/self/root", self.allowed_dirs)
        self.assertFalse(result)

    def test_is_path_safe_empty(self):
        """测试空路径安全检查"""
        result = self.security.is_path_safe("", self.allowed_dirs)
        self.assertFalse(result)

    def test_is_path_safe_none(self):
        """测试 None 路径"""
        result = self.security.is_path_safe(None, self.allowed_dirs)
        self.assertFalse(result)


class TestSanitizePath(unittest.TestCase):
    """路径消毒测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security
        cls.default_base = os.getcwd()

    def test_sanitize_path_safe_path(self):
        """测试安全路径的消毒"""
        path = os.path.join(self.default_base, "data", "safe.txt")
        result = self.security.sanitize_path(path, self.default_base)
        self.assertIsNotNone(result)

    def test_sanitize_path_escape_to_base(self):
        """测试路径越界回退到基目录"""
        # 越界路径应回退到默认基目录
        result = self.security.sanitize_path("/etc/passwd", self.default_base)
        # 应返回默认基目录
        self.assertTrue(
            os.path.commonpath([self.default_base, result]) == self.default_base
        )

    def test_sanitize_path_no_base_raises(self):
        """测试无基目录时的越界路径抛出异常"""
        with self.assertRaises(ValueError):
            self.security.sanitize_path("/etc/passwd")


class TestCommandSafety(unittest.TestCase):
    """命令安全检查测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_is_command_safe_normal_command(self):
        """测试正常命令"""
        result = self.security.is_command_safe("ls -la")
        self.assertTrue(result)

        result = self.security.is_command_safe("git status")
        self.assertTrue(result)

    def test_is_command_safe_format_command(self):
        """测试危险格式化命令"""
        result = self.security.is_command_safe("format c:")
        self.assertFalse(result)

    def test_is_command_safe_dd_command(self):
        """测试危险 dd 命令"""
        result = self.security.is_command_safe("dd if=/dev/zero of=/dev/sda")
        self.assertFalse(result)

    def test_is_command_safe_rm_rf_root(self):
        """测试删除根目录命令"""
        result = self.security.is_command_safe("rm -rf /")
        self.assertFalse(result)

        result = self.security.is_command_safe("rm -rf /*")
        self.assertFalse(result)

    def test_is_command_safe_fork_bomb(self):
        """测试 Fork 炸弹"""
        result = self.security.is_command_safe(":(){ :|:& };:")
        self.assertFalse(result)

    def test_is_command_safe_empty(self):
        """测试空命令"""
        result = self.security.is_command_safe("")
        self.assertFalse(result)

    def test_is_command_safe_none(self):
        """测试 None 命令"""
        result = self.security.is_command_safe(None)
        self.assertFalse(result)

    def test_is_command_safe_non_string(self):
        """测试非字符串命令"""
        result = self.security.is_command_safe(["rm", "-rf"])
        self.assertFalse(result)


class TestInputSanitization(unittest.TestCase):
    """输入消毒测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_sanitize_input_normal(self):
        """测试正常输入"""
        text = "这是一个正常的测试文本"
        result = self.security.sanitize_input(text)
        self.assertEqual(result, text)

    def test_sanitize_input_control_chars(self):
        """测试控制字符过滤"""
        text = "测试\x00\x01\x02文本"
        result = self.security.sanitize_input(text)
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x01", result)
        self.assertNotIn("\x02", result)

    def test_sanitize_input_zero_width_chars(self):
        """测试零宽字符过滤"""
        text = "测试\u200b\u200c\u200d文本"
        result = self.security.sanitize_input(text)
        self.assertNotIn("\u200b", result)
        self.assertNotIn("\u200c", result)
        self.assertNotIn("\u200d", result)

    def test_sanitize_input_length_limit(self):
        """测试长度限制"""
        text = "a" * 20000
        result = self.security.sanitize_input(text, max_length=1000)
        self.assertEqual(len(result), 1000)

    def test_sanitize_input_preserves_newline(self):
        """测试保留换行符"""
        text = "第一行\n第二行\n第三行"
        result = self.security.sanitize_input(text)
        self.assertIn("\n", result)

    def test_sanitize_input_preserves_tab(self):
        """测试保留制表符"""
        text = "列1\t列2\t列3"
        result = self.security.sanitize_input(text)
        self.assertIn("\t", result)

    def test_sanitize_input_non_string(self):
        """测试非字符串输入"""
        result = self.security.sanitize_input(12345)
        self.assertEqual(result, "12345")


class TestPluginUrlSafety(unittest.TestCase):
    """插件 URL 安全测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_is_plugin_url_safe_http(self):
        """测试 HTTP 协议"""
        result = self.security.is_plugin_url_safe("http://example.com/plugin.zip")
        self.assertTrue(result)

    def test_is_plugin_url_safe_https(self):
        """测试 HTTPS 协议"""
        result = self.security.is_plugin_url_safe("https://example.com/plugin.zip")
        self.assertTrue(result)

    def test_is_plugin_url_safe_file_protocol(self):
        """测试禁止 FILE 协议"""
        result = self.security.is_plugin_url_safe("file:///etc/passwd")
        self.assertFalse(result)

    def test_is_plugin_url_safe_ftp_protocol(self):
        """测试禁止 FTP 协议"""
        result = self.security.is_plugin_url_safe("ftp://example.com/plugin.zip")
        self.assertFalse(result)

    def test_is_plugin_url_safe_localhost(self):
        """测试禁止 localhost"""
        result = self.security.is_plugin_url_safe("http://localhost/plugin.zip")
        self.assertFalse(result)

        result = self.security.is_plugin_url_safe("http://127.0.0.1/plugin.zip")
        self.assertFalse(result)

    def test_is_plugin_url_safe_loopback(self):
        """测试禁止回环地址"""
        result = self.security.is_plugin_url_safe("http://[::1]/plugin.zip")
        self.assertFalse(result)

    def test_is_plugin_url_safe_0_0_0_0(self):
        """测试禁止 0.0.0.0"""
        result = self.security.is_plugin_url_safe("http://0.0.0.0/plugin.zip")
        self.assertFalse(result)

    def test_is_plugin_url_safe_empty(self):
        """测试空 URL"""
        result = self.security.is_plugin_url_safe("")
        self.assertFalse(result)

    def test_is_plugin_url_safe_none(self):
        """测试 None URL"""
        result = self.security.is_plugin_url_safe(None)
        self.assertFalse(result)

    def test_is_plugin_url_safe_non_string(self):
        """测试非字符串 URL"""
        result = self.security.is_plugin_url_safe(12345)
        self.assertFalse(result)


class TestGetSafeWorkDir(unittest.TestCase):
    """安全工作目录测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_get_safe_work_dir_default(self):
        """测试默认工作目录"""
        result = self.security.get_safe_work_dir()
        self.assertTrue(os.path.isdir(result))
        self.assertIn("data", result)

    def test_get_safe_work_dir_custom(self):
        """测试自定义子目录"""
        result = self.security.get_safe_work_dir("custom_dir")
        self.assertTrue(os.path.isdir(result))
        self.assertIn("custom_dir", result)


class TestDeniedPaths(unittest.TestCase):
    """敏感路径配置测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_denied_paths_exist(self):
        """测试敏感路径配置存在"""
        self.assertIsNotNone(self.security.DENIED_PATHS)
        self.assertGreater(len(self.security.DENIED_PATHS), 0)

    def test_denied_paths_coverage(self):
        """测试敏感路径覆盖范围"""
        # 应包含常见系统路径
        denied_lower = [p.lower() for p in self.security.DENIED_PATHS]

        # Windows 路径（在不同系统上可能存在）
        self.assertIn("c:\\windows", denied_lower)
        self.assertIn("c:\\program files", denied_lower)

        # Linux 路径
        self.assertIn("/etc", denied_lower)
        self.assertIn("/bin", denied_lower)
        self.assertIn("/usr/bin", denied_lower)


class TestDangerousCommands(unittest.TestCase):
    """危险命令配置测试"""

    @classmethod
    def setUpClass(cls):
        import security
        cls.security = security

    def test_dangerous_commands_exist(self):
        """测试危险命令配置存在"""
        self.assertIsNotNone(self.security.DANGEROUS_COMMANDS)
        self.assertGreater(len(self.security.DANGEROUS_COMMANDS), 0)

    def test_dangerous_commands_coverage(self):
        """测试危险命令覆盖范围"""
        commands_lower = [c.lower() for c in self.security.DANGEROUS_COMMANDS]

        # 应包含常见危险命令
        self.assertIn("format", commands_lower)
        self.assertIn("rm -rf /", commands_lower)
        self.assertIn("dd", commands_lower)
        self.assertIn("mkfs", commands_lower)


def run_tests():
    """运行测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPathNormalization))
    suite.addTests(loader.loadTestsFromTestCase(TestPathSafetyChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestSanitizePath))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestInputSanitization))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginUrlSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestGetSafeWorkDir))
    suite.addTests(loader.loadTestsFromTestCase(TestDeniedPaths))
    suite.addTests(loader.loadTestsFromTestCase(TestDangerousCommands))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)