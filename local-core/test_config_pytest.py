"""
config.py 的 pytest 测试
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from config import Settings, validate_config


# ---------------------------------------------------------------------------
# Settings 类默认值测试
# ---------------------------------------------------------------------------

class TestSettingsDefaults:
    """测试 Settings 类的默认值"""

    def test_default_api_bind_host(self):
        s = Settings()
        assert s.api_bind_host == "127.0.0.1"

    def test_default_rate_limit_enabled(self):
        s = Settings()
        assert s.rate_limit_enabled is True

    def test_default_use_local_first(self):
        s = Settings()
        assert s.use_local_first is False

    def test_default_deepseek_api_key(self):
        s = Settings()
        assert s.deepseek_api_key == ""

    def test_default_local_base_url(self):
        s = Settings()
        assert s.local_base_url == "http://localhost:11434"

    def test_default_rate_limit_requests_per_minute(self):
        s = Settings()
        assert s.rate_limit_requests_per_minute == 60

    def test_default_rate_limit_burst(self):
        s = Settings()
        assert s.rate_limit_burst == 10

    def test_default_api_key_required(self):
        s = Settings()
        assert s.api_key_required is True

    def test_default_max_content_length_mb(self):
        s = Settings()
        assert s.max_content_length_mb == 64

    def test_default_trusted_subnets(self):
        s = Settings()
        assert s.trusted_subnets == "127.0.0.1/32"


class TestSettingsInstance:
    """测试全局 settings 实例可访问"""

    def test_global_settings_exists(self):
        from config import settings
        assert settings is not None

    def test_global_settings_is_settings_instance(self):
        from config import settings
        assert isinstance(settings, Settings)


# ---------------------------------------------------------------------------
# validate_config() 测试
# ---------------------------------------------------------------------------

class TestValidateConfig:
    """测试 validate_config() 函数"""

    def test_issues_when_no_api_key_and_not_local_first(self, monkeypatch):
        """deepseek_api_key 为空且 use_local_first=False 时应返回问题"""
        import config
        monkeypatch.setattr(config.settings, "deepseek_api_key", "")
        monkeypatch.setattr(config.settings, "use_local_first", False)

        issues = validate_config()
        assert len(issues) >= 1
        assert any("DEEPSEEK_API_KEY" in issue for issue in issues)

    def test_no_issues_when_use_local_first(self, monkeypatch):
        """use_local_first=True 时，即使没有 API Key 也不应报错"""
        import config
        monkeypatch.setattr(config.settings, "use_local_first", True)
        monkeypatch.setattr(config.settings, "deepseek_api_key", "")
        monkeypatch.setattr(config.settings, "local_base_url", "http://localhost:11434")

        issues = validate_config()
        assert not any("DEEPSEEK_API_KEY" in issue for issue in issues)

    def test_issue_for_invalid_local_base_url(self, monkeypatch):
        """local_base_url 不以 http 开头时应返回问题"""
        import config
        monkeypatch.setattr(config.settings, "use_local_first", True)
        monkeypatch.setattr(config.settings, "local_base_url", "ftp://invalid-host")

        issues = validate_config()
        assert any("LOCAL_BASE_URL" in issue for issue in issues)

    def test_no_issue_for_valid_local_base_url(self, monkeypatch):
        """local_base_url 格式正确时不应报错"""
        import config
        monkeypatch.setattr(config.settings, "use_local_first", True)
        monkeypatch.setattr(config.settings, "local_base_url", "http://localhost:11434")

        issues = validate_config()
        assert not any("LOCAL_BASE_URL" in issue for issue in issues)

    def test_no_issues_with_api_key_and_not_local_first(self, monkeypatch):
        """有 API Key 且 use_local_first=False 时不应返回 API Key 相关问题"""
        import config
        monkeypatch.setattr(config.settings, "deepseek_api_key", "sk-test-123456")
        monkeypatch.setattr(config.settings, "use_local_first", False)

        issues = validate_config()
        assert not any("DEEPSEEK_API_KEY" in issue for issue in issues)
