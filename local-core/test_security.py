"""
安全模块单元测试
覆盖路径遍历防护、命令安全检查、输入消毒、插件 URL 安全
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
)


class TestSecurity:
    def test_normalize_path_valid(self):
        test_path = "./test/file.txt"
        result = normalize_path(test_path)
        assert result is not None
        assert os.path.isabs(result)

    def test_normalize_path_empty(self):
        result = normalize_path("")
        assert result is None

    def test_normalize_path_none(self):
        result = normalize_path(None)
        assert result is None

    def test_normalize_path_invalid(self):
        with patch("os.path.abspath", side_effect=Exception("invalid")):
            result = normalize_path("/invalid/path")
            assert result is None

    def test_is_path_safe_allowed(self):
        safe_path = os.path.join(os.getcwd(), "data", "test.txt")
        assert is_path_safe(safe_path) is True

    def test_is_path_safe_denied(self):
        assert is_path_safe("/etc/passwd") is False
        assert is_path_safe("/bin/bash") is False

    def test_is_path_safe_traversal(self):
        malicious = os.path.join(os.getcwd(), "..", "etc", "passwd")
        assert is_path_safe(malicious) is False

    def test_is_path_safe_relative_traversal(self):
        assert is_path_safe("../../../etc/passwd") is False

    def test_is_path_safe_empty(self):
        assert is_path_safe("") is False

    def test_sanitize_path_safe(self):
        safe_path = "data/test.txt"
        result = sanitize_path(safe_path, os.getcwd())
        assert os.path.isabs(result)

    def test_sanitize_path_unsafe(self):
        unsafe_path = "../../etc/passwd"
        with pytest.raises(ValueError):
            sanitize_path(unsafe_path)

    def test_is_command_safe_normal(self):
        assert is_command_safe("ls -la") is True
        assert is_command_safe("echo hello") is True

    def test_is_command_safe_dangerous(self):
        assert is_command_safe("rm -rf /") is False
        assert is_command_safe("rm -rf /*") is False
        assert is_command_safe("format C:") is False
        assert is_command_safe(":(){ :|:& };:\n") is False
        assert is_command_safe("> /dev/sda") is False

    def test_is_command_safe_empty(self):
        assert is_command_safe("") is False
        assert is_command_safe(None) is False

    def test_sanitize_input_normal(self):
        text = "Hello World"
        result = sanitize_input(text)
        assert result == "Hello World"

    def test_sanitize_input_truncation(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text)
        assert len(result) == 10000

    def test_sanitize_input_control_chars(self):
        text_with_control = "Hello\x00World\x07"
        result = sanitize_input(text_with_control)
        assert result == "HelloWorld"

    def test_sanitize_input_zero_width(self):
        text_with_zero_width = "Hello\u200bWorld"
        result = sanitize_input(text_with_zero_width)
        assert result == "HelloWorld"

    def test_is_plugin_url_safe_https(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 80))]):
            assert is_plugin_url_safe("https://github.com/user/repo.git") is True
            assert is_plugin_url_safe("http://plugins.example.com/plugin.zip") is True

    def test_is_plugin_url_safe_localhost(self):
        assert is_plugin_url_safe("http://localhost/plugin.zip") is False
        assert is_plugin_url_safe("http://127.0.0.1/plugin.zip") is False
        assert is_plugin_url_safe("http://0.0.0.0/plugin.zip") is False

    def test_is_plugin_url_safe_invalid_scheme(self):
        assert is_plugin_url_safe("file:///local/path.zip") is False
        assert is_plugin_url_safe("ftp://evil.com/plugin.zip") is False

    def test_is_plugin_url_safe_empty(self):
        assert is_plugin_url_safe("") is False
        assert is_plugin_url_safe(None) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
