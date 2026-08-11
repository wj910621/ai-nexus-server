"""
安全工具模块测试

覆盖路径遍历防护、命令黑名单、输入消毒、插件 URL SSRF 防护等关键安全行为。
"""

import importlib
import os

import pytest


@pytest.fixture
def sec(tmp_path, monkeypatch):
    """在隔离的临时目录中重新加载 security 模块，避免污染真实工作目录。"""
    monkeypatch.chdir(tmp_path)
    import security

    importlib.reload(security)
    return security


def test_normalize_path_valid(sec, tmp_path):
    assert sec.normalize_path("foo/bar") == str(tmp_path / "foo" / "bar")


def test_normalize_path_resolves_traversal(sec, tmp_path):
    assert sec.normalize_path("foo/../bar") == str(tmp_path / "bar")


def test_normalize_path_invalid_input(sec):
    assert sec.normalize_path("") is None
    assert sec.normalize_path(None) is None
    assert sec.normalize_path(123) is None


def test_is_path_safe_allows_allowed_base(sec, tmp_path):
    (tmp_path / "data").mkdir()
    safe_file = tmp_path / "data" / "notes.txt"
    safe_file.write_text("hello")
    assert sec.is_path_safe(str(safe_file)) is True


def test_is_path_safe_denies_sensitive_system_path(sec):
    assert sec.is_path_safe("/etc/passwd") is False
    assert sec.is_path_safe("/bin/sh") is False


def test_is_path_safe_denies_traversal_outside_base(sec, tmp_path):
    outside = tmp_path.parent / "outside_test"
    assert sec.is_path_safe(str(tmp_path / ".." / "outside_test")) is False


def test_sanitize_path_safe_returns_normalized(sec, tmp_path):
    (tmp_path / "data").mkdir()
    assert sec.sanitize_path("data/notes.txt") == str(tmp_path / "data" / "notes.txt")


def test_sanitize_path_unsafe_fallback_to_default_base(sec, tmp_path):
    base = tmp_path / "sandbox"
    base.mkdir()
    assert sec.sanitize_path("../../../etc/passwd", default_base=str(base)) == str(base.resolve())


def test_sanitize_path_unsafe_without_default_base_raises(sec):
    with pytest.raises(ValueError):
        sec.sanitize_path("/etc/passwd")


def test_is_command_safe(sec):
    assert sec.is_command_safe("ls -la") is True
    assert sec.is_command_safe("rm -rf /") is False
    assert sec.is_command_safe("echo hello | dd of=/dev/sda") is False
    assert sec.is_command_safe("") is False
    assert sec.is_command_safe(None) is False


def test_sanitize_input(sec):
    long_text = "a" * 20000
    assert len(sec.sanitize_input(long_text, max_length=100)) == 100

    control = "hello\x00\x07world\u200b"
    assert sec.sanitize_input(control) == "helloworld"

    assert sec.sanitize_input(123) == "123"


def test_is_plugin_url_safe_allows_public_https(sec):
    assert sec.is_plugin_url_safe("https://1.1.1.1/plugin.json") is True


def test_is_plugin_url_safe_blocks_private_and_local(sec):
    assert sec.is_plugin_url_safe("http://127.0.0.1/plugin.json") is False
    assert sec.is_plugin_url_safe("http://localhost/plugin.json") is False
    assert sec.is_plugin_url_safe("http://192.168.1.1/plugin.json") is False
    assert sec.is_plugin_url_safe("http://10.0.0.1/plugin.json") is False


def test_is_plugin_url_safe_blocks_non_http_scheme(sec):
    assert sec.is_plugin_url_safe("ftp://example.com/plugin.json") is False
    assert sec.is_plugin_url_safe("file:///etc/passwd") is False


def test_is_plugin_url_safe_rejects_invalid_url(sec):
    assert sec.is_plugin_url_safe("") is False
    assert sec.is_plugin_url_safe("not-a-url") is False


def test_get_safe_work_dir(sec, tmp_path):
    work_dir = sec.get_safe_work_dir("data/work")
    expected = str((tmp_path / "data" / "work").resolve())
    assert work_dir == expected
    assert os.path.isdir(work_dir)
