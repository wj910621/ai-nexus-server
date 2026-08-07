"""
配置模块测试
覆盖：配置校验逻辑
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from config import Settings


def _validate_with_settings(s):
    """使用指定 Settings 实例执行配置校验"""
    issues = []
    if not s.deepseek_api_key and not s.use_local_first:
        issues.append("未配置 DEEPSEEK_API_KEY，且未启用本地模型（USE_LOCAL_FIRST=false），真实 LLM 模式不可用。")
    if s.use_local_first:
        if not s.local_base_url.startswith("http"):
            issues.append(f"LOCAL_BASE_URL 格式不正确：{s.local_base_url}")
    return issues


class TestValidateConfig:
    def test_no_api_key_no_local_shows_issue(self):
        """未配置 API Key 且未启用本地模型时应报告问题"""
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("USE_LOCAL_FIRST", None)
        s = Settings()
        issues = _validate_with_settings(s)
        if not s.deepseek_api_key and not s.use_local_first:
            assert any("DEEPSEEK_API_KEY" in i for i in issues)

    def test_valid_local_config(self):
        """本地模式配置正确时不应报告 base_url 问题"""
        os.environ["USE_LOCAL_FIRST"] = "true"
        os.environ["LOCAL_BASE_URL"] = "http://localhost:11434"
        try:
            s = Settings()
            issues = _validate_with_settings(s)
            base_url_issues = [i for i in issues if "LOCAL_BASE_URL" in i]
            assert len(base_url_issues) == 0
        finally:
            os.environ.pop("USE_LOCAL_FIRST", None)
            os.environ.pop("LOCAL_BASE_URL", None)

    def test_invalid_base_url(self):
        """本地模式 base_url 格式不正确时应报告"""
        os.environ["USE_LOCAL_FIRST"] = "true"
        os.environ["LOCAL_BASE_URL"] = "ftp://invalid"
        try:
            s = Settings()
            issues = _validate_with_settings(s)
            base_url_issues = [i for i in issues if "LOCAL_BASE_URL" in i]
            assert len(base_url_issues) > 0
        finally:
            os.environ.pop("USE_LOCAL_FIRST", None)
            os.environ.pop("LOCAL_BASE_URL", None)


class TestSettingsDefaults:
    def test_default_api_bind_localhost(self):
        """默认应仅监听本地回环"""
        s = Settings()
        assert s.api_bind_host == "127.0.0.1"

    def test_default_api_key_required(self):
        """默认应要求 API Key"""
        s = Settings()
        assert s.api_key_required is True

    def test_default_rate_limit_enabled(self):
        """默认应启用限流"""
        s = Settings()
        assert s.rate_limit_enabled is True

    def test_default_max_content_length(self):
        s = Settings()
        assert s.max_content_length_mb == 64

    def test_rate_limit_defaults(self):
        s = Settings()
        assert s.rate_limit_requests_per_minute == 60
        assert s.rate_limit_burst == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
