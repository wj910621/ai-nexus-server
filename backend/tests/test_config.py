"""配置测试"""
import pytest
from app.core.config import Settings, settings


def test_settings_loads_defaults():
    """测试配置能正常加载"""
    assert settings.app_name == "Y·NEX Story Studio"
    assert settings.app_env in ["development", "production", "testing"]
    assert settings.jwt_algorithm == "HS256"


def test_cors_origins_list():
    """测试 CORS 来源解析"""
    s = Settings(cors_origins="http://a.com, http://b.com ,http://c.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]


def test_environment_flags():
    """测试环境标志"""
    s = Settings(app_env="development")
    assert s.is_development is True
    assert s.is_production is False

    s = Settings(app_env="production")
    assert s.is_development is False
    assert s.is_production is True


def test_benchmark_enabled_default():
    """benchmark_enabled 默认 True"""
    from app.core.config import Settings
    s = Settings()
    assert s.benchmark_enabled is True


def test_benchmark_cache_ttl_default():
    """benchmark_cache_ttl 默认 3600"""
    from app.core.config import Settings
    s = Settings()
    assert s.benchmark_cache_ttl == 3600


def test_llama_cpp_model_path_default():
    """llama_cpp_model_path 默认空字符串"""
    from app.core.config import Settings
    s = Settings()
    assert s.llama_cpp_model_path == ""


def test_llama_cpp_n_gpu_layers_default():
    """llama_cpp_n_gpu_layers 默认 -1（全部卸载）"""
    from app.core.config import Settings
    s = Settings()
    assert s.llama_cpp_n_gpu_layers == -1


def test_replicate_api_token_default():
    """P3: replicate_api_token 默认为空"""
    from app.core.config import Settings
    s = Settings()
    assert s.replicate_api_token == ""


def test_replicate_train_model_default():
    """P3: replicate_train_model 默认为空"""
    from app.core.config import Settings
    s = Settings()
    assert s.replicate_train_model == ""


def test_lora_train_local_enabled_default():
    """P3: lora_train_local_enabled 默认 True"""
    from app.core.config import Settings
    s = Settings()
    assert s.lora_train_local_enabled is True


def test_lora_train_cloud_enabled_default():
    """P3: lora_train_cloud_enabled 默认 True"""
    from app.core.config import Settings
    s = Settings()
    assert s.lora_train_cloud_enabled is True


def test_blip_model_name_default():
    """P3: blip_model_name 默认值"""
    from app.core.config import Settings
    s = Settings()
    assert s.blip_model_name == "Salesforce/blip-image-captioning-large"
