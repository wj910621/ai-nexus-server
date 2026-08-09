"""
配置模块测试
覆盖：配置加载、配置校验逻辑
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_settings_defaults():
    """默认配置值"""
    print("\n=== Settings 默认值 ===")

    from config import Settings
    s = Settings()

    # 安全相关默认值
    assert s.api_bind_host == "127.0.0.1", "默认应仅监听本地"
    assert s.api_key_required is True, "生产环境应要求 API Key"
    assert s.rate_limit_enabled is True, "限流应默认启用"
    assert s.max_content_length_mb == 64, "默认最大请求体 64MB"
    print(f"  api_bind_host: {s.api_bind_host}")
    print(f"  api_key_required: {s.api_key_required}")
    print(f"  rate_limit_enabled: {s.rate_limit_enabled}")


def test_settings_rate_limit():
    """限流配置"""
    print("\n=== Settings 限流配置 ===")

    from config import Settings
    s = Settings()

    assert s.rate_limit_requests_per_minute == 60, "默认每分钟 60 次"
    assert s.rate_limit_burst == 10, "默认突发 10"
    print(f"  每分钟: {s.rate_limit_requests_per_minute}, 突发: {s.rate_limit_burst}")


def test_validate_config_no_api_key():
    """未配置 API Key 且未启用本地模式"""
    print("\n=== validate_config 无 API Key ===")

    from config import Settings, validate_config
    # 使用独立实例，不影响全局
    import config
    old_settings = config.settings
    try:
        test_settings = Settings(deepseek_api_key="", use_local_first=False)
        config.settings = test_settings
        issues = validate_config()
        assert any("DEEPSEEK_API_KEY" in i for i in issues), "应检测到缺少 API Key"
        print(f"  检测到问题: {[i for i in issues if 'API_KEY' in i][0]}")
    finally:
        config.settings = old_settings


def test_validate_config_local_mode_bad_url():
    """本地模式 URL 格式错误"""
    print("\n=== validate_config 本地模式 URL 错误 ===")

    from config import Settings, validate_config
    import config
    old_settings = config.settings
    try:
        test_settings = Settings(
            use_local_first=True,
            local_base_url="ftp://bad-url",
            deepseek_api_key="",
        )
        config.settings = test_settings
        issues = validate_config()
        assert any("LOCAL_BASE_URL" in i for i in issues), "应检测到 URL 格式错误"
        print(f"  检测到问题: {[i for i in issues if 'LOCAL_BASE_URL' in i][0]}")
    finally:
        config.settings = old_settings


def test_validate_config_local_mode_valid():
    """本地模式正常配置"""
    print("\n=== validate_config 本地模式正常 ===")

    from config import Settings, validate_config
    import config
    old_settings = config.settings
    try:
        test_settings = Settings(
            use_local_first=True,
            local_base_url="http://localhost:11434",
            deepseek_api_key="",
        )
        config.settings = test_settings
        issues = validate_config()
        # 本地模式不要求 API Key
        assert not any("DEEPSEEK_API_KEY" in i for i in issues), "本地模式不应报 API Key 缺失"
        print(f"  问题数: {len(issues)}")
    finally:
        config.settings = old_settings


def test_validate_config_cors_origins():
    """CORS 配置"""
    print("\n=== Settings CORS 配置 ===")

    from config import Settings
    s = Settings()
    origins = s.cors_origins.split(",")
    assert "http://localhost:3000" in origins, "应包含 localhost:3000"
    assert len(origins) >= 3, "应有多个默认 CORS 源"
    print(f"  CORS 源数量: {len(origins)}")


def test_settings_memory():
    """记忆和知识库配置"""
    print("\n=== Settings 记忆配置 ===")

    from config import Settings
    s = Settings()

    assert s.memory_db == "data/memory.db"
    assert s.max_history == 20
    assert s.knowledge_dir == "data/knowledge"
    print(f"  memory_db: {s.memory_db}, max_history: {s.max_history}")


def main():
    print("=" * 60)
    print("  配置模块测试")
    print("=" * 60)

    test_settings_defaults()
    test_settings_rate_limit()
    test_validate_config_no_api_key()
    test_validate_config_local_mode_bad_url()
    test_validate_config_local_mode_valid()
    test_validate_config_cors_origins()
    test_settings_memory()

    print("\n" + "=" * 60)
    print("  配置模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
