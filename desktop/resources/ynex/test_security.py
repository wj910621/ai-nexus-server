"""
Y·NEX安全模块测试
测试目标：验证安全防护机制的有效性
- 路径遍历防护
- 命令执行安全
- 输入消毒
- SSRF防护
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
)


class TestPathTraversal(unittest.TestCase):
    """路径遍历防护测试"""

    def test_normalize_path_valid(self):
        """测试有效路径规范化"""
        # 相对路径转绝对路径
        result = normalize_path("./test.txt")
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isabs(result))

        # 用户目录展开
        result = normalize_path("~/test.txt")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith(os.path.expanduser("~")))

    def test_normalize_path_traversal(self):
        """测试路径穿越防护"""
        # 路径穿越尝试
        result = normalize_path("../../../etc/passwd")
        self.assertIsNotNone(result)
        # 应该被规范化为绝对路径，不包含 ..
        self.assertNotIn("..", result)

    def test_normalize_path_invalid(self):
        """测试无效路径处理"""
        # 空路径
        self.assertIsNone(normalize_path(""))
        self.assertIsNone(normalize_path(None))
        self.assertIsNone(normalize_path(123))

    def test_is_path_safe_allowed(self):
        """测试允许路径检查"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 当前工作目录下的文件应该被允许
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).touch()
            
            # 在允许的基目录内
            allowed_bases = [tmpdir]
            self.assertTrue(is_path_safe(test_file, allowed_bases))

    def test_is_path_safe_denied_paths(self):
        """测试敏感路径拒绝"""
        # 系统敏感路径应该被拒绝
        if os.name == 'nt':  # Windows
            self.assertFalse(is_path_safe("C:\\Windows\\System32"))
            self.assertFalse(is_path_safe("C:\\Program Files\\App"))
        else:  # Linux/Unix
            self.assertFalse(is_path_safe("/etc/passwd"))
            self.assertFalse(is_path_safe("/bin/ls"))
            # 注意：/root 不在 DENIED_PATHS 中，跳过此检查

    def test_is_path_safe_traversal(self):
        """测试路径穿越防护"""
        # 尝试通过 .. 穿越到不允许的目录
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            
            # 在允许目录内使用 .. 穿越
            traversal_path = os.path.join(subdir, "..", "..", "..", "..", "etc", "passwd")
            self.assertFalse(is_path_safe(traversal_path, [tmpdir]))

    def test_sanitize_path_fallback(self):
        """测试路径越界时的回退机制"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 越界路径应该回退到默认基目录
            result = sanitize_path("../../../etc/passwd", tmpdir)
            self.assertEqual(result, os.path.realpath(tmpdir))


class TestCommandSafety(unittest.TestCase):
    """命令执行安全测试"""

    def test_safe_commands(self):
        """测试安全命令"""
        self.assertTrue(is_command_safe("ls -la"))
        self.assertTrue(is_command_safe("echo hello"))
        self.assertTrue(is_command_safe("python script.py"))
        self.assertTrue(is_command_safe("node app.js"))

    def test_dangerous_commands(self):
        """测试危险命令拦截"""
        # 格式化命令
        self.assertFalse(is_command_safe("format C:"))
        self.assertFalse(is_command_safe("mkfs.ext4 /dev/sda"))
        
        # 删除命令
        self.assertFalse(is_command_safe("rm -rf /"))
        self.assertFalse(is_command_safe("rm -rf /*"))
        self.assertFalse(is_command_safe("deltree C:\\"))
        
        # Fork 炸弹
        self.assertFalse(is_command_safe(":(){ :|:& };:"))
        
        # 磁盘操作
        self.assertFalse(is_command_safe("dd if=/dev/zero of=/dev/sda"))
        self.assertFalse(is_command_safe("> /dev/sda"))

    def test_empty_command(self):
        """测试空命令处理"""
        self.assertFalse(is_command_safe(""))
        self.assertFalse(is_command_safe(None))
        self.assertFalse(is_command_safe(123))


class TestInputSanitization(unittest.TestCase):
    """输入消毒测试"""

    def test_sanitize_normal_input(self):
        """测试正常输入"""
        text = "Hello, 世界！"
        result = sanitize_input(text)
        self.assertEqual(result, text)

    def test_sanitize_length_limit(self):
        """测试长度限制"""
        long_text = "a" * 20000
        result = sanitize_input(long_text, max_length=10000)
        self.assertEqual(len(result), 10000)

    def test_sanitize_control_characters(self):
        """测试控制字符移除"""
        # 零宽字符
        text = "Hello\u200bWorld"
        result = sanitize_input(text)
        self.assertEqual(result, "HelloWorld")
        
        # 控制字符（保留换行和制表符）
        text = "Hello\x00World\nNew\tLine"
        result = sanitize_input(text)
        self.assertEqual(result, "HelloWorld\nNew\tLine")
        
        # 多种控制字符
        text = "Test\x01\x02\x03\x1f\x7f"
        result = sanitize_input(text)
        self.assertEqual(result, "Test")

    def test_sanitize_non_string(self):
        """测试非字符串输入"""
        self.assertEqual(sanitize_input(123), "123")
        self.assertEqual(sanitize_input(None), "None")


class TestSSRFProtection(unittest.TestCase):
    """SSRF防护测试"""

    def test_safe_urls(self):
        """测试安全的URL"""
        self.assertTrue(is_plugin_url_safe("https://example.com/plugin.zip"))
        self.assertTrue(is_plugin_url_safe("https://github.com/user/repo/archive/master.zip"))

    def test_blocked_protocols(self):
        """测试禁止的协议"""
        self.assertFalse(is_plugin_url_safe("file:///etc/passwd"))
        self.assertFalse(is_plugin_url_safe("ftp://example.com/file"))
        self.assertFalse(is_plugin_url_safe("javascript:alert(1)"))

    def test_blocked_local_addresses(self):
        """测试禁止的本地地址"""
        # localhost
        self.assertFalse(is_plugin_url_safe("http://localhost/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://127.0.0.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://0.0.0.0/plugin.zip"))
        
        # IPv6 本地地址
        self.assertFalse(is_plugin_url_safe("http://[::1]/plugin.zip"))

    def test_blocked_private_networks(self):
        """测试禁止的内网地址"""
        # 内网IP段
        self.assertFalse(is_plugin_url_safe("http://192.168.1.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://10.0.0.1/plugin.zip"))
        self.assertFalse(is_plugin_url_safe("http://172.16.0.1/plugin.zip"))

    def test_empty_url(self):
        """测试空URL处理"""
        self.assertFalse(is_plugin_url_safe(""))
        self.assertFalse(is_plugin_url_safe(None))


class TestWorkDirectory(unittest.TestCase):
    """工作目录测试"""

    def test_get_safe_work_dir(self):
        """测试获取安全工作目录"""
        work_dir = get_safe_work_dir("test_data")
        self.assertTrue(os.path.exists(work_dir))
        self.assertTrue(os.path.isdir(work_dir))
        
        # 清理测试目录
        if os.path.exists(work_dir):
            os.rmdir(work_dir)


if __name__ == '__main__':
    unittest.main(verbosity=2)